from __future__ import annotations

import math
from dataclasses import replace
from typing import TYPE_CHECKING

from shapely.geometry import LineString, Point, Polygon
from shapely.geometry.base import BaseGeometry

from generators.utils import rotate_points
from layout_ast.layout import Geometry, Item, Placement

if TYPE_CHECKING:
    from domains import Domain
    from domains.domain import Point2D

_CONTAINMENT_TOLERANCE_MM = 1e-6


def place_item(
    item: Item,
    *,
    angle_rad: float,
    offset: Point2D,
    shape_id: str,
    scale: float = 1.0,
) -> Item:
    assert item.geometry is not None
    assert item.placement is not None
    data = dict(item.geometry.data)

    if "points" in data:
        scaled = [(p[0] * scale, p[1] * scale) for p in data["points"]]
        data["points"] = [list(p) for p in rotate_points(scaled, angle_rad)]
    elif "start" in data and "end" in data:
        start, end = rotate_points(
            [(data["start"][0] * scale, data["start"][1] * scale), (data["end"][0] * scale, data["end"][1] * scale)],
            angle_rad,
        )
        data["start"] = list(start)
        data["end"] = list(end)
    if "diameter_mm" in data:
        data["diameter_mm"] = data["diameter_mm"] * scale

    cx, cy = item.placement.center_xy_mm
    cx *= scale
    cy *= scale
    cos_a = math.cos(angle_rad)
    sin_a = math.sin(angle_rad)
    new_cx = cx * cos_a - cy * sin_a + offset[0]
    new_cy = cx * sin_a + cy * cos_a + offset[1]

    return replace(
        item,
        geometry=Geometry(data=data),
        placement=Placement(center_xy_mm=(new_cx, new_cy)),
        shape_id=shape_id,
    )


def _item_shape(item: Item) -> BaseGeometry:
    assert item.geometry is not None
    assert item.placement is not None
    cx, cy = item.placement.center_xy_mm
    data = item.geometry.data
    if item.type == "Circle":
        return Point(cx, cy).buffer(data["diameter_mm"] / 2, resolution=16)
    if "points" in data:
        points = [(cx + p[0], cy + p[1]) for p in data["points"]]
        return Polygon(points) if item.type == "Polygon" else LineString(points)
    if "start" in data and "end" in data:
        return LineString([(cx + data["start"][0], cy + data["start"][1]), (cx + data["end"][0], cy + data["end"][1])])
    raise ValueError(f"item_inside_domain: unsupported item type '{item.type}' with keys {sorted(data)}")


def item_inside_domain(item: Item, domain: Domain) -> bool:
    region = domain.polygon if item.type == "Circle" else domain.polygon.buffer(_CONTAINMENT_TOLERANCE_MM)
    return bool(region.contains(_item_shape(item)))


__all__ = ["item_inside_domain", "place_item"]
