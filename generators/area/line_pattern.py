from __future__ import annotations

import math
from collections.abc import Callable
from typing import TYPE_CHECKING

from shapely.geometry import LineString

from domains.domain import Bounds2D
from domains.transforms import local_to_sheet_batch
from generators.core import (
    GeneratorResult,
    GeneratorSkipError,
    generate_shape_id,
    validate_domain_for_generation,
)
from generators.params.area import LinePatternParams
from generators.utils import get_local_bounds, iter_polygons, shapely_to_item

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
    if not validate_domain_for_generation(
        domain,
        min_area_mm2=1.0,
        allow_empty=allow_empty,
        generator_name="LinePatternGenerator",
    ):
        return []

    if local_coords:
        bounds = get_local_bounds(domain)

        def to_sheet(pts: list[tuple[float, float]]) -> list[tuple[float, float]]:
            return local_to_sheet_batch(pts, domain)
    else:
        bounds = domain.bounds
        to_sheet: Callable[[list[tuple[float, float]]], list[tuple[float, float]]] | None = None

    return _generate_lines(domain, params, bounds, allow_empty, shape_id_prefix, to_sheet)


def _generate_lines(
    domain: Domain,
    params: LinePatternParams,
    bounds: Bounds2D,
    allow_empty: bool,
    shape_id_prefix: str,
    to_sheet: Callable[[list[tuple[float, float]]], list[tuple[float, float]]] | None,
) -> GeneratorResult:
    angle_rad = math.radians(params.angle_deg)
    dx = math.cos(angle_rad)
    dy = math.sin(angle_rad)
    px = -dy
    py = dx

    diagonal = math.sqrt(bounds.width**2 + bounds.height**2)
    extent = diagonal + params.spacing_mm

    cx, cy = bounds.center

    half_extent = extent / 2
    num_lines_per_side = math.ceil(half_extent / params.spacing_mm)

    items = []
    line_idx = 0

    for i in range(-num_lines_per_side, num_lines_per_side + 1):
        offset = i * params.spacing_mm
        line_cx = cx + offset * px
        line_cy = cy + offset * py

        start = (line_cx - extent * dx, line_cy - extent * dy)
        end = (line_cx + extent * dx, line_cy + extent * dy)

        if to_sheet is not None:
            start, end = to_sheet([start, end])

        line = LineString([start, end])
        buffered = line.buffer(params.line_width_mm / 2, cap_style="flat", join_style="mitre")
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
        raise GeneratorSkipError(
            f"LinePatternGenerator: No lines fit within domain. "
            f"Domain bounds: {bounds.width:.1f}mm x {bounds.height:.1f}mm, "
            f"spacing: {params.spacing_mm}mm"
        )

    return items


__all__ = ["line_pattern_generator"]
