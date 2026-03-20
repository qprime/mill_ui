from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from shapely.geometry import Polygon
from shapely.ops import orient

from cam.model.setup import Setup
from cam.moves import Move
from cam.ops.profile import profile_outline
from cam.path.strategies import (
    onion_skin_rough,
    onion_skin_then_finish,
    profile_outline_with_tabs,
)
from cam.primitives import circle as circle_shape
from cam.primitives import polygon as polygon_prim
from cam.primitives import rectangle
from cam.primitives import rounded_rect as rounded_rect_prim
from cam.shape import Shape2D
from cam.transforms import Transform2D, place
from cam.types import Vec2

from .tools import ToolSelection, stepdown_for_tool


def rect_shape(width: float, height: float, center: tuple[float, float]) -> Shape2D:
    base = rectangle(width, height)
    cx, cy = center
    return place(base, Transform2D(tx=cx - width / 2.0, ty=cy - height / 2.0))


def circle_shape_mm(diameter: float, center: tuple[float, float]) -> Shape2D:
    cx, cy = center
    return circle_shape(Vec2(cx, cy), diameter / 2.0)


def offset_rect_shape(width: float, height: float, center: tuple[float, float], offset: float) -> Shape2D | None:
    width_expanded = width + 2.0 * offset
    height_expanded = height + 2.0 * offset
    if width_expanded <= 0.0 or height_expanded <= 0.0:
        return None
    return rect_shape(width_expanded, height_expanded, center)


def offset_circle_shape(diameter: float, center: tuple[float, float], offset: float) -> Shape2D | None:
    expanded = diameter + 2.0 * offset
    if expanded <= 0.0:
        return None
    return circle_shape_mm(expanded, center)


def polygon_shape(points: list, center: tuple[float, float]) -> Shape2D:
    return polygon_prim(points, center)


def offset_polygon_shape(points: list, center: tuple[float, float], offset: float) -> Shape2D | None:
    if abs(offset) < 1e-9:
        return polygon_shape(points, center)
    abs_points = [(float(p[0]), float(p[1])) for p in points if isinstance(p, (tuple, list)) and len(p) >= 2]
    if len(abs_points) < 3:
        return None

    poly = Polygon(abs_points)
    buffered = poly.buffer(offset, join_style="mitre", mitre_limit=2.0)
    buffered = orient(buffered, sign=1.0)

    if buffered.is_empty or not hasattr(buffered, "exterior"):
        return None

    offset_points = list(buffered.exterior.coords[:-1])
    return polygon_prim(offset_points, center)


def rounded_rect_shape(w: float, h: float, radii: dict[str, float], center: tuple[float, float]) -> Shape2D:
    return rounded_rect_prim(w, h, radii, center)


def offset_rounded_rect_shape(
    w: float, h: float, radii: dict[str, float], center: tuple[float, float], offset: float
) -> Shape2D | None:
    w2 = w + 2.0 * offset
    h2 = h + 2.0 * offset
    if w2 <= 0 or h2 <= 0:
        return None
    radii2 = {k: max(0.0, v + offset) for k, v in radii.items()}
    return rounded_rect_prim(w2, h2, radii2, center)


def profile_moves_with_options(
    shape: Shape2D,
    *,
    setup: Setup,
    depth_mm: float,
    tool: ToolSelection,
    onion_skin_mm: float,
    tabs_opts: Mapping[str, Any] | None,
) -> list[Move]:
    step_down = stepdown_for_tool(tool)

    tabs = tabs_opts if isinstance(tabs_opts, Mapping) else {}
    tabs_count = int(tabs.get("count", 0) or 0)
    onion_skin_positive = onion_skin_mm > 0.0
    tabs_enabled = tabs_count > 0

    if onion_skin_positive and tabs_enabled:
        raise ValueError("Onion skin and tabs cannot be combined in the same profile pass")

    if onion_skin_positive:
        return onion_skin_then_finish(
            shape,
            setup,
            total_depth_mm=depth_mm,
            skin_mm=onion_skin_mm,
            step_down_mm=step_down,
        )

    if tabs_enabled:
        tab_height = float(tabs.get("height_mm", 3.0))
        tab_width = tabs.get("width_mm")
        tab_width_val = float(tab_width) if tab_width is not None else None
        return profile_outline_with_tabs(
            shape,
            setup,
            depth_mm=depth_mm,
            step_down_mm=step_down,
            tab_count=max(1, tabs_count),
            tab_height_mm=max(0.1, tab_height),
            tab_width_mm=tab_width_val,
        )

    return profile_outline(shape, setup, depth_mm, step_down=step_down)


def onion_skin_rough_moves(
    shape: Shape2D,
    *,
    setup: Setup,
    depth_mm: float,
    tool: ToolSelection,
    onion_skin_mm: float,
    cut_through_mm: float = 0.2,
) -> tuple[list[Move], float]:
    step_down = stepdown_for_tool(tool)
    return onion_skin_rough(
        shape,
        setup,
        total_depth_mm=depth_mm,
        skin_mm=onion_skin_mm,
        step_down_mm=step_down,
        cut_through_mm=cut_through_mm,
    )


def onion_skin_finish_moves(
    shape: Shape2D,
    *,
    setup: Setup,
    finish_depth: float,
    spring_pass: bool = False,
) -> list[Move]:
    from cam.path.toolpath import move_comment

    moves: list[Move] = [move_comment("finish_profile_pass")]
    moves += profile_outline(shape, setup, depth_mm=finish_depth, step_down=finish_depth)
    if spring_pass:
        moves.append(move_comment("finish_profile_pass"))
        moves += profile_outline(shape, setup, depth_mm=finish_depth, step_down=finish_depth)
    return moves


def _profile_plain(
    shape: Shape2D,
    setup: Setup,
    *,
    depth_mm: float,
    tool: ToolSelection,
    **_: Any,
) -> list[Move]:
    return profile_outline(shape, setup, depth_mm, step_down=stepdown_for_tool(tool))


__all__ = [
    "circle_shape_mm",
    "offset_circle_shape",
    "offset_polygon_shape",
    "offset_rect_shape",
    "offset_rounded_rect_shape",
    "onion_skin_finish_moves",
    "onion_skin_rough_moves",
    "polygon_shape",
    "profile_moves_with_options",
    "rect_shape",
    "rounded_rect_shape",
]
