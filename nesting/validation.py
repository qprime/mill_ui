"""Validation for nesting results.

This module validates nesting solutions before CAM processing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .types import SheetLayout, NestingResult, NestedPart


@dataclass
class NestingValidationResult:
    """Result of nesting validation."""

    errors: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[dict[str, Any]] = field(default_factory=list)

    def add_error(self, message: str, **kwargs: Any) -> None:
        """Add an error."""
        self.errors.append({"message": message, **kwargs})

    def add_warning(self, message: str, **kwargs: Any) -> None:
        """Add a warning."""
        self.warnings.append({"message": message, **kwargs})

    @property
    def is_valid(self) -> bool:
        """True if no errors."""
        return len(self.errors) == 0

    def summary(self) -> str:
        """Get summary string."""
        if self.is_valid and not self.warnings:
            return "Validation passed"
        lines = []
        for err in self.errors:
            lines.append(f"ERROR: {err['message']}")
        for warn in self.warnings:
            lines.append(f"WARNING: {warn['message']}")
        return "\n".join(lines)


def _placements_overlap(p1: NestedPart, p2: NestedPart, gap: float = 0.0, epsilon: float = 0.01) -> bool:
    """Check if two placements overlap (with optional gap requirement).

    Args:
        p1, p2: NestedParts to check
        gap: Required gap between parts
        epsilon: Tolerance for floating point comparisons (default 0.01mm)

    Returns:
        True if placements overlap or violate gap requirement
    """
    # Get bounds (left, bottom, right, top)
    l1, b1, r1, t1 = p1.bounds
    l2, b2, r2, t2 = p2.bounds

    # Add gap to bounds for collision detection
    l1 -= gap / 2
    b1 -= gap / 2
    r1 += gap / 2
    t1 += gap / 2

    l2 -= gap / 2
    b2 -= gap / 2
    r2 += gap / 2
    t2 += gap / 2

    # Check if they overlap (with epsilon tolerance for floating point)
    # Two ranges [a, b] and [c, d] don't overlap if b <= c or d <= a
    # With epsilon: b <= c + epsilon or d <= a + epsilon
    overlap_x = not (r1 <= l2 + epsilon or r2 <= l1 + epsilon)
    overlap_y = not (t1 <= b2 + epsilon or t2 <= b1 + epsilon)

    return overlap_x and overlap_y


def _placement_in_bounds(p: NestedPart, sheet_width: float, sheet_height: float, margin: float) -> bool:
    """Check if placement is within sheet bounds (accounting for margin).

    Args:
        p: Placement to check
        sheet_width: Sheet width
        sheet_height: Sheet height
        margin: Required margin from edges

    Returns:
        True if placement is within bounds
    """
    l, b, r, t = p.bounds
    return (
        l >= margin
        and b >= margin
        and r <= sheet_width - margin
        and t <= sheet_height - margin
    )


def validate_sheet_layout(layout: SheetLayout) -> NestingValidationResult:
    """Validate a single sheet layout.

    Checks:
    - No overlapping placements
    - All placements within sheet bounds
    - Kerf gap is respected

    Args:
        layout: Sheet layout to validate

    Returns:
        Validation result
    """
    result = NestingValidationResult()
    spec = layout.sheet_spec

    # Check bounds
    for p in layout.placements:
        if not _placement_in_bounds(p, spec.width_mm, spec.height_mm, spec.margin_mm):
            result.add_error(
                f"Placement {p.part_spec.name}_{p.instance_id} extends outside sheet bounds",
                part_name=p.part_spec.name,
                instance_id=p.instance_id,
                bounds=p.bounds,
            )

    # Check overlaps
    placements = list(layout.placements)
    for i, p1 in enumerate(placements):
        for p2 in placements[i + 1:]:
            if _placements_overlap(p1, p2, gap=spec.gap_mm):
                result.add_error(
                    f"Placements overlap or violate part gap: "
                    f"{p1.part_spec.name}_{p1.instance_id} and {p2.part_spec.name}_{p2.instance_id}",
                    part1=f"{p1.part_spec.name}_{p1.instance_id}",
                    part2=f"{p2.part_spec.name}_{p2.instance_id}",
                )

    # Warn on low utilization
    if layout.utilization < 0.5:
        result.add_warning(
            f"Low material utilization: {layout.utilization_percent:.1f}%",
            utilization=layout.utilization,
        )

    return result


def validate_nesting_result(result: NestingResult) -> NestingValidationResult:
    """Validate complete nesting result.

    Args:
        result: Nesting result to validate

    Returns:
        Combined validation result
    """
    validation = NestingValidationResult()

    # Validate each sheet
    for sheet in result.sheets:
        sheet_result = validate_sheet_layout(sheet)
        validation.errors.extend(sheet_result.errors)
        validation.warnings.extend(sheet_result.warnings)

    # Warn about unplaced parts
    if result.unplaced_parts:
        for part in result.unplaced_parts:
            validation.add_warning(
                f"Could not place {part.quantity}x {part.name} ({part.width_mm}x{part.height_mm}mm)",
                part_name=part.name,
                quantity=part.quantity,
            )

    return validation


__all__ = [
    "NestingValidationResult",
    "validate_sheet_layout",
    "validate_nesting_result",
]
