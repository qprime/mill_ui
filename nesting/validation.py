from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from shapely.geometry import Polygon

from .types import NestedPart, NestingResult, SheetLayout


@dataclass
class NestingValidationResult:
    errors: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[dict[str, Any]] = field(default_factory=list)

    def add_error(self, message: str, **kwargs: Any) -> None:
        self.errors.append({"message": message, **kwargs})

    def add_warning(self, message: str, **kwargs: Any) -> None:
        self.warnings.append({"message": message, **kwargs})

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0

    def summary(self) -> str:
        if self.is_valid and not self.warnings:
            return "Validation passed"
        lines = []
        for err in self.errors:
            lines.append(f"ERROR: {err['message']}")
        for warn in self.warnings:
            lines.append(f"WARNING: {warn['message']}")
        return "\n".join(lines)


def _bounds_overlap(p1: NestedPart, p2: NestedPart, epsilon: float = 0.01) -> bool:
    l1, b1, r1, t1 = p1.bounds
    l2, b2, r2, t2 = p2.bounds

    overlap_x = not (r1 <= l2 + epsilon or r2 <= l1 + epsilon)
    overlap_y = not (t1 <= b2 + epsilon or t2 <= b1 + epsilon)

    return overlap_x and overlap_y


def _get_overlap_location(p1: NestedPart, p2: NestedPart) -> tuple[float, float] | None:
    poly1 = Polygon(p1.get_geometry_points())
    poly2 = Polygon(p2.get_geometry_points())

    if not poly1.is_valid or not poly2.is_valid:
        return None

    intersection = poly1.intersection(poly2)
    if intersection.is_empty:
        return None

    centroid = intersection.centroid
    return (round(centroid.x, 2), round(centroid.y, 2))


def _geometries_overlap(p1: NestedPart, p2: NestedPart, epsilon: float = 0.01) -> bool:
    if not _bounds_overlap(p1, p2, epsilon):
        return False

    poly1 = Polygon(p1.get_geometry_points())
    poly2 = Polygon(p2.get_geometry_points())

    if not poly1.is_valid or not poly2.is_valid:
        return _bounds_overlap(p1, p2, epsilon)

    intersection = poly1.intersection(poly2)
    if intersection.is_empty:
        return False

    return intersection.area > epsilon * epsilon


def _placement_in_bounds(p: NestedPart, sheet_width: float, sheet_height: float, margin: float) -> bool:
    left, b, r, t = p.bounds
    return left >= margin and b >= margin and r <= sheet_width - margin and t <= sheet_height - margin


def validate_sheet_layout(layout: SheetLayout) -> NestingValidationResult:
    result = NestingValidationResult()
    spec = layout.sheet_spec

    for p in layout.placements:
        if not _placement_in_bounds(p, spec.width_mm, spec.height_mm, spec.margin_mm):
            result.add_error(
                f"Placement {p.part_spec.name}_{p.instance_id} extends outside sheet bounds",
                part_name=p.part_spec.name,
                instance_id=p.instance_id,
                bounds=p.bounds,
            )

    placements = list(layout.placements)
    for i, p1 in enumerate(placements):
        for p2 in placements[i + 1 :]:
            if _geometries_overlap(p1, p2):
                overlap_loc = _get_overlap_location(p1, p2)
                loc_str = f" at ({overlap_loc[0]}, {overlap_loc[1]})mm" if overlap_loc else ""
                result.add_error(
                    f"Part geometries overlap: "
                    f"{p1.part_spec.name}_{p1.instance_id} and {p2.part_spec.name}_{p2.instance_id}{loc_str}",
                    part1=f"{p1.part_spec.name}_{p1.instance_id}",
                    part2=f"{p2.part_spec.name}_{p2.instance_id}",
                    overlap_location=overlap_loc,
                )

    if layout.utilization < 0.5:
        result.add_warning(
            f"Low material utilization: {layout.utilization_percent:.1f}%",
            utilization=layout.utilization,
        )

    return result


def validate_nesting_result(result: NestingResult) -> NestingValidationResult:
    validation = NestingValidationResult()

    for sheet in result.sheets:
        sheet_result = validate_sheet_layout(sheet)
        validation.errors.extend(sheet_result.errors)
        validation.warnings.extend(sheet_result.warnings)

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
    "validate_nesting_result",
    "validate_sheet_layout",
]
