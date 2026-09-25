from __future__ import annotations

import shapely
from shapely.geometry import LinearRing, Polygon
from shapely.geometry.base import BaseGeometry
from shapely.ops import orient

from cam.model.setup import Setup
from cam.moves import Move
from cam.native import core as native_core
from cam.shape import Shape2D
from cam.types import Vec2


def pocket_raster(
    shape: Shape2D,
    setup: Setup,
    *,
    depth_mm: float,
    stepover: float,
    stepdown: float | None = None,
    strategy: str = "spiral",
) -> list[Move]:
    return native_core.pocket_raster(
        shape,
        setup,
        depth_mm=float(depth_mm),
        stepover_mm=float(stepover),
        stepdown_mm=None if stepdown is None else float(stepdown),
        strategy=strategy,
    )


def _loop_shape(ring: LinearRing) -> Shape2D:
    return Shape2D(tuple(Vec2(float(x), float(y)) for x, y in ring.coords))


def _contour_moves(geometry: BaseGeometry, setup: Setup, *, depth_mm: float, stepdown: float) -> list[Move]:
    moves: list[Move] = []
    for part in shapely.get_parts(geometry):
        if not isinstance(part, Polygon) or part.is_empty:
            continue
        oriented = orient(part, sign=-1.0)
        for ring in (oriented.exterior, *oriented.interiors):
            moves += native_core.profile_outline(
                _loop_shape(ring),
                setup,
                depth_mm=float(depth_mm),
                stepdown_mm=float(stepdown),
            )
    return moves


def pocket_offset_loops(
    region: BaseGeometry,
    setup: Setup,
    *,
    depth_mm: float,
    stepover: float,
    stepdown: float,
    wall_allowance_mm: float = 0.0,
) -> list[Move]:
    tool_radius = float(setup.tool.diameter) / 2.0
    step = min(float(stepover), tool_radius)
    moves: list[Move] = []
    level = 0
    while True:
        offset_region = region.buffer(-(tool_radius + wall_allowance_mm + level * step), join_style="round")
        if offset_region.is_empty:
            return moves
        moves += _contour_moves(offset_region, setup, depth_mm=depth_mm, stepdown=stepdown)
        level += 1


def pocket_finish_contours(
    region: BaseGeometry,
    setup: Setup,
    *,
    depth_mm: float,
    stepdown: float,
    wall_allowance_mm: float = 0.0,
) -> list[Move]:
    tool_radius = float(setup.tool.diameter) / 2.0
    return _contour_moves(
        region.buffer(-(tool_radius + wall_allowance_mm), join_style="round"),
        setup,
        depth_mm=depth_mm,
        stepdown=stepdown,
    )
