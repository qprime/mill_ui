"""Validation functions for RemovalIntent records."""

from __future__ import annotations

from typing import Any

from skills.mill_ui.ir.removal_intent import RemovalIntent
from skills.mill_ui.validation.results import ValidationResult


def check_overlap(intents: list[RemovalIntent]) -> ValidationResult:
    """Check for overlapping RemovalIntent regions.

    Args:
        intents: List of RemovalIntent records to check

    Returns:
        ValidationResult with overlap errors detected
    """
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
    """Check if depth constraints are feasible.

    Args:
        intent: RemovalIntent to validate
        sheet_thickness_mm: Material thickness

    Returns:
        ValidationResult with depth errors/suggestions
    """
    result = ValidationResult()

    # Check z_top >= z_bottom
    if intent.z_top < intent.z_bottom:
        result.add_error(
            f"Invalid depth: z_top ({intent.z_top}) < z_bottom ({intent.z_bottom})",
            region_id=intent.region_id,
            z_top=intent.z_top,
            z_bottom=intent.z_bottom,
        )
        result.add_suggestion(
            f"Swap z_top and z_bottom values for region {intent.region_id}",
            region_id=intent.region_id,
        )

    # Check if cutting deeper than material thickness
    depth = intent.depth_mm()
    if abs(intent.z_bottom) > sheet_thickness_mm:
        result.add_warning(
            f"Cutting deeper than material thickness: depth={depth:.2f}mm, thickness={sheet_thickness_mm:.2f}mm",
            region_id=intent.region_id,
            depth_mm=depth,
            sheet_thickness_mm=sheet_thickness_mm,
        )

    # Suggest if depth is very shallow (< 0.5mm)
    if 0 < depth < 0.5:
        result.add_suggestion(
            f"Very shallow cut detected ({depth:.2f}mm) - verify this is intentional",
            region_id=intent.region_id,
            depth_mm=depth,
        )

    return result


def check_toolability(intent: RemovalIntent, available_tools: list[dict[str, Any]] | None = None) -> ValidationResult:
    """Check if region can be machined with available tools.

    Args:
        intent: RemovalIntent to validate
        available_tools: Optional list of tool specifications (diameter_mm, flutes, etc.)

    Returns:
        ValidationResult with toolability warnings/suggestions
    """
    result = ValidationResult()

    # Get bounds for all checks
    bounds = intent.bounds
    width = bounds.x_max - bounds.x_min
    height = bounds.y_max - bounds.y_min

    # If no tools specified, just do basic checks
    if not available_tools:
        # Check for very small features that may be hard to mill
        if width < 1.0 or height < 1.0:
            result.add_warning(
                f"Very small feature detected: {width:.2f}mm x {height:.2f}mm - may require micro tooling",
                region_id=intent.region_id,
                width_mm=width,
                height_mm=height,
            )

        return result

    # With tools specified, check if any tool can reach the feature
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
    """Check if two RemovalIntent regions overlap in XYZ space."""
    # Check Z overlap
    z_overlap = not (a.z_top <= b.z_bottom or b.z_top <= a.z_bottom)

    # Check XY overlap (2D bounding box)
    x_overlap = not (a.bounds.x_max <= b.bounds.x_min or b.bounds.x_max <= a.bounds.x_min)
    y_overlap = not (a.bounds.y_max <= b.bounds.y_min or b.bounds.y_max <= a.bounds.y_min)

    return z_overlap and x_overlap and y_overlap
