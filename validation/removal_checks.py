from __future__ import annotations

import math
from dataclasses import replace
from itertools import pairwise
from typing import Any

from shapely.geometry import LineString, Point, Polygon, box
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from core.constants import (
    BACK_FACE_DEPTH_MODES,
    BACK_FACE_FEATURE_TYPES,
    WEB_CHECK_FEATURE_TYPES,
    FeatureType,
)
from core.geometry import chamfer_included_angle, engraving_paths, extract_shape_geometry, pocket_region, polygon_region
from ir.removal_intent import BevelSpec, Bounds2D, ChamferSpec, RemovalIntent, RoundoverSpec
from validation.core import ValidationResult

_WEB_TOLERANCE_MM = 1e-6
_OVERLAP_CLEARANCE_TOLERANCE_MM = 1e-6
_GROOVE_ASPECT_RATIO = 1.5
_PERPENDICULAR_DOT_TOLERANCE = 1e-9


def check_depth_profile(
    intent: RemovalIntent,
    sheet_thickness_mm: float,
    available_v_angles: list[float] | None = None,
) -> ValidationResult:
    result = ValidationResult()
    profile = intent.depth_profile

    if profile.mode == "linear_gradient" and abs(profile.z_bottom) > sheet_thickness_mm:
        result.add_error(
            f"Gradient depth ({abs(profile.z_bottom):.2f}mm) exceeds sheet thickness ({sheet_thickness_mm:.2f}mm)",
            region_id=intent.region_id,
            gradient_depth_mm=abs(profile.z_bottom),
            sheet_thickness_mm=sheet_thickness_mm,
        )

    if profile.mode == "v_carve":
        v_angle = profile.v_angle_deg
        if v_angle is None:
            raise ValueError(f"v_carve mode requires v_angle_deg, region: {intent.region_id}")

        if available_v_angles is not None:
            matching = [a for a in available_v_angles if abs(a - v_angle) < 1.0]
            if not matching:
                result.add_error(
                    f"V-carve requires {v_angle:.0f}° V-bit, but none available. "
                    f"Available angles: {available_v_angles}",
                    region_id=intent.region_id,
                    required_angle=v_angle,
                    available_angles=available_v_angles,
                )

        if abs(profile.z_bottom) > sheet_thickness_mm:
            result.add_warning(
                f"V-carve depth ({abs(profile.z_bottom):.2f}mm) may exceed material",
                region_id=intent.region_id,
                v_carve_depth_mm=abs(profile.z_bottom),
                sheet_thickness_mm=sheet_thickness_mm,
            )

    bevel_data = intent.edge_feature if isinstance(intent.edge_feature, BevelSpec) else None
    if bevel_data:
        bevel_width = bevel_data.width_mm
        bevel_angle = bevel_data.angle_deg
        inner_depth = bevel_data.inner_depth_mm

        if bevel_angle > 0 and bevel_angle < 90:
            expected_depth = bevel_width * math.tan(math.radians(bevel_angle))

            if inner_depth > expected_depth * 1.1:
                result.add_warning(
                    f"Bevel inner depth ({inner_depth:.2f}mm) may not be achievable "
                    f"with {bevel_angle:.0f}° angle and {bevel_width:.2f}mm width",
                    region_id=intent.region_id,
                    inner_depth_mm=inner_depth,
                    expected_depth_mm=expected_depth,
                    bevel_angle_deg=bevel_angle,
                    bevel_width_mm=bevel_width,
                )

    return result


