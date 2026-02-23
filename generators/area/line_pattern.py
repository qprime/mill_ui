
from __future__ import annotations

import math
from typing import TYPE_CHECKING

from shapely.geometry import LineString

from domains.transforms import local_to_sheet_batch
from generators.core import (
    GeneratorResult,
    generate_shape_id,
    validate_domain_for_generation,
)
from generators.params.area import LinePatternParams
from generators.utils import shapely_to_item, iter_polygons, get_local_bounds

if TYPE_CHECKING:
    from domains import Domain


def line_pattern_generator(
    domain: Domain,
    params: LinePatternParams,
    *,
    allow_empty: bool = False,
    shape_id_prefix: str = "line_pattern",
    local_coords: bool = False,
) -> GeneratorResult:

    params.validate()


    if not validate_domain_for_generation(
        domain,
        min_area_mm2=1.0,
        allow_empty=allow_empty,
        generator_name="LinePatternGenerator",
    ):
        return []

    if local_coords:
        return _generate_local_coords(domain, params, allow_empty, shape_id_prefix)
    else:
        return _generate_sheet_coords(domain, params, allow_empty, shape_id_prefix)


def _generate_local_coords(
    domain: Domain,
    params: LinePatternParams,
    allow_empty: bool,
    shape_id_prefix: str,
) -> GeneratorResult:
    local_bounds = get_local_bounds(domain)
    local_width = local_bounds["x_max"] - local_bounds["x_min"]
    local_height = local_bounds["y_max"] - local_bounds["y_min"]

    angle_rad = math.radians(params.angle_deg)
    dx = math.cos(angle_rad)
    dy = math.sin(angle_rad)
    px = -dy
    py = dx

    diagonal = math.sqrt(local_width**2 + local_height**2)
    extent = diagonal + params.spacing_mm

    local_cx = (local_bounds["x_min"] + local_bounds["x_max"]) / 2
    local_cy = (local_bounds["y_min"] + local_bounds["y_max"]) / 2

    half_extent = extent / 2
    num_lines_per_side = int(math.ceil(half_extent / params.spacing_mm))

    items = []
    line_idx = 0

    for i in range(-num_lines_per_side, num_lines_per_side + 1):
        offset = i * params.spacing_mm
        line_cx = local_cx + offset * px
        line_cy = local_cy + offset * py

        local_start = (line_cx - extent * dx, line_cy - extent * dy)
        local_end = (line_cx + extent * dx, line_cy + extent * dy)

        sheet_points = local_to_sheet_batch([local_start, local_end], domain)
        sheet_start, sheet_end = sheet_points[0], sheet_points[1]

        line = LineString([sheet_start, sheet_end])
        buffered = line.buffer(params.line_width_mm / 2, cap_style=2, join_style=2)
        clipped = buffered.intersection(domain.polygon)

        for poly in iter_polygons(clipped):
            if poly.area < 0.01:
                continue

            item = shapely_to_item(
                poly,
                feature_type="pocket",
                depth_mm=params.depth_mm,
                shape_id=generate_shape_id(shape_id_prefix, line_idx),
            )
            items.append(item)
            line_idx += 1

    if not items and not allow_empty:
        raise ValueError(
            f"LinePatternGenerator: No lines fit within domain. "
            f"Domain bounds: {local_width:.1f}mm x {local_height:.1f}mm, "
            f"spacing: {params.spacing_mm}mm"
        )

    return items


def _generate_sheet_coords(
    domain: Domain,
    params: LinePatternParams,
    allow_empty: bool,
    shape_id_prefix: str,
) -> GeneratorResult:
    bounds = domain.bounds
    angle_rad = math.radians(params.angle_deg)

    dx = math.cos(angle_rad)
    dy = math.sin(angle_rad)
    px = -dy
    py = dx

    diagonal = math.sqrt(bounds.width**2 + bounds.height**2)
    extent = diagonal + params.spacing_mm

    cx, cy = bounds.center

    half_extent = extent / 2
    num_lines_per_side = int(math.ceil(half_extent / params.spacing_mm))

    items = []
    line_idx = 0

    for i in range(-num_lines_per_side, num_lines_per_side + 1):
        offset = i * params.spacing_mm
        line_cx = cx + offset * px
        line_cy = cy + offset * py

        start = (line_cx - extent * dx, line_cy - extent * dy)
        end = (line_cx + extent * dx, line_cy + extent * dy)

        line = LineString([start, end])
        buffered = line.buffer(params.line_width_mm / 2, cap_style=2, join_style=2)
        clipped = buffered.intersection(domain.polygon)

        for poly in iter_polygons(clipped):
            if poly.area < 0.01:
                continue

            item = shapely_to_item(
                poly,
                feature_type="pocket",
                depth_mm=params.depth_mm,
                shape_id=generate_shape_id(shape_id_prefix, line_idx),
            )
            items.append(item)
            line_idx += 1

    if not items and not allow_empty:
        raise ValueError(
            f"LinePatternGenerator: No lines fit within domain. "
            f"Domain bounds: {bounds.width:.1f}mm x {bounds.height:.1f}mm, "
            f"spacing: {params.spacing_mm}mm"
        )

    return items


__all__ = ["line_pattern_generator"]
