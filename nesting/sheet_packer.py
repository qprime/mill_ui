
from __future__ import annotations

from enum import Enum
from typing import Any

from .types import PartSpec, SheetSpec, NestedPart, SheetLayout, NestingResult
from .guillotine import guillotine_pack
from .maxrects import maxrects_pack, MaxRectsHeuristic


class PackingAlgorithm(Enum):
    GUILLOTINE = "guillotine"
    MAXRECTS = "maxrects"


DEFAULT_ALGORITHM = PackingAlgorithm.MAXRECTS


def _expand_parts(parts: list[PartSpec]) -> list[tuple[PartSpec, int]]:
    expanded = []
    for part in parts:
        for i in range(part.quantity):
            expanded.append((part, i))
    return expanded


def _part_fits_on_sheet(part: PartSpec, sheet: SheetSpec) -> bool:
    usable_w = sheet.usable_width_mm
    usable_h = sheet.usable_height_mm

    if part.width_mm <= usable_w and part.height_mm <= usable_h:
        return True

    if part.allow_rotation:
        if part.height_mm <= usable_w and part.width_mm <= usable_h:
            return True

    return False


def _pack_single_sheet(
    parts_input: list[tuple[float, float, bool, Any]],
    bin_width: float,
    bin_height: float,
    gap: float,
    algorithm: PackingAlgorithm,
) -> list[Any]:
    if algorithm == PackingAlgorithm.GUILLOTINE:
        return guillotine_pack(
            parts=parts_input,
            bin_width=bin_width,
            bin_height=bin_height,
            gap=gap,
            sort_by_area=False,
        )
    elif algorithm == PackingAlgorithm.MAXRECTS:
        return maxrects_pack(
            parts=parts_input,
            bin_width=bin_width,
            bin_height=bin_height,
            gap=gap,
            sort_by_area=False,
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

    if isinstance(algorithm, str):
        algorithm = PackingAlgorithm(algorithm)


    too_large = []
    valid_parts = []
    for part in parts:
        if part.quantity == 0:
            continue
        if _part_fits_on_sheet(part, sheet_spec):
            valid_parts.append(part)
        else:
            too_large.append(part)


    expanded = _expand_parts(valid_parts)

    if not expanded:
        return NestingResult(sheets=(), unplaced_parts=tuple(too_large))


    expanded.sort(key=lambda x: x[0].area_mm2, reverse=True)


    remaining = list(expanded)
    sheets = []
    sheet_index = 0

    while remaining and (max_sheets is None or sheet_index < max_sheets):


        pack_input = [
            (part.width_mm, part.height_mm, part.allow_rotation, (part, inst_id))
            for part, inst_id in remaining
        ]


        placements = _pack_single_sheet(
            parts_input=pack_input,
            bin_width=sheet_spec.usable_width_mm,
            bin_height=sheet_spec.usable_height_mm,
            gap=0.0,
            algorithm=algorithm,
        )

        if not placements:

            break


        sheet_placements = []
        placed_keys = set()

        for p in placements:
            part_spec, inst_id = p.metadata

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


        sheet_layout = SheetLayout(
            sheet_spec=sheet_spec,
            placements=tuple(sheet_placements),
            sheet_index=sheet_index,
        )
        sheets.append(sheet_layout)


        remaining = [
            (part, inst_id)
            for part, inst_id in remaining
            if (id(part), inst_id) not in placed_keys
        ]

        sheet_index += 1


    unplaced = list(too_large)

    remaining_by_spec = {}
    for part, inst_id in remaining:
        key = id(part)
        if key not in remaining_by_spec:
            remaining_by_spec[key] = (part, 0)
        spec, count = remaining_by_spec[key]
        remaining_by_spec[key] = (spec, count + 1)

    for spec, count in remaining_by_spec.values():
        if count > 0:

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
