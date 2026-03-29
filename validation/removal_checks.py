from __future__ import annotations

import math
from typing import Any

from core.constants import FeatureType
from ir.removal_intent import BevelSpec, Bounds2D, ChamferSpec, RemovalIntent, RoundoverSpec
from validation.core import ValidationResult


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
        assert v_angle is not None

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


def _is_hole_inside_profile(a: RemovalIntent, b: RemovalIntent) -> bool:
    match = _match_feature_types(a, b, FeatureType.PROFILE, (FeatureType.HOLE, "drill"))
    if match is None:
        return False
    profile, hole = match

    return (
        hole.bounds.x_min >= profile.bounds.x_min
        and hole.bounds.x_max <= profile.bounds.x_max
        and hole.bounds.y_min >= profile.bounds.y_min
        and hole.bounds.y_max <= profile.bounds.y_max
    )


def check_overlap(intents: list[RemovalIntent]) -> ValidationResult:
    result = ValidationResult()

    for i, intent_a in enumerate(intents):
        for intent_b in intents[i + 1 :]:
            if _regions_overlap(intent_a, intent_b):
                if _are_perpendicular_pockets(intent_a, intent_b):
                    continue
                if _is_pocket_on_profile_edge(intent_a, intent_b):
                    continue
                if _is_hole_inside_profile(intent_a, intent_b):
                    continue
                result.add_error(
                    f"Overlapping regions detected: {intent_a.region_id} and {intent_b.region_id}",
                    region_id=intent_a.region_id,
                    overlapping_with=intent_b.region_id,
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