def check_edge_feature(  # noqa: C901 — edge validation dispatcher
    intent: RemovalIntent,
    sheet_thickness_mm: float,
    available_v_angles: list[float] | None = None,
) -> ValidationResult:
    result = ValidationResult()

    spec = intent.edge_feature
    if spec is None:
        return result

    if isinstance(spec, BevelSpec):
        width = spec.width_mm
        angle = spec.angle_deg
        inner_depth = spec.inner_depth_mm

        if width <= 0.0:
            result.add_error(
                f"Bevel width must be positive, got {width:.2f}mm",
                region_id=intent.region_id,
                bevel_width_mm=width,
            )

        if angle <= 0.0 or angle >= 90.0:
            result.add_warning(
                f"Bevel angle {angle:.1f}° outside practical range (0°, 90°)",
                region_id=intent.region_id,
                bevel_angle_deg=angle,
            )

        if inner_depth < 0.0:
            result.add_error(
                f"Bevel inner depth must be non-negative, got {inner_depth:.2f}mm",
                region_id=intent.region_id,
                inner_depth_mm=inner_depth,
            )

        if inner_depth > sheet_thickness_mm:
            result.add_error(
                f"Bevel inner depth ({inner_depth:.2f}mm) exceeds sheet thickness ({sheet_thickness_mm:.2f}mm)",
                region_id=intent.region_id,
                inner_depth_mm=inner_depth,
                sheet_thickness_mm=sheet_thickness_mm,
            )

    elif isinstance(spec, ChamferSpec):
        width = spec.width_mm
        angle = spec.angle_deg

        if width <= 0.0:
            result.add_error(
                f"Chamfer width must be positive, got {width:.2f}mm",
                region_id=intent.region_id,
                chamfer_width_mm=width,
            )

        if angle <= 0.0 or angle >= 90.0:
            result.add_warning(
                f"Chamfer angle {angle:.1f}° outside practical range (0°, 90°)",
                region_id=intent.region_id,
                chamfer_angle_deg=angle,
            )

        if 0.0 < angle < 90.0:
            cut_depth = width * math.tan(math.radians(angle))
            if cut_depth > sheet_thickness_mm:
                result.add_error(
                    f"Chamfer cut depth ({cut_depth:.2f}mm) exceeds sheet thickness ({sheet_thickness_mm:.2f}mm)",
                    region_id=intent.region_id,
                    chamfer_cut_depth_mm=cut_depth,
                    sheet_thickness_mm=sheet_thickness_mm,
                )

    elif isinstance(spec, RoundoverSpec):
        radius = spec.radius_mm

        if radius <= 0.0:
            result.add_error(
                f"Roundover radius must be positive, got {radius:.2f}mm",
                region_id=intent.region_id,
                roundover_radius_mm=radius,
            )

        if radius > sheet_thickness_mm:
            result.add_error(
                f"Roundover radius ({radius:.2f}mm) exceeds sheet thickness ({sheet_thickness_mm:.2f}mm)",
                region_id=intent.region_id,
                roundover_radius_mm=radius,
                sheet_thickness_mm=sheet_thickness_mm,
            )

    if available_v_angles is not None and len(available_v_angles) > 0 and isinstance(spec, (BevelSpec, ChamferSpec)):
        desired_included = (
            chamfer_included_angle(spec.angle_deg) if isinstance(spec, ChamferSpec) else spec.angle_deg * 2.0
        )
        matching = [a for a in available_v_angles if abs(a - desired_included) < 5.0]
        if not matching:
            result.add_warning(
                f"No V-bit with included angle near {desired_included:.0f}° available. Available: {available_v_angles}",
                region_id=intent.region_id,
                desired_angle=desired_included,
                available_angles=available_v_angles,
            )

    bounds = intent.bounds
    feature_width = min(bounds.width, bounds.height)
    if isinstance(spec, (BevelSpec, ChamferSpec)) and spec.width_mm > feature_width / 2.0:
        result.add_warning(
            f"Edge feature width ({spec.width_mm:.2f}mm) exceeds half the feature size "
            f"({feature_width:.2f}mm) — tool clearance may be insufficient",
            region_id=intent.region_id,
            edge_width_mm=spec.width_mm,
            feature_size_mm=feature_width,
        )

    return result


def _match_feature_types(
    a: RemovalIntent,
    b: RemovalIntent,
    type_a: str,
    type_b: str | tuple[str, ...],
) -> tuple[RemovalIntent, RemovalIntent] | None:
    hint_type_a = a.hint_type
    hint_type_b = b.hint_type

    type_b_set = (type_b,) if isinstance(type_b, str) else type_b

    if hint_type_a == type_a and hint_type_b in type_b_set:
        return (a, b)
    if hint_type_b == type_a and hint_type_a in type_b_set:
        return (b, a)
    return None


def _match_same_type(
    a: RemovalIntent,
    b: RemovalIntent,
    feature_type: str,
) -> bool:
    return a.hint_type == feature_type and b.hint_type == feature_type


