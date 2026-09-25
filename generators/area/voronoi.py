from __future__ import annotations

import math
from collections.abc import Sequence
from typing import TYPE_CHECKING, cast

import numpy as np
import shapely
from shapely.geometry import MultiPoint, Point, Polygon
from shapely.ops import unary_union, voronoi_diagram

from domains.transforms import local_to_sheet_batch
from generators.core import (
    GeneratorResult,
    GeneratorSkipError,
    generate_shape_id,
    validate_domain_for_generation,
)
from generators.params.area import VoronoiParams
from generators.utils import (
    boundary_zone,
    clip_polylines_to_domain,
    iter_polygons,
    polyline_engrave_item,
    shapely_to_item,
    sorted_polylines,
)

if TYPE_CHECKING:
    from shapely.geometry.base import BaseGeometry

    from domains import Domain
    from domains.domain import Point2D
    from layout_ast.layout import Item

SEED_ATTEMPTS_PER_POINT = 50

_MIN_POCKET_AREA_MM2 = 0.01


def _seed_region(domain: Domain, margin_mm: float) -> BaseGeometry:
    if margin_mm == 0:
        return domain.polygon
    region = domain.polygon.buffer(-margin_mm)
    if region.is_empty:
        bounds = domain.bounds
        raise ValueError(
            f"VoronoiGenerator: margin {margin_mm}mm leaves no room for seeds in domain "
            f"{bounds.width:.1f}mm x {bounds.height:.1f}mm"
        )
    return region


def _sample_seeds(domain: Domain, seed_count: int, params: VoronoiParams) -> list[Point2D]:
    region = _seed_region(domain, params.margin_mm)
    x_min, y_min, x_max, y_max = region.bounds
    rng = np.random.default_rng(params.seed)
    seeds: list[Point2D] = []
    attempts = 0
    while len(seeds) < seed_count and attempts < seed_count * SEED_ATTEMPTS_PER_POINT:
        attempts += 1
        x = float(rng.uniform(x_min, x_max))
        y = float(rng.uniform(y_min, y_max))
        if not region.contains(Point(x, y)):
            continue
        if params.min_spacing_mm is not None and any(math.dist((x, y), seed) < params.min_spacing_mm for seed in seeds):
            continue
        seeds.append((x, y))
    if len(seeds) < seed_count:
        raise ValueError(
            f"VoronoiGenerator: placed {len(seeds)} of {seed_count} seeds with min_spacing "
            f"{params.min_spacing_mm}mm; lower seed_count or min_spacing"
        )
    return seeds


def _explicit_seeds(domain: Domain, points: Sequence[Point2D]) -> list[Point2D]:
    seeds = local_to_sheet_batch(points, domain)
    for index, (given, seed) in enumerate(zip(points, seeds, strict=True)):
        if not domain.polygon.covers(Point(seed)):
            raise ValueError(f"VoronoiGenerator: point {index} {given} lies outside the parent shape")
    return seeds


def _cell_pieces(domain: Domain, seeds: Sequence[Point2D]) -> list[Polygon]:
    diagram = voronoi_diagram(MultiPoint(seeds), envelope=domain.polygon)
    return [piece for cell in diagram.geoms for piece in iter_polygons(cell.intersection(domain.polygon))]


def _engrave_edges(domain: Domain, pieces: list[Polygon], params: VoronoiParams, shape_id_prefix: str) -> list[Item]:
    boundaries = unary_union([piece.boundary for piece in pieces])
    interior = boundaries.difference(boundary_zone(domain))
    lines = [[(float(x), float(y)) for x, y in line.coords] for line in shapely.get_parts(shapely.line_merge(interior))]
    clipped = clip_polylines_to_domain(lines, domain, min_length_mm=params.min_length_mm)
    edges = sorted_polylines(clipped)
    return [
        polyline_engrave_item(edge, params.depth_mm, generate_shape_id(shape_id_prefix, index))
        for index, edge in enumerate(edges)
    ]


def _representative_xy(polygon: Polygon) -> Point2D:
    point = polygon.representative_point()
    return (point.x, point.y)


def _pocket_cells(pieces: list[Polygon], params: VoronoiParams, shape_id_prefix: str) -> list[Item]:
    inset_mm = cast(float, params.line_width_mm) / 2 + params.cell_inset_mm
    pockets = sorted(
        (
            pocket
            for piece in pieces
            for pocket in iter_polygons(piece.buffer(-inset_mm, join_style="mitre"))
            if pocket.area >= _MIN_POCKET_AREA_MM2
        ),
        key=_representative_xy,
    )
    return [
        shapely_to_item(pocket, "pocket", params.depth_mm, generate_shape_id(shape_id_prefix, index), rest=params.rest)
        for index, pocket in enumerate(pockets)
    ]


def voronoi_generator(
    domain: Domain,
    params: VoronoiParams,
    *,
    allow_empty: bool = False,
    shape_id_prefix: str = "voronoi",
) -> GeneratorResult:
    if not validate_domain_for_generation(
        domain, min_area_mm2=1.0, allow_empty=allow_empty, generator_name="VoronoiGenerator"
    ):
        return []

    if params.points is not None:
        seeds = _explicit_seeds(domain, params.points)
    else:
        seeds = _sample_seeds(domain, cast(int, params.seed_count), params)
    pieces = _cell_pieces(domain, seeds)

    if params.mode == "engrave":
        items = _engrave_edges(domain, pieces, params, shape_id_prefix)
    else:
        items = _pocket_cells(pieces, params, shape_id_prefix)

    if not items and not allow_empty:
        bounds = domain.bounds
        raise GeneratorSkipError(
            f"VoronoiGenerator: no {params.mode} features fit in domain {bounds.width:.1f}mm x {bounds.height:.1f}mm"
        )
    return items


__all__ = ["SEED_ATTEMPTS_PER_POINT", "voronoi_generator"]
