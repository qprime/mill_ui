from __future__ import annotations

import math
from collections.abc import Sequence
from itertools import pairwise
from typing import TYPE_CHECKING

from shapely.geometry import LineString, MultiLineString, MultiPolygon, Polygon
from shapely.geometry.base import BaseGeometry

from domains.domain import Bounds2D, Point2D
from domains.transforms import sheet_to_local
from generators.core import (
    GeneratorSkipError,
    LoopSelection,
)
from layout_ast.layout import Feature, Geometry, Item, Placement

if TYPE_CHECKING:
    from domains.domain import Domain

_COINCIDENT_MM = 1e-6


def shapely_to_item(
    polygon: Polygon,
    feature_type: str,
    depth_mm: float,
    shape_id: str,
    *,
    side: str | None = None,
) -> Item:
    if polygon.is_empty:
        raise ValueError("Cannot convert empty polygon to Item")

    if not polygon.is_valid:
        raise ValueError(f"Invalid polygon: {polygon.is_valid}")

    centroid = polygon.centroid
    cx, cy = float(centroid.x), float(centroid.y)

    outer_coords = list(polygon.exterior.coords[:-1])
    outer_points = [[float(x) - cx, float(y) - cy] for x, y in outer_coords]

    geometry_data: dict[str, list[list[float]] | list[list[list[float]]]] = {"points": outer_points}

    if polygon.interiors:
        holes: list[list[list[float]]] = []
        for interior in polygon.interiors:
            hole_coords = list(interior.coords[:-1])
            hole_points = [[float(x) - cx, float(y) - cy] for x, y in hole_coords]
            holes.append(hole_points)
        geometry_data["holes"] = holes

    feature = Feature(
        type=feature_type,
        depth_mm=depth_mm,
        side=side,
    )

    return Item(
        kind="shape",
        type="Polygon",
        geometry=Geometry(data=geometry_data),
        placement=Placement(center_xy_mm=(cx, cy)),
        feature=feature,
        shape_id=shape_id,
    )


def iter_polygons(geom) -> list[Polygon]:
    result: list[Polygon] = []

    if geom.is_empty:
        return result

    if isinstance(geom, Polygon):
        result.append(geom)
    elif isinstance(geom, MultiPolygon):
        for poly in geom.geoms:
            if not poly.is_empty:
                result.append(poly)
    elif hasattr(geom, "geoms"):
        for sub in geom.geoms:
            result.extend(iter_polygons(sub))

    return result


def _iter_linestrings(geom: BaseGeometry) -> list[LineString]:
    if geom.is_empty:
        return []
    if isinstance(geom, LineString):
        return [geom]
    if isinstance(geom, MultiLineString):
        return list(geom.geoms)
    if hasattr(geom, "geoms"):
        result: list[LineString] = []
        for sub in geom.geoms:
            result.extend(_iter_linestrings(sub))
        return result
    return []


def clip_polylines_to_domain(
    polylines: Sequence[Sequence[Point2D]],
    domain: Domain,
    *,
    min_length_mm: float = 0.0,
) -> list[list[Point2D]]:
    if min_length_mm < 0:
        raise ValueError(f"clip_polylines_to_domain: min_length_mm must be non-negative, got {min_length_mm}")
    polygon = domain.polygon
    pieces: list[list[Point2D]] = []
    for polyline in polylines:
        if len(polyline) < 2:
            continue
        line = LineString(polyline)
        if polygon.covers(line):
            candidates = [[(float(x), float(y)) for x, y in polyline]]
        else:
            candidates = _merge_contiguous(
                [
                    [(float(x), float(y)) for x, y in piece.coords]
                    for piece in _iter_linestrings(line.intersection(polygon))
                ]
            )
        for points in candidates:
            if len(points) >= 2 and _polyline_length(points) >= min_length_mm:
                pieces.append(points)
    return pieces


def _merge_contiguous(pieces: list[list[Point2D]], tolerance_mm: float = _COINCIDENT_MM) -> list[list[Point2D]]:
    merged: list[list[Point2D]] = []
    for piece in pieces:
        if merged and math.dist(merged[-1][-1], piece[0]) <= tolerance_mm:
            merged[-1] = merged[-1] + piece[1:]
        else:
            merged.append(list(piece))
    return merged


def _polyline_length(points: Sequence[Point2D]) -> float:
    return sum(math.dist(a, b) for a, b in pairwise(points))