def _are_sibling_features(a: RemovalIntent, b: RemovalIntent) -> bool:
    if a.hint_type != b.hint_type:
        return False
    if abs(a.depth_mm() - b.depth_mm()) > 0.001:
        return False
    prefix_a = a.region_id.rsplit("_", 1)[0]
    prefix_b = b.region_id.rsplit("_", 1)[0]
    return prefix_a == prefix_b and "generated_" in prefix_a


def _are_perpendicular_pockets(a: RemovalIntent, b: RemovalIntent) -> bool:
    if not _match_same_type(a, b, FeatureType.POCKET):
        return False

    is_a_horizontal = a.bounds.width > a.bounds.height * _GROOVE_ASPECT_RATIO
    is_a_vertical = a.bounds.height > a.bounds.width * _GROOVE_ASPECT_RATIO
    is_b_horizontal = b.bounds.width > b.bounds.height * _GROOVE_ASPECT_RATIO
    is_b_vertical = b.bounds.height > b.bounds.width * _GROOVE_ASPECT_RATIO

    if (is_a_horizontal and is_b_vertical) or (is_a_vertical and is_b_horizontal):
        return True
    axis_a, axis_b = _pocket_long_axis(a), _pocket_long_axis(b)
    if axis_a is None or axis_b is None:
        return False
    return abs(axis_a[0] * axis_b[0] + axis_a[1] * axis_b[1]) <= _PERPENDICULAR_DOT_TOLERANCE


def _is_pocket_on_profile_edge(a: RemovalIntent, b: RemovalIntent) -> bool:
    match = _match_feature_types(a, b, FeatureType.PROFILE, FeatureType.POCKET)
    if match is None:
        return False
    profile, pocket = match

    return (
        abs(pocket.bounds.x_min - profile.bounds.x_min) < 1.0
        or abs(pocket.bounds.x_max - profile.bounds.x_max) < 1.0
        or abs(pocket.bounds.y_min - profile.bounds.y_min) < 1.0
        or abs(pocket.bounds.y_max - profile.bounds.y_max) < 1.0
    )


def _is_inside_profile(a: RemovalIntent, b: RemovalIntent) -> bool:
    match = _match_feature_types(
        a, b, FeatureType.PROFILE, (FeatureType.HOLE, "drill", FeatureType.POCKET, FeatureType.ENGRAVE)
    )
    if match is None:
        return False
    profile, contained = match

    return (
        contained.bounds.x_min >= profile.bounds.x_min
        and contained.bounds.x_max <= profile.bounds.x_max
        and contained.bounds.y_min >= profile.bounds.y_min
        and contained.bounds.y_max <= profile.bounds.y_max
    )


def _engraving_trace(intent: RemovalIntent) -> BaseGeometry | None:
    if intent.hint_type != FeatureType.ENGRAVE:
        return None
    geometry = extract_shape_geometry(intent.shape, intent.bounds, intent.shape_geometry)
    paths = engraving_paths(intent.shape, geometry, intent.bounds.center)
    if not paths:
        return None
    return unary_union([LineString(path) if len(path) > 1 else Point(path[0]) for path in paths])


def _has_boundary_modifiers(intent: RemovalIntent) -> bool:
    return (
        intent.constraints.edge_treatment is not None
        or intent.dogbone is not None
        or intent.dogbone_corners is not None
    )


def _profile_containment_region(intent: RemovalIntent) -> BaseGeometry | None:
    if _has_boundary_modifiers(intent):
        return None
    shape = intent.shape.lower()
    if shape == "rect" or (shape == "circle" and intent.side == "inside"):
        return box(intent.bounds.x_min, intent.bounds.y_min, intent.bounds.x_max, intent.bounds.y_max)
    if shape == "polygon":
        return polygon_region(replace(intent.shape_geometry, holes=None), intent.bounds.center)
    return None


