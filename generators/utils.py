
from __future__ import annotations

from shapely.geometry import Polygon, MultiPolygon

from layout_ast.layout import Feature, Geometry, Item, Placement
from generators.base import generate_shape_id


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
        depth=str(depth_mm),
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


__all__ = [
    "shapely_to_item",
    "iter_polygons",
]
