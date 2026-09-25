from __future__ import annotations

from typing import TYPE_CHECKING, cast

import shapely
from shapely.geometry import LineString

from generators.core import (
    GeneratorResult,
    GeneratorSkipError,
    generate_shape_id,
    validate_domain_for_generation,
)
from generators.params.area import StringArtParams
from generators.utils import boundary_zone, clip_polylines_to_domain, polyline_engrave_item, sorted_polylines

if TYPE_CHECKING:
    from domains import Domain
    from domains.domain import Point2D


def _partner(index: int, params: StringArtParams) -> int:
    if params.rule == "multiply":
        return (index * cast(int, params.factor)) % params.anchors
    if params.rule == "skip":
        return (index + cast(int, params.step)) % params.anchors
    return params.anchors - 1 - index


def _anchor_points(domain: Domain, params: StringArtParams) -> list[Point2D]:
    exterior = domain.polygon.exterior
    perimeter = exterior.length
    count = params.anchors
    points = [exterior.interpolate(((k / count + params.phase_deg / 360) % 1.0) * perimeter) for k in range(count)]
    return [(point.x, point.y) for point in points]


def _chord_pairs(params: StringArtParams) -> list[tuple[int, int]]:
    return sorted({(min(i, j), max(i, j)) for i in range(params.anchors) if (j := _partner(i, params)) != i})


def _off_boundary_parts(domain: Domain, chords: list[list[Point2D]]) -> list[list[Point2D]]:
    zone = boundary_zone(domain)
    return [
        [(float(x), float(y)) for x, y in part.coords]
        for chord in chords
        for part in shapely.get_parts(LineString(chord).difference(zone))
        if not part.is_empty
    ]


def string_art_generator(
    domain: Domain,
    params: StringArtParams,
    *,
    allow_empty: bool = False,
    shape_id_prefix: str = "string_art",
) -> GeneratorResult:
    if not validate_domain_for_generation(
        domain, min_area_mm2=1.0, allow_empty=allow_empty, generator_name="StringArtGenerator"
    ):
        return []

    anchors = _anchor_points(domain, params)
    chords = [[anchors[i], anchors[j]] for i, j in _chord_pairs(params)]
    pieces = sorted_polylines(
        clip_polylines_to_domain(_off_boundary_parts(domain, chords), domain, min_length_mm=params.min_length_mm)
    )
    items = [
        polyline_engrave_item(piece, params.depth_mm, generate_shape_id(shape_id_prefix, index))
        for index, piece in enumerate(pieces)
    ]

    if not items and not allow_empty:
        bounds = domain.bounds
        raise GeneratorSkipError(
            f"StringArtGenerator: no chord pieces fit in domain {bounds.width:.1f}mm x {bounds.height:.1f}mm"
        )
    return items


__all__ = ["string_art_generator"]