def _is_nested_inside_profile(a: RemovalIntent, b: RemovalIntent) -> bool:
    if not _match_same_type(a, b, FeatureType.PROFILE):
        return False
    outer, inner = (a, b) if a.side == "outside" else (b, a)
    if outer.side != "outside" or inner.side != "inside":
        return False
    outer_region = _profile_containment_region(outer)
    inner_region = _profile_containment_region(inner)
    if outer_region is None or inner_region is None or not outer_region.is_valid or not inner_region.is_valid:
        return False
    return (
        outer_region.contains(inner_region)
        and outer_region.boundary.distance(inner_region) > _OVERLAP_CLEARANCE_TOLERANCE_MM
    )


def _is_compatible_profile_edge(a: RemovalIntent, b: RemovalIntent) -> bool:
    match = _match_feature_types(a, b, FeatureType.PROFILE, (FeatureType.CHAMFER, FeatureType.ROUNDOVER))
    if match is None:
        return False
    profile, edge = match
    if profile.side not in ("inside", "outside") or profile.depth_profile.z_top != 0 or edge.depth_profile.z_top != 0:
        return False
    spec = edge.edge_feature
    if not isinstance(spec, (ChamferSpec, RoundoverSpec)):
        return False
    if isinstance(spec, ChamferSpec) and (spec.width_mm <= 0 or not 0 < spec.angle_deg < 90):
        return False
    if isinstance(spec, RoundoverSpec) and spec.radius_mm <= 0:
        return False
    depth = (
        spec.radius_mm if isinstance(spec, RoundoverSpec) else spec.width_mm * math.tan(math.radians(spec.angle_deg))
    )
    if not math.isclose(edge.depth_mm(), depth, rel_tol=0, abs_tol=_OVERLAP_CLEARANCE_TOLERANCE_MM):
        return False
    if depth >= profile.depth_mm() - _OVERLAP_CLEARANCE_TOLERANCE_MM:
        return False
    profile_region = _profile_containment_region(profile)
    edge_region = _profile_containment_region(edge)
    if profile_region is None or edge_region is None or not profile_region.is_valid or not edge_region.is_valid:
        return False
    if profile_region.equals(edge_region):
        return isinstance(spec, ChamferSpec) or profile.side == (edge.side or "outside")
    if profile.side != "outside" or not isinstance(spec, ChamferSpec):
        return False
    envelope = edge_region.buffer(spec.width_mm, join_style="mitre")
    return (
        profile_region.contains(envelope)
        and profile_region.boundary.distance(envelope) > _OVERLAP_CLEARANCE_TOLERANCE_MM
    )


def _pocket_overlap_region(intent: RemovalIntent) -> BaseGeometry | None:
    if intent.hint_type != FeatureType.POCKET or _has_boundary_modifiers(intent):
        return None
    geometry = extract_shape_geometry(intent.shape, intent.bounds, intent.shape_geometry)
    region = pocket_region(intent.shape, geometry, intent.bounds.center, [i.bounds for i in intent.constraints.islands])
    if region is None:
        region = box(intent.bounds.x_min, intent.bounds.y_min, intent.bounds.x_max, intent.bounds.y_max)
    return region if region.is_valid else None


def _pocket_long_axis(intent: RemovalIntent) -> tuple[float, float] | None:
    region = _pocket_overlap_region(intent)
    if not isinstance(region, Polygon) or region.is_empty or not region.equals(region.convex_hull):
        return None
    rectangle = region.minimum_rotated_rectangle
    if not isinstance(rectangle, Polygon):
        return None
    corners = list(rectangle.exterior.coords)
    ax, ay = corners[1][0] - corners[0][0], corners[1][1] - corners[0][1]
    bx, by = corners[2][0] - corners[1][0], corners[2][1] - corners[1][1]
    length_a, length_b = math.hypot(ax, ay), math.hypot(bx, by)
    if length_a > length_b * _GROOVE_ASPECT_RATIO:
        return ax / length_a, ay / length_a
    if length_b > length_a * _GROOVE_ASPECT_RATIO:
        return bx / length_b, by / length_b
    return None


