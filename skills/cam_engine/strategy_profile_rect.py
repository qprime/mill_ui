# path: skills/cam_engine/strategy_profile_rect.py
# desc: Perimeter profile strategy using rectangular offsets
# api: plan_profile_rect
# tags: cam,strategy,border

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

_Move = Dict[str, float]
_Bounds = Tuple[float, float, float, float]


def _float(value: Any, default: float) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def _int(value: Any, default: int) -> int:
    try:
        return int(round(float(value)))
    except Exception:
        return int(default)


def _depth_steps(total_depth_mm: float, stepdown_mm: float) -> List[float]:
    total = abs(float(total_depth_mm))
    step = abs(float(stepdown_mm)) or total
    if step <= 0.0:
        step = total
    depths: List[float] = []
    depth = step
    eps = 1e-9
    while depth < total - eps:
        depths.append(depth)
        depth += step
    depths.append(total)
    return depths


def _rect_points(x0: float, x1: float, y0: float, y1: float, climb_ccw: bool) -> Sequence[Tuple[float, float]]:
    if climb_ccw:
        return (
            (x0, y0),
            (x1, y0),
            (x1, y1),
            (x0, y1),
        )
    return (
        (x0, y0),
        (x0, y1),
        (x1, y1),
        (x1, y0),
    )


def _rect_loop(x0: float, x1: float, y0: float, y1: float, z: float,
               feed: int, climb_ccw: bool) -> List[_Move]:
    pts = _rect_points(x0, x1, y0, y1, climb_ccw)
    moves: List[_Move] = []
    for x, y in pts:
        moves.append({"mode": 1, "x": float(x), "y": float(y), "z": float(z), "f": feed})
    start_x, start_y = pts[0]
    moves.append({"mode": 1, "x": float(start_x), "y": float(start_y), "z": float(z), "f": feed})
    return moves


def _segment_length(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])


def _lerp(a: Tuple[float, float], b: Tuple[float, float], t: float) -> Tuple[float, float]:
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def _tab_windows(perimeter: float, count: int, width_mm: float) -> List[Tuple[float, float]]:
    if perimeter <= 0.0 or count <= 0:
        return []
    spacing = perimeter / float(count)
    span = min(max(width_mm, 0.1), spacing * 0.9)
    half = span * 0.5
    windows: List[Tuple[float, float]] = []
    for i in range(count):
        center = spacing * (i + 0.5)
        start = max(0.0, center - half)
        end = min(perimeter, center + half)
        windows.append((start, end))
    return windows


def _rect_loop_with_tabs(x0: float, x1: float, y0: float, y1: float, z: float,
                         feed: int, plunge: int, climb_ccw: bool,
                         tabs: Dict[str, float]) -> List[_Move]:
    tab_count = int(tabs.get("count", 0) or 0)
    if tab_count <= 0:
        return _rect_loop(x0, x1, y0, y1, z, feed, climb_ccw)

    tab_height = max(0.0, float(tabs.get("height_mm", 3.0)))
    tab_width = max(0.1, float(tabs.get("width_mm", 6.0)))
    tab_z = min(0.0, z + tab_height)

    pts = list(_rect_points(x0, x1, y0, y1, climb_ccw))
    if pts[0] != pts[-1]:
        pts.append(pts[0])

    segments = list(zip(pts, pts[1:]))
    lengths = [_segment_length(a, b) for a, b in segments]
    perimeter = sum(lengths)
    windows = _tab_windows(perimeter, tab_count, tab_width)
    if not windows:
        return _rect_loop(x0, x1, y0, y1, z, feed, climb_ccw)

    moves: List[_Move] = []
    eps = 1e-9
    dist = 0.0
    window_iter = iter(windows)
    current_window = next(window_iter, None)

    def _append_cut(move: _Move) -> None:
        if moves and all(abs(move.get(k, 0.0) - moves[-1].get(k, 0.0)) <= eps for k in ("x", "y", "z")):
            return
        moves.append(move)

    start_x, start_y = pts[0]
    _append_cut({"mode": 1, "x": float(start_x), "y": float(start_y), "z": float(z), "f": feed})

    for (seg_start, seg_end), seg_len in zip(segments, lengths):
        if seg_len <= eps:
            continue
        seg_start_dist = dist
        seg_consumed = 0.0
        while current_window and current_window[0] < seg_start_dist + seg_len - eps:
            win_start, win_end = current_window
            win_start = max(win_start, seg_start_dist)
            win_end = min(win_end, seg_start_dist + seg_len)
            if win_end <= win_start + eps:
                current_window = next(window_iter, None)
                continue

            start_frac = (win_start - seg_start_dist) / seg_len
            end_frac = (win_end - seg_start_dist) / seg_len

            if start_frac > seg_consumed + eps:
                lead_point = _lerp(seg_start, seg_end, start_frac)
                _append_cut({"mode": 1, "x": float(lead_point[0]), "y": float(lead_point[1]), "z": float(z), "f": feed})
                seg_consumed = start_frac

            if tab_z < z - eps:
                _append_cut({"mode": 1, "z": float(tab_z), "f": plunge})

            tab_point = _lerp(seg_start, seg_end, end_frac)
            _append_cut({"mode": 1, "x": float(tab_point[0]), "y": float(tab_point[1]), "z": float(tab_z), "f": feed})
            _append_cut({"mode": 1, "z": float(z), "f": plunge})
            seg_consumed = end_frac
            current_window = next(window_iter, None)

        if seg_consumed < 1.0 - eps:
            end_point = seg_end
            _append_cut({"mode": 1, "x": float(end_point[0]), "y": float(end_point[1]), "z": float(z), "f": feed})
            seg_consumed = 1.0
        dist = seg_start_dist + seg_len

    return moves


