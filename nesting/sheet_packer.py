"""Multi-sheet packing with selectable algorithm.

This module coordinates packing parts across multiple sheets when
a single sheet cannot contain all requested parts.

Algorithm:
1. Expand PartSpecs by quantity into individual items
2. Sort items by area (largest first)
3. Pack items onto sheets using selected algorithm
4. When current sheet is full, start a new sheet
5. Track any parts that couldn't be placed

Supported algorithms:
- guillotine: Guillotine bin packing with BSSF heuristic (faster, simpler)
- maxrects: MaxRects with Best Area Fit heuristic (better utilization)
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from .types import PartSpec, SheetSpec, NestedPart, SheetLayout, NestingResult
from .guillotine import guillotine_pack
from .maxrects import maxrects_pack, MaxRectsHeuristic


class PackingAlgorithm(Enum):
    """Available packing algorithms."""
    GUILLOTINE = "guillotine"
    MAXRECTS = "maxrects"


# Default algorithm - MaxRects for better utilization
DEFAULT_ALGORITHM = PackingAlgorithm.MAXRECTS


def _expand_parts(parts: list[PartSpec]) -> list[tuple[PartSpec, int]]:
    """Expand parts by quantity into individual items.

    Args:
        parts: List of PartSpecs with quantities

    Returns:
        List of (PartSpec, instance_id) tuples
    """
    expanded = []
    for part in parts:
        for i in range(part.quantity):
            expanded.append((part, i))
    return expanded


def _part_fits_on_sheet(part: PartSpec, sheet: SheetSpec) -> bool:
    """Check if a part can possibly fit on a sheet.

    Args:
        part: Part specification
        sheet: Sheet specification

    Returns:
        True if part could fit (with or without rotation)
    """
    usable_w = sheet.usable_width_mm
    usable_h = sheet.usable_height_mm
    gap = sheet.gap_mm

    # Check normal orientation (part + gap must fit)
    if part.width_mm + gap <= usable_w and part.height_mm + gap <= usable_h:
        return True

    # Check rotated orientation (if allowed)
    if part.allow_rotation:
        if part.height_mm + gap <= usable_w and part.width_mm + gap <= usable_h:
            return True

    return False


def _pack_single_sheet(
    parts_input: list[tuple[float, float, bool, Any]],
    bin_width: float,
    bin_height: float,
    gap: float,
    algorithm: PackingAlgorithm,
) -> list[Any]:
    """Pack parts onto a single sheet using selected algorithm.

    Args:
        parts_input: List of (width, height, allow_rotation, metadata)
        bin_width: Usable bin width
        bin_height: Usable bin height
        gap: Required gap between parts
        algorithm: Packing algorithm to use

    Returns:
        List of placement results
    """
    if algorithm == PackingAlgorithm.GUILLOTINE:
        return guillotine_pack(
            parts=parts_input,
            bin_width=bin_width,
            bin_height=bin_height,
            gap=gap,
            sort_by_area=False,  # Already sorted
        )
    elif algorithm == PackingAlgorithm.MAXRECTS:
        return maxrects_pack(
            parts=parts_input,
            bin_width=bin_width,
            bin_height=bin_height,
            gap=gap,
            sort_by_area=False,  # Already sorted
            heuristic=MaxRectsHeuristic.CONTACT_POINT,
        )
    else:
        raise ValueError(f"Unknown algorithm: {algorithm}")


def pack_sheets(
    parts: list[PartSpec],
    sheet_spec: SheetSpec,
    max_sheets: int | None = None,
    algorithm: PackingAlgorithm | str = DEFAULT_ALGORITHM,
) -> NestingResult:
    """Pack all parts across minimum number of sheets.

    Args:
        parts: List of PartSpecs with quantities
        sheet_spec: Sheet specification for all sheets
        max_sheets: Maximum number of sheets to use (None = unlimited)
        algorithm: Packing algorithm ("guillotine" or "maxrects")

    Returns:
        NestingResult with all sheet layouts and unplaced parts
    """
    # Convert string to enum if needed
    if isinstance(algorithm, str):
        algorithm = PackingAlgorithm(algorithm)

    # First, identify parts that are too large for any sheet
    too_large = []
    valid_parts = []
    for part in parts:
        if part.quantity == 0:
            continue
        if _part_fits_on_sheet(part, sheet_spec):
            valid_parts.append(part)
        else:
            too_large.append(part)

    # Expand valid parts by quantity
    expanded = _expand_parts(valid_parts)

    if not expanded:
        return NestingResult(sheets=(), unplaced_parts=tuple(too_large))

    # Sort by area (largest first) for better packing
    expanded.sort(key=lambda x: x[0].area_mm2, reverse=True)

    # Track which items have been placed
    remaining = list(expanded)
    sheets = []
    sheet_index = 0

    while remaining and (max_sheets is None or sheet_index < max_sheets):
        # Prepare parts for packer
        # Format: (width, height, allow_rotation, metadata)
        # Metadata = (part_spec, instance_id)
        pack_input = [
            (part.width_mm, part.height_mm, part.allow_rotation, (part, inst_id))
            for part, inst_id in remaining
        ]

        # Pack onto one sheet
        placements = _pack_single_sheet(
            parts_input=pack_input,
            bin_width=sheet_spec.usable_width_mm,
            bin_height=sheet_spec.usable_height_mm,
            gap=sheet_spec.gap_mm,
            algorithm=algorithm,
        )

        if not placements:
            # Nothing fits on this sheet - shouldn't happen if parts fit individually
            break

        # Convert placements to NestedPart instances
        # Adjust coordinates from usable area to sheet coordinates
        sheet_placements = []
        placed_keys = set()

        for p in placements:
            part_spec, inst_id = p.metadata
            # Offset from usable area origin (margin) to sheet origin
            sheet_x = p.x + sheet_spec.margin_mm
            sheet_y = p.y + sheet_spec.margin_mm

            sheet_placements.append(
                NestedPart(
                    part_spec=part_spec,
                    x_mm=sheet_x,
                    y_mm=sheet_y,
                    rotated=p.rotated,
                    instance_id=inst_id,
                )
            )
            placed_keys.add((id(part_spec), inst_id))

        # Create sheet layout
        sheet_layout = SheetLayout(
            sheet_spec=sheet_spec,
            placements=tuple(sheet_placements),
            sheet_index=sheet_index,
        )
        sheets.append(sheet_layout)

        # Remove placed items from remaining
        remaining = [
            (part, inst_id)
            for part, inst_id in remaining
            if (id(part), inst_id) not in placed_keys
        ]

        sheet_index += 1

    # Any remaining items plus too-large items are unplaced
    unplaced = list(too_large)
    # Collapse remaining expanded items back to PartSpecs with adjusted quantities
    remaining_by_spec = {}
    for part, inst_id in remaining:
        key = id(part)
        if key not in remaining_by_spec:
            remaining_by_spec[key] = (part, 0)
        spec, count = remaining_by_spec[key]
        remaining_by_spec[key] = (spec, count + 1)

    for spec, count in remaining_by_spec.values():
        if count > 0:
            # Create a new PartSpec with remaining quantity
            unplaced.append(
                PartSpec(
                    name=spec.name,
                    width_mm=spec.width_mm,
                    height_mm=spec.height_mm,
                    quantity=count,
                    template=spec.template,
                    template_params=spec.template_params,
                    allow_rotation=spec.allow_rotation,
                )
            )

    return NestingResult(
        sheets=tuple(sheets),
        unplaced_parts=tuple(unplaced),
    )


__all__ = ["pack_sheets", "PackingAlgorithm", "DEFAULT_ALGORITHM"]