def _is_hole_through_pocket_floor(a: RemovalIntent, b: RemovalIntent) -> bool:
    match = _match_feature_types(a, b, FeatureType.POCKET, FeatureType.HOLE)
    if match is None:
        return False
    pocket, hole = match
    if pocket.depth_profile.mode != "constant" or hole.depth_profile.mode != "constant":
        return False
    if hole.shape.lower() != "circle" or _has_boundary_modifiers(hole):
        return False
    if pocket.shape.lower() not in ("rect", "polygon"):
        return False
    if pocket.shape.lower() == "polygon" and not pocket.shape_geometry.points:
        return False
    if pocket.rest is not None or pocket.depth_profile.z_top != 0 or hole.depth_profile.z_top != 0:
        return False
    if hole.depth_profile.z_bottom >= pocket.depth_profile.z_bottom - _OVERLAP_CLEARANCE_TOLERANCE_MM:
        return False
    region = _pocket_overlap_region(pocket)
    if region is None or region.is_empty:
        return False
    envelope = box(hole.bounds.x_min, hole.bounds.y_min, hole.bounds.x_max, hole.bounds.y_max)
    return region.contains(envelope) and region.boundary.distance(envelope) > _OVERLAP_CLEARANCE_TOLERANCE_MM


def _notch_owner_region(profile: RemovalIntent, relief: RemovalIntent, notch: BaseGeometry) -> BaseGeometry | None:
    if profile.face != relief.face or profile.shape.lower() != "polygon" or profile.depth_profile.z_top != 0:
        return None
    if profile.depth_profile.mode != "constant" or not math.isclose(
        profile.depth_mm(), relief.depth_mm(), rel_tol=0, abs_tol=_OVERLAP_CLEARANCE_TOLERANCE_MM
    ):
        return None
    region = _profile_containment_region(profile)
    if region is None or not region.is_valid or relief.dogbone_reference_point is None:
        return None
    reference = Point(relief.dogbone_reference_point)
    return region if region.contains(reference) or notch.contains(reference) else None


def _is_groove_on_profile_notch_relief(a: RemovalIntent, b: RemovalIntent, profiles: list[RemovalIntent]) -> bool:
    if not _match_same_type(a, b, FeatureType.POCKET):
        return False
    relief, groove = (a, b) if a.dogbone_corners is not None else (b, a)
    if relief.dogbone is None or relief.dogbone_corners is None or len(relief.dogbone_corners) != 2:
        return False
    if groove.dogbone_corners is not None or relief.dogbone_reference_point is None:
        return False
    if relief.shape.lower() != "rect" or groove.shape.lower() != "rect":
        return False
    if any(
        i.depth_profile.mode != "constant"
        or i.depth_profile.z_top != 0
        or i.rest is not None
        or i.constraints.islands
        or i.constraints.edge_treatment is not None
        for i in (relief, groove)
    ):
        return False
    if groove.depth_mm() <= 0 or groove.depth_mm() >= relief.depth_mm() - _OVERLAP_CLEARANCE_TOLERANCE_MM:
        return False
    notch = box(relief.bounds.x_min, relief.bounds.y_min, relief.bounds.x_max, relief.bounds.y_max)
    pocket = box(groove.bounds.x_min, groove.bounds.y_min, groove.bounds.x_max, groove.bounds.y_max)
    corners = LineString(relief.dogbone_corners)
    edges = list(notch.exterior.coords)
    if not any(
        corners.hausdorff_distance(LineString([p, q])) <= _OVERLAP_CLEARANCE_TOLERANCE_MM for p, q in pairwise(edges)
    ):
        return False
    for profile in profiles:
        region = _notch_owner_region(profile, relief, notch)
        if region is None:
            continue
        blank = box(profile.bounds.x_min, profile.bounds.y_min, profile.bounds.x_max, profile.bounds.y_max)
        envelope = blank.buffer(_OVERLAP_CLEARANCE_TOLERANCE_MM, join_style="mitre")
        if not envelope.covers(notch) or not envelope.covers(pocket):
            continue
        if notch.distance(blank.boundary) > _OVERLAP_CLEARANCE_TOLERANCE_MM:
            continue
        if region.buffer(-_OVERLAP_CLEARANCE_TOLERANCE_MM).intersects(notch):
            continue
        if region.boundary.buffer(_OVERLAP_CLEARANCE_TOLERANCE_MM).covers(corners):
            return True
    return False