@dataclass(frozen=True)
class _Inputs:
    bounds_mm: _Bounds
    offset_mm: float
    depth_mm: float
    stepdown_mm: float
    feed_mm_min: int
    plunge_mm_min: int
    safe_z_mm: float
    climb_ccw: bool
    tool_diameter_mm: float
    tabs: Optional[Dict[str, float]]


def _resolve_offset(pass_cfg: Mapping[str, Any], cfg: Mapping[str, Any]) -> float:
    offset = _float(pass_cfg.get("offset_mm", 1.0), 1.0)
    if not bool(pass_cfg.get("follow_border", False)):
        return offset
    border_pass = next(
        (pc for pc in cfg["passes"] if str(pc.get("strategy")) == "border_rect"),
        None,
    )
    if not border_pass:
        return offset
    inset = _float(border_pass.get("inset_mm", 0.0), 0.0)
    width = _float(border_pass.get("width_mm", 0.0), 0.0)
    outer = inset + width
    extra = _float(pass_cfg.get("extra_offset_mm", 0.5), 0.5)
    return max(offset, outer + extra)


def _resolve_tabs(pass_cfg: Mapping[str, Any], tool_diameter_mm: float) -> Optional[Dict[str, float]]:
    raw = pass_cfg.get("tabs")
    if not isinstance(raw, Mapping):
        return None
    count = _int(raw.get("count", 0), 0)
    if count <= 0:
        return None
    tabs: Dict[str, float] = {"count": float(count)}
    height = _float(raw.get("height_mm", 3.0), 3.0)
    tabs["height_mm"] = max(0.0, height)
    width = raw.get("width_mm")
    if width is None:
        width_val = max(tool_diameter_mm * 2.0, 6.0)
    else:
        width_val = max(0.1, _float(width, 6.0))
    tabs["width_mm"] = width_val
    return tabs


def _resolve_inputs(pass_cfg: Mapping[str, Any], cfg: Mapping[str, Any]) -> _Inputs:
    hm_cfg = cfg["heightmap"]
    bounds = tuple(hm_cfg.get("bounds_mm") or (0.0, 0.0, 0.0, 0.0))  # type: ignore[assignment]
    offset = _resolve_offset(pass_cfg, cfg)
    depth = _float(pass_cfg.get("target_depth_mm", hm_cfg.get("max_depth_mm", 2.0)), 2.0)
    stepdown = _float(pass_cfg.get("stepdown_mm", depth), depth)
    feed = _int(pass_cfg.get("feed_mm_per_min", 900), 900)
    plunge = _int(pass_cfg.get("plunge_mm_per_min", feed), feed)
    safe_z = float(cfg["stock"].get("safe_z_mm", 6.0))
    climb_ccw = bool(pass_cfg.get("climb_ccw", True))
    tool = pass_cfg.get("tool") or {}
    tool_diam = _float(tool.get("diameter_mm", 0.0), 0.0)
    tabs = _resolve_tabs(pass_cfg, tool_diam)
    return _Inputs(
        bounds_mm=(float(bounds[0]), float(bounds[1]), float(bounds[2]), float(bounds[3])),
        offset_mm=float(offset),
        depth_mm=float(abs(depth)),
        stepdown_mm=float(abs(stepdown)),
        feed_mm_min=feed,
        plunge_mm_min=plunge,
        safe_z_mm=float(safe_z),
        climb_ccw=climb_ccw,
        tool_diameter_mm=tool_diam,
        tabs=tabs,
    )


def plan_profile_rect(pass_cfg: Mapping[str, Any], cfg: Mapping[str, Any]) -> List[_Move]:
    if not bool(pass_cfg.get("enable", True)):
        return []

    params = _resolve_inputs(pass_cfg, cfg)

    xmin, xmax, ymin, ymax = params.bounds_mm
    offset = params.offset_mm
    if xmax <= xmin or ymax <= ymin:
        return []

    x0 = xmin - offset
    x1 = xmax + offset
    y0 = ymin - offset
    y1 = ymax + offset

    if x1 <= x0 or y1 <= y0:
        return []

    depths = _depth_steps(params.depth_mm, params.stepdown_mm)
    feed = params.feed_mm_min
    plunge = params.plunge_mm_min

    moves: List[_Move] = []
    start_x, start_y = x0, y0
    moves.append({"mode": 0, "x": float(start_x), "y": float(start_y)})

    current_z = params.safe_z_mm
    for depth in depths:
        target_z = -depth
        if current_z != target_z:
            moves.append({"mode": 0, "z": float(params.safe_z_mm)})
            moves.append({"mode": 1, "z": float(target_z), "f": plunge})
            current_z = target_z
        if params.tabs:
            moves.extend(_rect_loop_with_tabs(x0, x1, y0, y1, target_z, feed, plunge, params.climb_ccw, params.tabs))
        else:
            moves.extend(_rect_loop(x0, x1, y0, y1, target_z, feed, params.climb_ccw))

    moves.append({"mode": 0, "z": float(params.safe_z_mm)})
    return moves
