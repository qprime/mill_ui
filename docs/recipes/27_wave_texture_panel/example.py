#!/usr/bin/env python3
"""Recipe 27: Wave Texture Panel.

Builds sinusoidal wave grooves as buffered polygons and pockets them.
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

try:
    import numpy as np
    HAVE_NUMPY = True
except ImportError:  # pragma: no cover - optional dependency
    HAVE_NUMPY = False

from domains import Domain
from generators import ProfileParams, profile_generator
from layout_ast.layout import Feature, Geometry, Item, LayoutAST, Placement, Sheet
from recipe_utils import write_recipe_outputs


PANEL_SIZE = 300
WAVE_COUNT = 5
AMPLITUDE_MM = 10.0
WAVELENGTH_MM = 60.0
GROOVE_WIDTH_MM = 3.0
GROOVE_DEPTH_MM = 2.0


def _linspace(start: float, stop: float, count: int) -> list[float]:
    if HAVE_NUMPY:
        return np.linspace(start, stop, count).tolist()
    if count <= 1:
        return [start]
    step = (stop - start) / (count - 1)
    return [start + step * i for i in range(count)]


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


def build_ast() -> LayoutAST:
    panel = Domain.from_rectangle(PANEL_SIZE, PANEL_SIZE, center=(150, 150))
    items = []
    items.extend(profile_generator(panel, ProfileParams(side="outside", depth="through")))

    x_min = panel.bounds.x_min
    x_max = panel.bounds.x_max
    y_min = panel.bounds.y_min
    y_max = panel.bounds.y_max

    margin = 30.0
    spacing = (y_max - y_min - 2 * margin) / (WAVE_COUNT - 1)
    base_ys = [y_min + margin + spacing * i for i in range(WAVE_COUNT)]

    samples = int((x_max - x_min) / 5) + 1

    for wave_idx, base_y in enumerate(base_ys):
        xs = _linspace(x_min, x_max, samples)
        if HAVE_NUMPY:
            xs_array = np.array(xs)
            ys = base_y + AMPLITUDE_MM * np.sin(2 * math.pi * (xs_array - x_min) / WAVELENGTH_MM)
            points = list(zip(xs_array.tolist(), ys.tolist()))
        else:
            points = [
                (
                    x,
                    base_y + AMPLITUDE_MM * math.sin(2 * math.pi * (x - x_min) / WAVELENGTH_MM),
                )
                for x in xs
            ]

        wave_line = LineString(points)
        wave_band = wave_line.buffer(GROOVE_WIDTH_MM / 2, cap_style=2, join_style=2)
        clipped = wave_band.intersection(panel.polygon)

        for poly_idx, poly in enumerate(_iter_polygons(clipped)):
            shape_id = f"wave_{wave_idx}_{poly_idx}"
            items.append(_polygon_item(poly, GROOVE_DEPTH_MM, shape_id))

    return LayoutAST(
        sheet=Sheet(width_mm=PANEL_SIZE, height_mm=PANEL_SIZE, thickness_mm=19.0),
        items=tuple(items),
        project="recipe_27_wave_texture_panel",
    )


def main() -> None:
    output_dir = Path(__file__).parent / "output"
    ast = build_ast()
    write_recipe_outputs(ast, output_dir)


if __name__ == "__main__":
    main()