def check_overlap(intents: list[RemovalIntent], *, engrave_tool_diameter_mm: float | None = None) -> ValidationResult:
    if engrave_tool_diameter_mm is not None and (
        not math.isfinite(engrave_tool_diameter_mm) or engrave_tool_diameter_mm <= 0
    ):
        raise ValueError(
            f"check_overlap: engrave_tool_diameter_mm must be finite and positive, got {engrave_tool_diameter_mm}"
        )
    result = ValidationResult()
    traces = [_engraving_trace(intent) if engrave_tool_diameter_mm is not None else None for intent in intents]
    pocket_regions = [_pocket_overlap_region(intent) for intent in intents]
    profiles = [i for i in intents if i.hint_type == FeatureType.PROFILE and i.side == "outside"]

    for i, intent_a in enumerate(intents):
        for j, intent_b in enumerate(intents[i + 1 :], start=i + 1):
            if intent_a.face != intent_b.face:
                continue
            if _regions_overlap(intent_a, intent_b):
                trace_a, trace_b = traces[i], traces[j]
                if (
                    engrave_tool_diameter_mm is not None
                    and trace_a is not None
                    and trace_b is not None
                    and trace_a.distance(trace_b) > engrave_tool_diameter_mm + _OVERLAP_CLEARANCE_TOLERANCE_MM
                ):
                    continue
                pocket_a, pocket_b = pocket_regions[i], pocket_regions[j]
                if (
                    pocket_a is not None
                    and pocket_b is not None
                    and pocket_a.distance(pocket_b) > _OVERLAP_CLEARANCE_TOLERANCE_MM
                ):
                    continue
                if _are_sibling_features(intent_a, intent_b):
                    continue
                if _is_nested_inside_profile(intent_a, intent_b):
                    continue
                if _is_compatible_profile_edge(intent_a, intent_b):
                    continue
                if _is_hole_through_pocket_floor(intent_a, intent_b) or _is_groove_on_profile_notch_relief(
                    intent_a, intent_b, profiles
                ):
                    continue
                if _are_perpendicular_pockets(intent_a, intent_b):
                    continue
                if _is_pocket_on_profile_edge(intent_a, intent_b):
                    continue
                if _is_inside_profile(intent_a, intent_b):
                    continue
                result.add_error(
                    f"Overlapping regions detected: {intent_a.region_id} and {intent_b.region_id}",
                    region_id=intent_a.region_id,
                    overlapping_with=intent_b.region_id,
                )

    return result


def check_back_face_support(intent: RemovalIntent) -> ValidationResult:
    result = ValidationResult()
    if intent.face != "back":
        return result

    if intent.hint_type not in BACK_FACE_FEATURE_TYPES:
        result.add_error(
            f"Back-face machining supports {BACK_FACE_FEATURE_TYPES} only, got '{intent.hint_type}'",
            region_id=intent.region_id,
            feature_type=intent.hint_type,
        )

    mode = intent.depth_profile.mode
    if mode not in BACK_FACE_DEPTH_MODES:
        result.add_error(
            f"Back-face machining does not support '{mode}' depth profiles (supported: {BACK_FACE_DEPTH_MODES})",
            region_id=intent.region_id,
            depth_mode=mode,
        )

    return result


def check_cross_face_web(
    intents: list[RemovalIntent],
    sheet_thickness_mm: float,
    min_web_mm: float,
) -> ValidationResult:
    result = ValidationResult()
    if min_web_mm <= 0.0:
        return result

    front = [i for i in intents if i.face == "front" and i.hint_type in WEB_CHECK_FEATURE_TYPES]
    back = [i for i in intents if i.face == "back" and i.hint_type in WEB_CHECK_FEATURE_TYPES]
    if not front or not back:
        return result

    budget_mm = sheet_thickness_mm - min_web_mm

    for front_intent in front:
        for back_intent in back:
            if not _bounds_overlap_xy(front_intent.bounds, back_intent.bounds):
                continue
            combined = front_intent.depth_mm() + back_intent.depth_mm()
            if combined > budget_mm + _WEB_TOLERANCE_MM:
                result.add_error(
                    f"Cross-face web breach: {front_intent.region_id} ({front_intent.depth_mm():.2f}mm front) "
                    f"and {back_intent.region_id} ({back_intent.depth_mm():.2f}mm back) leave "
                    f"{sheet_thickness_mm - combined:.2f}mm of material, below the {min_web_mm:.2f}mm minimum web",
                    region_id=front_intent.region_id,
                    overlapping_with=back_intent.region_id,
                    combined_depth_mm=combined,
                    min_web_mm=min_web_mm,
                )

    return result


