from __future__ import annotations

from typing import TYPE_CHECKING

from core.geometry import clip_line_to_domain
from domains.transforms import local_to_sheet_batch
from generators.base import (
    GeneratorResult,
    generate_shape_id,
    validate_domain_for_generation,
)
from generators.params.area import GridLinesParams
from generators.utils import get_local_bounds
from layout_ast.layout import Feature, Geometry, Item, Placement

if TYPE_CHECKING:
    from domains import Domain


def grid_lines_generator(
    domain: Domain,
    params: GridLinesParams,
    *,
    allow_empty: bool = False,
    shape_id_prefix: str = "grid_lines",
) -> GeneratorResult:
    params.validate()

    if not validate_domain_for_generation(
        domain,
        min_area_mm2=1.0,
        allow_empty=allow_empty,
        generator_name="GridLinesGenerator",
    ):
        return []

    local_bounds = get_local_bounds(domain)
    local_x_min = local_bounds["x_min"]
    local_x_max = local_bounds["x_max"]
    local_y_min = local_bounds["y_min"]
    local_y_max = local_bounds["y_max"]

    major_spacing = params.get_major_spacing()
    minor_spacing = params.get_minor_spacing() if params.minor_lines else None

    items: list[Item] = []
    item_index = 0

    def is_major_line(pos: float, origin: float) -> bool:
        offset = abs(pos - origin)
        return abs(offset % major_spacing) < 0.001 or abs(offset % major_spacing - major_spacing) < 0.001

    def add_line(
        start_local: tuple[float, float],
        end_local: tuple[float, float],
        suffix: str,
    ) -> None:
        nonlocal item_index
        sheet_points = local_to_sheet_batch([start_local, end_local], domain)
        sheet_start, sheet_end = sheet_points[0], sheet_points[1]

        clipped = clip_line_to_domain(sheet_start, sheet_end, domain)

        for seg_start, seg_end in clipped:
            item = _create_line_item(
                start=seg_start,
                end=seg_end,
                depth_mm=params.depth_mm,
                shape_id=generate_shape_id(shape_id_prefix, item_index, suffix),
            )
            items.append(item)
            item_index += 1

    x_origin = local_x_min
    y_origin = local_y_min

    spacing = minor_spacing if params.minor_lines else major_spacing

    x = x_origin + spacing
    while x < local_x_max - 0.001:
        is_major = is_major_line(x, x_origin)
        if is_major or params.minor_lines:
            add_line(
                (x, local_y_min),
                (x, local_y_max),
                "vertical",
            )
        x += spacing

    y = y_origin + spacing
    while y < local_y_max - 0.001:
        is_major = is_major_line(y, y_origin)
        if is_major or params.minor_lines:
            add_line(
                (local_x_min, y),
                (local_x_max, y),
                "horizontal",
            )
        y += spacing

    if not items and not allow_empty:
        raise ValueError(
            "GridLinesGenerator: Could not generate any grid lines. "
            "Domain may be too small for the specified spacing."
        )

    return items


def _create_line_item(
    start: tuple[float, float],
    end: tuple[float, float],
    depth_mm: float,
    shape_id: str,
) -> Item:
    cx = (start[0] + end[0]) / 2
    cy = (start[1] + end[1]) / 2

    geometry_data = {
        "start": [start[0] - cx, start[1] - cy],
        "end": [end[0] - cx, end[1] - cy],
        "width_mm": 0.5,
    }

    return Item(
        kind="shape",
        type="Line",
        geometry=Geometry(data=geometry_data),
        placement=Placement(center_xy_mm=(cx, cy)),
        feature=Feature(
            type="engrave",
            depth_mm=depth_mm,
        ),
        shape_id=shape_id,
    )


__all__ = ["grid_lines_generator"]
