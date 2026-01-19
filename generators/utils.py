"""Utility functions for generators.

This module provides common utilities used across multiple generators,
including conversions between Shapely geometry and LayoutAST Items.

Usage:
    from generators.utils import shapely_to_item

    polygon = LineString([(0, 0), (100, 0)]).buffer(2)
    item = shapely_to_item(
        polygon,
        feature_type="pocket",
        depth_mm=3.0,
        shape_id="groove_001",
    )
"""

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
    """Convert a Shapely Polygon to a LayoutAST Item.

    Handles polygons with holes, converting them to the geometry data
    format expected by the LayoutAST system.

    Args:
        polygon: Shapely Polygon to convert (may have holes)
        feature_type: Feature type string (e.g., "pocket", "profile")
        depth_mm: Depth in millimeters
        shape_id: Unique identifier for this shape
        side: Optional side for profile-type features ("outside", "inside", "on")

    Returns:
        LayoutAST Item with Polygon geometry

    Raises:
        ValueError: If polygon is empty or invalid

    Example:
        >>> from shapely.geometry import LineString
        >>> line = LineString([(0, 0), (100, 0)])
        >>> band = line.buffer(2)  # Creates a rectangle-ish polygon
        >>> item = shapely_to_item(band, "pocket", 3.0, "groove_001")
        >>> item.type
        'Polygon'
    """
    if polygon.is_empty:
        raise ValueError("Cannot convert empty polygon to Item")

    if not polygon.is_valid:
        raise ValueError(f"Invalid polygon: {polygon.is_valid}")

    # Extract outer boundary points (exclude closing point)
    outer_coords = list(polygon.exterior.coords[:-1])
    outer_points = [[float(x), float(y)] for x, y in outer_coords]

    # Build geometry data
    geometry_data = {"points": outer_points}

    # Add holes if present
    if polygon.interiors:
        holes = []
        for interior in polygon.interiors:
            hole_coords = list(interior.coords[:-1])
            hole_points = [[float(x), float(y)] for x, y in hole_coords]
            holes.append(hole_points)
        geometry_data["holes"] = holes

    # Get centroid for placement
    centroid = polygon.centroid
    cx, cy = float(centroid.x), float(centroid.y)

    # Build feature
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
    """Extract all polygons from a Shapely geometry.

    Handles Polygon, MultiPolygon, and GeometryCollection types,
    returning a flat list of non-empty Polygon objects.

    Args:
        geom: Shapely geometry (Polygon, MultiPolygon, or GeometryCollection)

    Returns:
        List of Polygon objects (may be empty)

    Example:
        >>> from shapely.geometry import Polygon, MultiPolygon
        >>> mp = MultiPolygon([Polygon([(0,0),(1,0),(1,1),(0,1)]),
        ...                    Polygon([(2,0),(3,0),(3,1),(2,1)])])
        >>> polys = iter_polygons(mp)
        >>> len(polys)
        2
    """
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
        # GeometryCollection or similar
        for sub in geom.geoms:
            result.extend(iter_polygons(sub))

    return result


__all__ = [
    "shapely_to_item",
    "iter_polygons",
]
