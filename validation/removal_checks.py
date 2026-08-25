from __future__ import annotations

import math
from typing import Any

from core.constants import (
    BACK_FACE_DEPTH_MODES,
    BACK_FACE_FEATURE_TYPES,
    WEB_CHECK_FEATURE_TYPES,
    FeatureType,
)
from ir.removal_intent import BevelSpec, Bounds2D, ChamferSpec, RemovalIntent, RoundoverSpec
from validation.core import ValidationResult

_WEB_TOLERANCE_MM = 1e-6


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
        desired_included = spec.angle_deg * 2.0
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

    is_a_horizontal = a.bounds.width > a.bounds.height * 1.5
    is_a_vertical = a.bounds.height > a.bounds.width * 1.5
    is_b_horizontal = b.bounds.width > b.bounds.height * 1.5
    is_b_vertical = b.bounds.height > b.bounds.width * 1.5

    return (is_a_horizontal and is_b_vertical) or (is_a_vertical and is_b_horizontal)


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
    match = _match_feature_types(a, b, FeatureType.PROFILE, (FeatureType.HOLE, "drill", FeatureType.POCKET))
    if match is None:
        return False
    profile, contained = match

    return (
        contained.bounds.x_min >= profile.bounds.x_min
        and contained.bounds.x_max <= profile.bounds.x_max
        and contained.bounds.y_min >= profile.bounds.y_min
        and contained.bounds.y_max <= profile.bounds.y_max
    )


def check_overlap(intents: list[RemovalIntent]) -> ValidationResult:
    result = ValidationResult()

    for i, intent_a in enumerate(intents):
        for intent_b in intents[i + 1 :]:
            if intent_a.face != intent_b.face:
                continue
            if _regions_overlap(intent_a, intent_b):
                if _are_sibling_features(intent_a, intent_b):
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
        return min(x_gap, y_gap)
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
