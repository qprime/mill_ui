from __future__ import annotations

from typing import Any, Dict, Mapping, Tuple

from cam.types import Vec2
from cam.primitives import rectangle, circle as circle_shape, polygon as polygon_prim, rounded_rect as rounded_rect_prim
from cam.transforms import Transform2D, place
from cam.shape import Shape2D
from cam.model.setup import Setup
from cam.ops.profile import profile_outline
from cam.path.strategies import (
    onion_skin_then_finish,
    profile_outline_with_tabs,
)
from cam.planner.registry import register_strategy

from .tools import ToolSelection, stepdown_for_tool


def rect_shape(width: float, height: float, center: Tuple[float, float]) -> Shape2D:
    base = rectangle(width, height)
    cx, cy = center
    return place(base, Transform2D(tx=cx - width / 2.0, ty=cy - height / 2.0))


def circle_shape_mm(diameter: float, center: Tuple[float, float]) -> Shape2D:
    cx, cy = center
    return circle_shape(Vec2(cx, cy), diameter / 2.0)


def ensure_center(record: Mapping[str, Any]) -> Tuple[float, float]:
    placement = record.get("placement") if isinstance(record.get("placement"), Mapping) else None
    if placement is not None:
        value = placement.get("center_xy_mm")
        if isinstance(value, (list, tuple)) and len(value) == 2:
            return float(value[0]), float(value[1])

    direct = record.get("center_xy_mm")
    if isinstance(direct, (list, tuple)) and len(direct) == 2:
        return float(direct[0]), float(direct[1])
    return 0.0, 0.0


def offset_rect_shape(width: float, height: float, center: Tuple[float, float], offset: float) -> Shape2D | None:
    width_expanded = width + 2.0 * offset
    height_expanded = height + 2.0 * offset
    if width_expanded <= 0.0 or height_expanded <= 0.0:
        return None
    return rect_shape(width_expanded, height_expanded, center)


def offset_circle_shape(diameter: float, center: Tuple[float, float], offset: float) -> Shape2D | None:
    expanded = diameter + 2.0 * offset
    if expanded <= 0.0:
        return None
    return circle_shape_mm(expanded, center)


def polygon_shape(points: list, center: Tuple[float, float]) -> Shape2D:
    return polygon_prim(points, center)


def offset_polygon_shape(points: list, center: Tuple[float, float], offset: float) -> Shape2D | None:
    if abs(offset) < 1e-9:
        return polygon_shape(points, center)
    cx, cy = center
    abs_points = [(float(p[0]) + cx, float(p[1]) + cy) for p in points if isinstance(p, (tuple, list)) and len(p) >= 2]
    if len(abs_points) < 3:
        return None
    n = len(abs_points)
    offset_points = []
    for i in range(n):
        p0 = abs_points[(i - 1) % n]
        p1 = abs_points[i]
        p2 = abs_points[(i + 1) % n]
        dx1, dy1 = p1[0] - p0[0], p1[1] - p0[1]
        dx2, dy2 = p2[0] - p1[0], p2[1] - p1[1]
        len1 = (dx1**2 + dy1**2) ** 0.5
        len2 = (dx2**2 + dy2**2) ** 0.5
        if len1 < 1e-9 or len2 < 1e-9:
            offset_points.append(p1)
            continue
        nx1, ny1 = -dy1 / len1, dx1 / len1
        nx2, ny2 = -dy2 / len2, dx2 / len2
        nx, ny = (nx1 + nx2) / 2, (ny1 + ny2) / 2
        nlen = (nx**2 + ny**2) ** 0.5
        if nlen < 1e-9:
            nx, ny = nx1, ny1
        else:
            nx, ny = nx / nlen, ny / nlen
        offset_points.append((p1[0] + nx * offset, p1[1] + ny * offset))
    return polygon_prim([(p[0] - cx, p[1] - cy) for p in offset_points], center)


def rounded_rect_shape(w: float, h: float, radii: Dict[str, float], center: Tuple[float, float]) -> Shape2D:
    return rounded_rect_prim(w, h, radii, center)


def offset_rounded_rect_shape(w: float, h: float, radii: Dict[str, float], center: Tuple[float, float], offset: float) -> Shape2D | None:
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
) -> list[Dict[str, Any]]:
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


def _profile_plain(
    shape: Shape2D,
    setup: Setup,
    *,
    depth_mm: float,
    tool: ToolSelection,
    **_: Any,
) -> list[Dict[str, Any]]:
    return profile_outline(shape, setup, depth_mm, step_down=stepdown_for_tool(tool))


register_strategy("profile", "onion_skin", onion_skin_then_finish)
register_strategy("profile", "tabs", profile_outline_with_tabs)
register_strategy("profile", "plain", _profile_plain)


__all__ = [
    "circle_shape_mm",
    "ensure_center",
    "offset_circle_shape",
    "offset_polygon_shape",
    "offset_rect_shape",
    "offset_rounded_rect_shape",
    "polygon_shape",
    "profile_moves_with_options",
    "rect_shape",
    "rounded_rect_shape",
]
