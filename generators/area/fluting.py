from __future__ import annotations

import math
from typing import TYPE_CHECKING

from core.geometry import clip_line_to_domain
from domains.transforms import local_to_sheet_batch
from generators.core import (
    GeneratorResult,
    GeneratorSkipError,
    generate_shape_id,
    validate_domain_for_generation,
)
from generators.params.area import FlutingParams
from generators.utils import get_local_bounds
from layout_ast.layout import Feature, Geometry, Item, Placement

if TYPE_CHECKING:
    from domains import Domain


def fluting_generator(
    domain: Domain,
    params: FlutingParams,
    *,
    allow_empty: bool = False,
    shape_id_prefix: str = "fluting",
) -> GeneratorResult:
    if not validate_domain_for_generation(
        domain,
        min_area_mm2=1.0,
        allow_empty=allow_empty,
        generator_name="FlutingGenerator",
    ):
        return []

    local_bounds = get_local_bounds(domain)
    lx_min = local_bounds.x_min + params.inset_mm
    lx_max = local_bounds.x_max - params.inset_mm
    ly_min = local_bounds.y_min + params.inset_mm
    ly_max = local_bounds.y_max - params.inset_mm

    if lx_max <= lx_min or ly_max <= ly_min:
        if allow_empty:
            return []
        raise GeneratorSkipError("FlutingGenerator: inset leaves no room for grooves.")

    angle_rad = math.radians(params.angle_deg)
    dx = math.cos(angle_rad)
    dy = math.sin(angle_rad)
    px = -dy
    py = dx

    cx = (lx_min + lx_max) / 2
    cy = (ly_min + ly_max) / 2
    w = lx_max - lx_min
    h = ly_max - ly_min
    diagonal = math.sqrt(w**2 + h**2)
    extent = diagonal + params.spacing_mm

    half_extent = extent / 2
    num_lines_per_side = math.ceil(half_extent / params.spacing_mm)

    items: list[Item] = []
    item_index = 0

    for i in range(-num_lines_per_side, num_lines_per_side + 1):
        offset = i * params.spacing_mm
        line_cx = cx + offset * px
        line_cy = cy + offset * py

        start_local = (line_cx - extent * dx, line_cy - extent * dy)
        end_local = (line_cx + extent * dx, line_cy + extent * dy)

        sheet_points = local_to_sheet_batch([start_local, end_local], domain)
        sheet_start, sheet_end = sheet_points[0], sheet_points[1]

        clipped = clip_line_to_domain(sheet_start, sheet_end, domain)

        for seg_start, seg_end in clipped:
            scx = (seg_start[0] + seg_end[0]) / 2
            scy = (seg_start[1] + seg_end[1]) / 2

            geometry_data = {
                "start": [seg_start[0] - scx, seg_start[1] - scy],
                "end": [seg_end[0] - scx, seg_end[1] - scy],
                "width_mm": 0.5,
            }

            item = Item(
                kind="shape",
                type="Line",
                geometry=Geometry(data=geometry_data),
                placement=Placement(center_xy_mm=(scx, scy)),
                feature=Feature(
                    type="engrave",
                    depth_mm=params.depth_mm,
                    ramp_mm=params.ramp_mm if params.ramp_mm > 0 else None,
                ),
                shape_id=generate_shape_id(shape_id_prefix, item_index),
            )
            items.append(item)
            item_index += 1

    if not items and not allow_empty:
        raise GeneratorSkipError(
            f"FlutingGenerator: No grooves fit within domain. "
            f"Domain bounds: {w:.1f}mm x {h:.1f}mm, "
            f"spacing: {params.spacing_mm}mm"
        )

    return items


__all__ = ["fluting_generator"]
