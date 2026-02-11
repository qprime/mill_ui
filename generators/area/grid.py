
from __future__ import annotations

from typing import TYPE_CHECKING

from core.geometry import clip_line_to_domain
from domains.transforms import local_to_sheet_batch
from generators.base import (
    GeneratorResult,
    GridParams,
    generate_shape_id,
    validate_domain_for_generation,
)
from generators.utils import create_line_item, get_local_bounds
from layout_ast.layout import Item

if TYPE_CHECKING:
    from domains import Domain


def grid_generator(
    domain: Domain,
    params: GridParams,
    *,
    allow_empty: bool = False,
    shape_id_prefix: str = "grid",
) -> GeneratorResult:

    params.validate()


    if not validate_domain_for_generation(
        domain,
        min_area_mm2=1.0,
        allow_empty=allow_empty,
        generator_name="GridGenerator",
    ):
        return []


    local_bounds = get_local_bounds(domain)
    local_x_min = local_bounds["x_min"]
    local_x_max = local_bounds["x_max"]
    local_y_min = local_bounds["y_min"]
    local_y_max = local_bounds["y_max"]


    domain_width = local_x_max - local_x_min
    domain_height = local_y_max - local_y_min

    if domain_width < params.spacing_x_mm and domain_height < params.spacing_y_mm:
        if allow_empty:
            return []
        raise ValueError(
            f"GridGenerator: Domain size ({domain_width:.1f}mm x {domain_height:.1f}mm) "
            f"is smaller than grid spacing ({params.spacing_x_mm}mm x {params.spacing_y_mm}mm). "
            f"Reduce spacing or use a larger domain."
        )

    items: list[Item] = []
    item_index = 0


    x_start = params.offset_x_mm

    while x_start > local_x_min:
        x_start -= params.spacing_x_mm

    x = x_start
    while x <= local_x_max:

        local_start = (x, local_y_min - 10)
        local_end = (x, local_y_max + 10)


        sheet_points = local_to_sheet_batch([local_start, local_end], domain)
        sheet_start, sheet_end = sheet_points[0], sheet_points[1]


        clipped = clip_line_to_domain(sheet_start, sheet_end, domain)

        for seg_start, seg_end in clipped:
            item = create_line_item(
                start=seg_start,
                end=seg_end,
                depth_mm=params.depth_mm,
                shape_id=generate_shape_id(shape_id_prefix, item_index, "v"),
                line_width_mm=params.line_width_mm,
            )
            items.append(item)
            item_index += 1

        x += params.spacing_x_mm


    y_start = params.offset_y_mm
    while y_start > local_y_min:
        y_start -= params.spacing_y_mm

    y = y_start
    while y <= local_y_max:

        local_start = (local_x_min - 10, y)
        local_end = (local_x_max + 10, y)


        sheet_points = local_to_sheet_batch([local_start, local_end], domain)
        sheet_start, sheet_end = sheet_points[0], sheet_points[1]


        clipped = clip_line_to_domain(sheet_start, sheet_end, domain)

        for seg_start, seg_end in clipped:
            item = create_line_item(
                start=seg_start,
                end=seg_end,
                depth_mm=params.depth_mm,
                shape_id=generate_shape_id(shape_id_prefix, item_index, "h"),
                line_width_mm=params.line_width_mm,
            )
            items.append(item)
            item_index += 1

        y += params.spacing_y_mm

    if not items and not allow_empty:
        raise ValueError(
            f"GridGenerator: Could not generate any grid lines for domain. "
            f"Domain may be too small or grid parameters incompatible."
        )

    return items


__all__ = ["grid_generator"]