def rotate_points(points: Sequence[Point2D], angle_rad: float) -> list[Point2D]:
    if angle_rad == 0.0:
        return list(points)
    cos_a = math.cos(angle_rad)
    sin_a = math.sin(angle_rad)
    return [(x * cos_a - y * sin_a, x * sin_a + y * cos_a) for x, y in points]


def join_pieces_at_point(
    pieces: list[list[Point2D]],
    point: Point2D,
    tolerance_mm: float = _COINCIDENT_MM,
) -> list[list[Point2D]]:
    if len(pieces) < 2:
        return pieces
    first, last = pieces[0], pieces[-1]
    if math.dist(first[0], point) > tolerance_mm or math.dist(last[-1], point) > tolerance_mm:
        return pieces
    return [last + first[1:], *pieces[1:-1]]


def polyline_engrave_item(
    points: Sequence[Point2D],
    depth_mm: float,
    shape_id: str,
) -> Item:
    cx = sum(p[0] for p in points) / len(points)
    cy = sum(p[1] for p in points) / len(points)
    is_open = math.dist(points[0], points[-1]) > _COINCIDENT_MM
    return Item(
        kind="shape",
        type="Polyline",
        geometry=Geometry(data={"points": [[x - cx, y - cy] for x, y in points], "is_open": is_open}),
        placement=Placement(center_xy_mm=(cx, cy)),
        feature=Feature(type="engrave", depth_mm=depth_mm),
        shape_id=shape_id,
    )


def get_local_bounds(domain: Domain) -> Bounds2D:
    local_points = [sheet_to_local(pt, domain) for pt in domain.outer_boundary]
    return Bounds2D.from_points(local_points)


def compute_centroid_and_normalize(
    boundary: tuple[tuple[float, float], ...] | list[tuple[float, float]],
) -> tuple[tuple[float, float], list[list[float]]]:
    cx = sum(p[0] for p in boundary) / len(boundary)
    cy = sum(p[1] for p in boundary) / len(boundary)
    normalized = [[pt[0] - cx, pt[1] - cy] for pt in boundary]
    return (cx, cy), normalized


def extract_loops(
    domain: Domain,
    selection: LoopSelection,
    generator_name: str,
) -> list[tuple[int, tuple[tuple[float, float], ...]]]:
    all_loops = [domain.outer_boundary, *domain.inner_boundaries]
    num_loops = len(all_loops)

    if selection == "outer_only":
        return [(0, domain.outer_boundary)]

    elif selection == "inner_only":
        return [(i + 1, inner) for i, inner in enumerate(domain.inner_boundaries)]

    elif selection == "all_loops":
        return [(i, loop) for i, loop in enumerate(all_loops)]

    elif isinstance(selection, list):
        result = []
        for idx in selection:
            if idx < 0 or idx >= num_loops:
                raise GeneratorSkipError(
                    f"{generator_name}: loop index {idx} out of range. "
                    f"Domain has {num_loops} loops (0=outer, 1-{num_loops - 1}=inner)"
                )
            result.append((idx, all_loops[idx]))
        return result

    else:
        raise ValueError(f"{generator_name}: invalid loop_selection: {selection}")


def loop_type_suffix(index: int) -> str:
    if index == 0:
        return "outer"
    return f"inner_{index}"


def create_line_item(
    start: tuple[float, float],
    end: tuple[float, float],
    depth_mm: float,
    shape_id: str,
    line_width_mm: float = 0.5,
) -> Item:
    cx = (start[0] + end[0]) / 2
    cy = (start[1] + end[1]) / 2

    geometry_data = {
        "start": [start[0] - cx, start[1] - cy],
        "end": [end[0] - cx, end[1] - cy],
        "width_mm": line_width_mm,
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


def is_major_tick(pos: float, origin: float, major_spacing: float) -> bool:
    offset = abs(pos - origin)
    return abs(offset % major_spacing) < 0.001 or abs(offset % major_spacing - major_spacing) < 0.001


__all__ = [
    "clip_polylines_to_domain",
    "compute_centroid_and_normalize",
    "create_line_item",
    "extract_loops",
    "get_local_bounds",
    "is_major_tick",
    "iter_polygons",
    "join_pieces_at_point",
    "loop_type_suffix",
    "polyline_engrave_item",
    "rotate_points",
    "shapely_to_item",
]
