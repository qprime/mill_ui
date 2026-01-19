
from __future__ import annotations

import math
from typing import Any

from ir.removal_intent import RemovalIntent
from validation.results import ValidationResult


def check_depth_profile(
    intent: RemovalIntent,
    sheet_thickness_mm: float,
    available_v_angles: list[float] | None = None,
) -> ValidationResult:
    """Validate depth profile semantics.

    Checks:
    - V-carve angle must match available tooling (if specified)
    - Gradient depth must not exceed sheet thickness
    - Bevel/V-carve inner depth must be reachable with specified angle

    Args:
        intent: The RemovalIntent to validate
        sheet_thickness_mm: Material thickness for depth validation
        available_v_angles: List of available V-bit angles (e.g., [60.0, 90.0, 120.0]).
            If None, skips V-bit availability check.

    Returns:
        ValidationResult with any issues found
    """
    result = ValidationResult()
    profile = intent.depth_profile

    # Check gradient depth doesn't exceed sheet thickness
    if profile.mode == "linear_gradient":
        if abs(profile.z_bottom) > sheet_thickness_mm:
            result.add_error(
                f"Gradient depth ({abs(profile.z_bottom):.2f}mm) exceeds sheet thickness ({sheet_thickness_mm:.2f}mm)",
                region_id=intent.region_id,
                gradient_depth_mm=abs(profile.z_bottom),
                sheet_thickness_mm=sheet_thickness_mm,
            )

    # Check V-carve angle availability
    if profile.mode == "v_carve":
        v_angle = profile.v_angle_deg

        # Check if V-bit angle is available
        if available_v_angles is not None:
            # Allow 1 degree tolerance for matching
            matching = [a for a in available_v_angles if abs(a - v_angle) < 1.0]
            if not matching:
                result.add_error(
                    f"V-carve requires {v_angle:.0f}° V-bit, but none available. "
                    f"Available angles: {available_v_angles}",
                    region_id=intent.region_id,
                    required_angle=v_angle,
                    available_angles=available_v_angles,
                )

        # Check V-carve depth is achievable
        # For a V-bit, max depth at a point depends on feature width
        # This is a basic check - actual depth depends on geometry
        if abs(profile.z_bottom) > sheet_thickness_mm:
            result.add_warning(
                f"V-carve depth ({abs(profile.z_bottom):.2f}mm) may exceed material",
                region_id=intent.region_id,
                v_carve_depth_mm=abs(profile.z_bottom),
                sheet_thickness_mm=sheet_thickness_mm,
            )

    # Check for bevel metadata (from chamfer/bevel features)
    bevel_data = intent.metadata.get("bevel")
    if bevel_data:
        bevel_width = bevel_data.get("width_mm", 0)
        bevel_angle = bevel_data.get("angle_deg", 45)
        inner_depth = bevel_data.get("inner_depth_mm", 0)

        # Calculate expected depth from width and angle
        # For a 45° bevel, depth = width. For other angles: depth = width * tan(angle)
        if bevel_angle > 0 and bevel_angle < 90:
            expected_depth = bevel_width * math.tan(math.radians(bevel_angle))
            # Allow some tolerance
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


def check_overlap(intents: list[RemovalIntent]) -> ValidationResult:
    result = ValidationResult()

    for i, intent_a in enumerate(intents):
        for intent_b in intents[i + 1 :]:
            if _regions_overlap(intent_a, intent_b):
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
    width = bounds.x_max - bounds.x_min
    height = bounds.y_max - bounds.y_min


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

    suitable_tools = [
        tool for tool in available_tools if tool.get("diameter_mm", float("inf")) <= min_feature_size
    ]

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

    z_overlap = not (a.depth_profile.z_top <= b.depth_profile.z_bottom or b.depth_profile.z_top <= a.depth_profile.z_bottom)


    x_overlap = not (a.bounds.x_max <= b.bounds.x_min or b.bounds.x_max <= a.bounds.x_min)
    y_overlap = not (a.bounds.y_max <= b.bounds.y_min or b.bounds.y_max <= a.bounds.y_min)

    return z_overlap and x_overlap and y_overlap
