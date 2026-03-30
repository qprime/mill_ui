from __future__ import annotations

from typing import TYPE_CHECKING

from generators.core import (
    GeneratorResult,
    GeneratorSkipError,
    validate_domain_for_generation,
)
from generators.measurement_helpers import create_engraved_line
from generators.params.area import GridLinesParams
from generators.utils import get_local_bounds, is_major_tick
from layout_ast.layout import Item

if TYPE_CHECKING:
    from domains import Domain


def grid_lines_generator(
    domain: Domain,
    params: GridLinesParams,
    *,
    allow_empty: bool = False,
    shape_id_prefix: str = "grid_lines",
) -> GeneratorResult:
    if not validate_domain_for_generation(
        domain,
        min_area_mm2=1.0,
        allow_empty=allow_empty,
        generator_name="GridLinesGenerator",
    ):
        return []

    local_bounds = get_local_bounds(domain)
    local_x_min = local_bounds.x_min
    local_x_max = local_bounds.x_max
    local_y_min = local_bounds.y_min
    local_y_max = local_bounds.y_max

    major_spacing = params.get_major_spacing()
    minor_spacing = params.get_minor_spacing() if params.minor_lines else None

    items: list[Item] = []
    item_index = 0

    x_origin = local_x_min
    y_origin = local_y_min

    spacing = minor_spacing if params.minor_lines else major_spacing
    if spacing is None:
        raise ValueError("Grid line spacing resolved to None — check major/minor spacing parameters")

    x = x_origin + spacing
    while x < local_x_max - 0.001:
        is_major = is_major_tick(x, x_origin, major_spacing)
        if is_major or params.minor_lines:
            new_items = create_engraved_line(
                (x, local_y_min),
                (x, local_y_max),
                "vertical",
                domain,
                params.depth_mm,
                shape_id_prefix,
                item_index,
            )
            items.extend(new_items)
            item_index += len(new_items)
        x += spacing

    y = y_origin + spacing
    while y < local_y_max - 0.001:
        is_major = is_major_tick(y, y_origin, major_spacing)
        if is_major or params.minor_lines:
            new_items = create_engraved_line(
                (local_x_min, y),
                (local_x_max, y),
                "horizontal",
                domain,
                params.depth_mm,
                shape_id_prefix,
                item_index,
            )
            items.extend(new_items)
            item_index += len(new_items)
        y += spacing

    if not items and not allow_empty:
        raise GeneratorSkipError(
            "GridLinesGenerator: Could not generate any grid lines. Domain may be too small for the specified spacing."
        )

    return items


__all__ = ["grid_lines_generator"]