def _bounds_overlap_xy(a: Bounds2D, b: Bounds2D) -> bool:
    x_overlap = not (a.x_max <= b.x_min or b.x_max <= a.x_min)
    y_overlap = not (a.y_max <= b.y_min or b.y_max <= a.y_min)
    return x_overlap and y_overlap


def check_heightfield(intent: RemovalIntent, sheet_thickness_mm: float) -> ValidationResult:
    result = ValidationResult()
    profile = intent.depth_profile
    if profile.mode != "heightfield":
        return result

    if profile.image_path is None:
        result.add_error(
            "Heightfield depth_profile missing image_path",
            region_id=intent.region_id,
        )
        return result

    from generators.area.heightfield_loader import load_heightfield, validate_square_pixels

    try:
        load_heightfield(profile.image_path)
    except (ValueError, OSError) as exc:
        result.add_error(
            f"Heightfield image load failed: {exc}",
            region_id=intent.region_id,
            image_path=profile.image_path,
        )
        return result

    width_mm = intent.bounds.width
    height_mm = intent.bounds.height
    try:
        validate_square_pixels(profile.image_path, width_mm, height_mm)
    except ValueError as exc:
        result.add_error(
            f"Heightfield square-pixel check failed: {exc}",
            region_id=intent.region_id,
        )

    depth = abs(profile.z_bottom - profile.z_top)
    if depth <= 0.0:
        result.add_error(
            f"Heightfield depth must be positive, got {depth:.2f}mm",
            region_id=intent.region_id,
        )
    elif depth > sheet_thickness_mm:
        result.add_error(
            f"Heightfield depth ({depth:.2f}mm) exceeds sheet thickness ({sheet_thickness_mm:.2f}mm)",
            region_id=intent.region_id,
            depth_mm=depth,
            sheet_thickness_mm=sheet_thickness_mm,
        )

    return result


def check_depth_feasibility(intent: RemovalIntent, sheet_thickness_mm: float) -> ValidationResult:
    result = ValidationResult()

    profile = intent.depth_profile
    if profile.z_top < profile.z_bottom:
        result.add_error(
            f"Invalid depth: z_top ({profile.z_top}) < z_bottom ({profile.z_bottom})",
            region_id=intent.region_id,
            z_top=profile.z_top,
            z_bottom=profile.z_bottom,
        )
        result.add_suggestion(
            f"Swap z_top and z_bottom values for region {intent.region_id}",
            region_id=intent.region_id,
        )

    depth = intent.depth_mm()
    if abs(profile.z_bottom) > sheet_thickness_mm:
        result.add_warning(
            f"Cutting deeper than material thickness: depth={depth:.2f}mm, thickness={sheet_thickness_mm:.2f}mm",
            region_id=intent.region_id,
            depth_mm=depth,
            sheet_thickness_mm=sheet_thickness_mm,
        )

    if 0 < depth < 0.5:
        result.add_suggestion(
            f"Very shallow cut detected ({depth:.2f}mm) - verify this is intentional",
            region_id=intent.region_id,
            depth_mm=depth,
        )

    return result


def check_toolability(intent: RemovalIntent, available_tools: list[dict[str, Any]] | None = None) -> ValidationResult:
    result = ValidationResult()

    bounds = intent.bounds
    width = bounds.width
    height = bounds.height

    if not available_tools:
        if width < 1.0 or height < 1.0:
            result.add_warning(
                f"Very small feature detected: {width:.2f}mm x {height:.2f}mm - may require micro tooling",
                region_id=intent.region_id,
                width_mm=width,
                height_mm=height,
            )

        return result

    min_feature_size = min(width, height)

    suitable_tools = [tool for tool in available_tools if tool.get("diameter_mm", float("inf")) <= min_feature_size]

    if not suitable_tools:
        result.add_error(
            f"No available tool can reach feature size {min_feature_size:.2f}mm",
            region_id=intent.region_id,
            min_feature_size_mm=min_feature_size,
        )
    elif len(suitable_tools) <= len(available_tools) // 2:
        result.add_suggestion(
            f"Limited tool options for feature size {min_feature_size:.2f}mm - consider using smaller endmill",
            region_id=intent.region_id,
            suitable_tool_count=len(suitable_tools),
        )

    return result


