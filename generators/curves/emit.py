from __future__ import annotations

import math
from collections.abc import Callable
from typing import TYPE_CHECKING

from domains.transforms import local_to_sheet_batch
from generators.core import generate_shape_id
from generators.curves.sampler import sample_parametric
from generators.utils import (
    clip_polylines_to_domain,
    join_pieces_at_point,
    polyline_engrave_item,
    rotate_points,
)

if TYPE_CHECKING:
    from domains import Domain
    from domains.domain import Point2D
    from layout_ast.layout import Item


def curve_items(
    domain: Domain,
    fn: Callable[[float], Point2D],
    t_end: float,
    *,
    initial_segments: int,
    tolerance_mm: float,
    rotation_deg: float,
    min_length_mm: float,
    depth_mm: float,
    shape_id_prefix: str,
) -> list[Item]:
    local_points = sample_parametric(
        fn,
        0.0,
        t_end,
        tolerance_mm=tolerance_mm,
        initial_segments=initial_segments,
    )
    closed = math.dist(local_points[0], local_points[-1]) <= tolerance_mm
    if closed:
        local_points[-1] = local_points[0]

    if rotation_deg != 0.0:
        local_points = rotate_points(local_points, math.radians(rotation_deg))

    sheet_points = local_to_sheet_batch(local_points, domain)
    pieces = clip_polylines_to_domain([sheet_points], domain, min_length_mm=min_length_mm)
    if closed:
        pieces = join_pieces_at_point(pieces, sheet_points[0])

    return [
        polyline_engrave_item(piece, depth_mm, generate_shape_id(shape_id_prefix, index))
        for index, piece in enumerate(pieces)
    ]


__all__ = ["curve_items"]
