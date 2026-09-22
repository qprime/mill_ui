from __future__ import annotations

import math
from typing import TYPE_CHECKING

from domains.transforms import local_to_sheet_batch
from generators.core import (
    GeneratorResult,
    GeneratorSkipError,
    generate_shape_id,
    validate_domain_for_generation,
)
from generators.curves.sampler import sample_parametric
from generators.params.area import RoseCurveParams
from generators.utils import (
    clip_polylines_to_domain,
    get_local_bounds,
    join_pieces_at_point,
    polyline_engrave_item,
    rotate_points,
)

if TYPE_CHECKING:
    from domains import Domain
    from domains.domain import Point2D


def rose_curve_generator(
    domain: Domain,
    params: RoseCurveParams,
    *,
    allow_empty: bool = False,
    shape_id_prefix: str = "rose",
) -> GeneratorResult:
    if not validate_domain_for_generation(
        domain,
        min_area_mm2=1.0,
        allow_empty=allow_empty,
        generator_name="RoseCurveGenerator",
    ):
        return []

    local_bounds = get_local_bounds(domain)
    size = params.size_mm if params.size_mm is not None else 0.9 * min(local_bounds.width, local_bounds.height)
    radius = size / 2
    k = params.lobes
    period = math.pi if k % 2 else 2 * math.pi

    def rose(t: float) -> Point2D:
        r = radius * math.cos(k * t)
        return (r * math.cos(t), r * math.sin(t))

    local_points = sample_parametric(
        rose,
        0.0,
        period,
        tolerance_mm=params.tolerance_mm,
        initial_segments=32 * k,
    )
    local_points[-1] = local_points[0]

    if params.rotation_deg != 0.0:
        local_points = rotate_points(local_points, math.radians(params.rotation_deg))

    sheet_points = local_to_sheet_batch(local_points, domain)
    pieces = clip_polylines_to_domain([sheet_points], domain, min_length_mm=params.min_length_mm)
    pieces = join_pieces_at_point(pieces, sheet_points[0])

    items = [
        polyline_engrave_item(piece, params.depth_mm, generate_shape_id(shape_id_prefix, index))
        for index, piece in enumerate(pieces)
    ]

    if not items and not allow_empty:
        raise GeneratorSkipError(
            f"RoseCurveGenerator: curve of size {size:.1f}mm lies entirely outside domain "
            f"{local_bounds.width:.1f}mm x {local_bounds.height:.1f}mm"
        )

    return items


__all__ = ["rose_curve_generator"]
