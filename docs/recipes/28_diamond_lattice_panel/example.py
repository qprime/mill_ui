#!/usr/bin/env python3
"""Recipe 28: Diamond Lattice Panel.

Creates a diagonal lattice by buffering 45-degree lines.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

from shapely.geometry import LineString, MultiPolygon, Polygon

REPO_ROOT = Path(__file__).resolve().parents[3]
RECIPES_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(RECIPES_ROOT))

from domains import Domain
from generators import ProfileParams, profile_generator
from layout_ast.layout import Feature, Geometry, Item, LayoutAST, Placement, Sheet
from recipe_utils import write_recipe_outputs


PANEL_SIZE = 400
SPACING_MM = 25.0
LINE_WIDTH_MM = 4.0
LINE_DEPTH_MM = 3.0


def _iter_polygons(geom):
    if isinstance(geom, Polygon):
        yield geom
    elif isinstance(geom, MultiPolygon):
        for poly in geom.geoms:
            yield poly
    elif hasattr(geom, "geoms"):
        for sub in geom.geoms:
            yield from _iter_polygons(sub)


def _polygon_item(poly: Polygon, depth_mm: float, shape_id: str) -> Item:
    outer = [list(pt) for pt in poly.exterior.coords[:-1]]
    holes = [
        [list(pt) for pt in ring.coords[:-1]]
        for ring in poly.interiors
    ]

    geometry_data = {"points": outer}
    if holes:
        geometry_data["holes"] = holes

    centroid = poly.centroid
    return Item(
        kind="shape",
        type="Polygon",
        geometry=Geometry(data=geometry_data),
        placement=Placement(center_xy_mm=(centroid.x, centroid.y)),
        feature=Feature(type="pocket", depth=str(depth_mm), depth_mm=depth_mm),
        shape_id=shape_id,
    )


def _buffered_line(start: tuple[float, float], end: tuple[float, float]) -> Polygon:
    line = LineString([start, end])
    return line.buffer(LINE_WIDTH_MM / 2, cap_style=2, join_style=2)


def build_ast() -> LayoutAST:
    panel = Domain.from_rectangle(PANEL_SIZE, PANEL_SIZE, center=(200, 200))
    items = []
    items.extend(profile_generator(panel, ProfileParams(side="outside", depth="through")))

    x_min = panel.bounds.x_min
    x_max = panel.bounds.x_max
    y_min = panel.bounds.y_min
    y_max = panel.bounds.y_max
    extent = PANEL_SIZE

    step = SPACING_MM * math.sqrt(2)

    # Lines with slope +1 (y = x + c)
    c = y_min - x_max
    c_max = y_max - x_min
    while c <= c_max + 0.1:
        start = (x_min - extent, (x_min - extent) + c)
        end = (x_max + extent, (x_max + extent) + c)
        band = _buffered_line(start, end).intersection(panel.polygon)
        for idx, poly in enumerate(_iter_polygons(band)):
            items.append(_polygon_item(poly, LINE_DEPTH_MM, f"diag_pos_{int(c)}_{idx}"))
        c += step

    # Lines with slope -1 (y = -x + c)
    c = x_min + y_min
    c_max = x_max + y_max
    while c <= c_max + 0.1:
        start = (x_min - extent, -(x_min - extent) + c)
        end = (x_max + extent, -(x_max + extent) + c)
        band = _buffered_line(start, end).intersection(panel.polygon)
        for idx, poly in enumerate(_iter_polygons(band)):
            items.append(_polygon_item(poly, LINE_DEPTH_MM, f"diag_neg_{int(c)}_{idx}"))
        c += step

    return LayoutAST(
        sheet=Sheet(width_mm=PANEL_SIZE, height_mm=PANEL_SIZE, thickness_mm=19.0),
        items=tuple(items),
        project="recipe_28_diamond_lattice_panel",
    )


def main() -> None:
    output_dir = Path(__file__).parent / "output"
    ast = build_ast()
    write_recipe_outputs(ast, output_dir)


if __name__ == "__main__":
    main()
