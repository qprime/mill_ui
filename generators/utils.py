
from __future__ import annotations

from typing import TYPE_CHECKING

from shapely.geometry import Polygon, MultiPolygon

from domains.transforms import sheet_to_local
from generators.base import generate_shape_id, LoopSelection
from layout_ast.layout import Feature, Geometry, Item, Placement

if TYPE_CHECKING:
    from domains.domain import Domain


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

    geometry_data = {"points": outer_points}

    if polygon.interiors:
        holes = []
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
    result = []

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


def get_local_bounds(domain: Domain) -> dict[str, float]:
    local_points = [
        sheet_to_local(pt, domain)
        for pt in domain.outer_boundary
    ]

    xs = [p[0] for p in local_points]
    ys = [p[1] for p in local_points]

    return {
        "x_min": min(xs),
        "x_max": max(xs),
        "y_min": min(ys),
        "y_max": max(ys),
    }


def extract_loops(
    domain: Domain,
    selection: LoopSelection,
    generator_name: str,
) -> list[tuple[int, tuple[tuple[float, float], ...]]]:
    all_loops = [domain.outer_boundary] + list(domain.inner_boundaries)
    num_loops = len(all_loops)

    if selection == "outer_only":
        return [(0, domain.outer_boundary)]

    elif selection == "inner_only":
        return [
            (i + 1, inner)
            for i, inner in enumerate(domain.inner_boundaries)
        ]

    elif selection == "all_loops":
        return [(i, loop) for i, loop in enumerate(all_loops)]

    elif isinstance(selection, list):
        result = []
        for idx in selection:
            if idx < 0 or idx >= num_loops:
                raise ValueError(
                    f"{generator_name}: loop index {idx} out of range. "
                    f"Domain has {num_loops} loops (0=outer, 1-{num_loops-1}=inner)"
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
    "shapely_to_item",
    "iter_polygons",
    "get_local_bounds",
    "extract_loops",
    "loop_type_suffix",
    "create_line_item",
    "is_major_tick",
]