def _regions_overlap(a: RemovalIntent, b: RemovalIntent) -> bool:
    z_overlap = not (
        a.depth_profile.z_top <= b.depth_profile.z_bottom or b.depth_profile.z_top <= a.depth_profile.z_bottom
    )

    x_overlap = not (a.bounds.x_max <= b.bounds.x_min or b.bounds.x_max <= a.bounds.x_min)
    y_overlap = not (a.bounds.y_max <= b.bounds.y_min or b.bounds.y_max <= a.bounds.y_min)

    return z_overlap and x_overlap and y_overlap


def check_toolpath_clearance(
    intents: list[RemovalIntent],
    tool_diameter_mm: float,
) -> ValidationResult:
    result = ValidationResult()

    outside_profiles = [i for i in intents if i.side == "outside" and i.hint_type == "profile"]

    for i, a in enumerate(outside_profiles):
        for b in outside_profiles[i + 1 :]:
            if not _same_z_range(a, b):
                continue

            gap = _min_gap_between(a.bounds, b.bounds)

            if gap < 0:
                continue

            if gap < tool_diameter_mm - 0.001:
                result.add_error(
                    f"Insufficient clearance between {a.region_id} and {b.region_id}: "
                    f"{gap:.2f}mm gap, need {tool_diameter_mm:.2f}mm for tool",
                    region_id=a.region_id,
                    other_region_id=b.region_id,
                    gap_mm=gap,
                    required_mm=tool_diameter_mm,
                )

    return result


def _same_z_range(a: RemovalIntent, b: RemovalIntent) -> bool:
    return not (a.depth_profile.z_top <= b.depth_profile.z_bottom or b.depth_profile.z_top <= a.depth_profile.z_bottom)


def _min_gap_between(a: Bounds2D, b: Bounds2D) -> float:
    x_gap = max(a.x_min, b.x_min) - min(a.x_max, b.x_max)
    y_gap = max(a.y_min, b.y_min) - min(a.y_max, b.y_max)

    if x_gap >= 0 and y_gap >= 0:
        return math.hypot(x_gap, y_gap)
    elif x_gap >= 0:
        return x_gap
    elif y_gap >= 0:
        return y_gap
    else:
        return -1


def check_working_area_bounds(
    intents: list[RemovalIntent],
    working_width_mm: float,
    working_height_mm: float,
    tool_radius_mm: float = 0.0,
    tolerance_mm: float = 0.01,
) -> ValidationResult:
    result = ValidationResult()

    tool_diameter_mm = 2 * tool_radius_mm

    for intent in intents:
        bounds = intent.bounds
        side = intent.side or "on"

        offset = tool_diameter_mm if side == "outside" else 0.0

        min_x = bounds.x_min - offset
        min_y = bounds.y_min - offset
        max_x = bounds.x_max + offset
        max_y = bounds.y_max + offset

        if min_x < -tolerance_mm:
            result.add_error(
                f"Cutting edge extends {abs(min_x):.2f}mm into left margin zone",
                region_id=intent.region_id,
                boundary_exceeded="left",
                excess_mm=abs(min_x),
            )

        if min_y < -tolerance_mm:
            result.add_error(
                f"Cutting edge extends {abs(min_y):.2f}mm into bottom margin zone",
                region_id=intent.region_id,
                boundary_exceeded="bottom",
                excess_mm=abs(min_y),
            )

        if max_x > working_width_mm + tolerance_mm:
            excess = max_x - working_width_mm
            result.add_error(
                f"Cutting edge extends {excess:.2f}mm into right margin zone",
                region_id=intent.region_id,
                boundary_exceeded="right",
                excess_mm=excess,
            )

        if max_y > working_height_mm + tolerance_mm:
            excess = max_y - working_height_mm
            result.add_error(
                f"Cutting edge extends {excess:.2f}mm into top margin zone",
                region_id=intent.region_id,
                boundary_exceeded="top",
                excess_mm=excess,
            )

    return result
