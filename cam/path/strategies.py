# path: skills/mill_ui/cam/path/strategies.py
from __future__ import annotations
from typing import List, Set, Optional, Tuple

import math

from cam.shape import Shape2D
from cam.primitives import rectangle
from cam.transforms import Transform2D, place
from cam.types import Vec2

from cam.model.setup import Setup
from cam.ops.profile import profile_outline
from cam.ops.pocket import pocket_raster
from cam.planner.params import stepdown_for, stepover_for
from cam.path.toolpath import (
    move_comment, move_set_rpm, move_set_feed, move_rapid, move_cut, move_retract
)

# ---------------------------------------------------------------------------
# Internal helper: single finish loop at target depth for a given shape
# ---------------------------------------------------------------------------

def _finish_profile_pass(shape: Shape2D, setup: Setup, depth_mm: float) -> List[dict]:
    pts = shape.points
    if not pts:
        return []
    target_z = -abs(float(depth_mm))
    m: List[dict] = []
    m.append(move_comment("finish_profile_pass"))
    m.append(move_set_rpm(setup.tool.rpm))
    m.append(move_set_feed(setup.tool.feed_xy))
    p0 = pts[0]
    m.append(move_rapid(x=p0.x, y=p0.y, z=setup.safe_z))
    m.append(move_cut(z=target_z, feed=setup.tool.feed_z))   # plunge at Z feed
    m.append(move_set_feed(setup.tool.feed_xy))              # restore XY feed
    for p in pts[1:]:
        m.append(move_cut(x=p.x, y=p.y))
    m.append(move_retract(setup.safe_z))
    return m

# ---------------------------------------------------------------------------
# Profiles: onion-skin rough then finish (for external cutouts)
# ---------------------------------------------------------------------------

def onion_skin_then_finish(
    shape: Shape2D,
    setup: Setup,
    total_depth_mm: float,
    *,
    skin_mm: float = 0.5,
    step_down_mm: Optional[float] = None,
    spring_pass: bool = False,
) -> List[dict]:
    """
    For external profiles: rough to (total - skin), then single finish pass at total.
    Optional spring pass to clean deflection.
    """
    total = abs(float(total_depth_mm))
    skin  = max(0.0, float(skin_mm))
    sd = step_down_mm or stepdown_for(tool_diameter=setup.tool.diameter, cap_mm=3.0)

    moves: List[dict] = []
    if skin <= 0.0:
        moves += profile_outline(shape, setup, depth=total, step_down=sd)
        return moves

    rough_depth = max(0.0, total - skin)
    moves.append(move_comment(f"onion_skin_then_finish rough={rough_depth:.3f} finish={total:.3f}"))
    if rough_depth > 0:
        moves += profile_outline(shape, setup, depth=rough_depth, step_down=sd)
    moves += _finish_profile_pass(shape, setup, depth_mm=total)
    if spring_pass:
        moves += _finish_profile_pass(shape, setup, depth_mm=total)
    return moves

def _offset_moves_z(moves: List[dict], offset: float) -> List[dict]:
    if offset <= 0.0:
        return moves
    adjusted: List[dict] = []
    for mv in moves:
        clone = dict(mv)
        if "z" in clone and clone["z"] is not None:
            z_val = float(clone["z"])
            if z_val <= 0.0:
                clone["z"] = z_val - offset
        adjusted.append(clone)
    return adjusted

# ---------------------------------------------------------------------------
# Profiles: tabs on the final pass
# ---------------------------------------------------------------------------

def _segment_length(a: Vec2, b: Vec2) -> float:
    return math.hypot(b.x - a.x, b.y - a.y)


def _lerp_vec(a: Vec2, b: Vec2, t: float) -> Vec2:
    return Vec2(a.x + (b.x - a.x) * t, a.y + (b.y - a.y) * t)


def _tab_windows(perimeter: float, count: int, width: float) -> List[Tuple[float, float]]:
    if count <= 0 or perimeter <= 0.0:
        return []
    spacing = perimeter / count
    span = min(max(width, 0.1), spacing * 0.9)
    half = 0.5 * span
    windows = []
    for i in range(count):
        center = spacing * (i + 0.5)
        start = max(0.0, center - half)
        end = min(perimeter, center + half)
        windows.append((start, end))
    return windows


def profile_outline_with_tabs(
    shape: Shape2D,
    setup: Setup,
    *,
    depth_mm: float,
    step_down_mm: Optional[float] = None,
    tab_count: int = 4,
    tab_height_mm: float = 3.0,
    tab_width_mm: Optional[float] = None,
) -> List[dict]:
    pts = shape.points
    if not pts:
        return []

    total = abs(float(depth_mm))
    sd = step_down_mm or stepdown_for(tool_diameter=setup.tool.diameter, cap_mm=3.0)

    perimeter_pts = pts[:-1] if pts[0] == pts[-1] else pts
    if len(perimeter_pts) < 2 or tab_count <= 0:
        return profile_outline(shape, setup, depth=total, step_down=sd)

    segments: List[Tuple[Vec2, Vec2]] = []
    lengths: List[float] = []
    for i in range(len(perimeter_pts)):
        a = perimeter_pts[i]
        b = perimeter_pts[(i + 1) % len(perimeter_pts)]
        segments.append((a, b))
        lengths.append(_segment_length(a, b))

    perimeter = sum(lengths)
    if perimeter <= 0.0:
        return profile_outline(shape, setup, depth=total, step_down=sd)

    width = tab_width_mm if tab_width_mm is not None else max(setup.tool.diameter * 2.0, 6.0)
    tab_windows = _tab_windows(perimeter, tab_count, width)
    if not tab_windows:
        return profile_outline(shape, setup, depth=total, step_down=sd)

    moves: List[dict] = []
    moves.append(move_comment(f"profile_with_tabs depth={total:.3f} tabs={tab_count}"))
    moves.append(move_set_rpm(setup.tool.rpm))
    moves.append(move_set_feed(setup.tool.feed_xy))

    target = -total
    z = 0.0
    start_point = pts[0]

    tab_height = max(0.0, float(tab_height_mm))
    tab_z = min(0.0, target + tab_height)

    while z > target + 1e-9:
        z_next = max(target, z - sd)
        moves.append(move_rapid(x=start_point.x, y=start_point.y, z=setup.safe_z))
        moves.append(move_cut(z=z_next, feed=setup.tool.feed_z))
        moves.append(move_set_feed(setup.tool.feed_xy))

        tab_active = tab_windows and z_next < tab_z + 1e-9
        if not tab_active:
            for p in pts[1:]:
                moves.append(move_cut(x=p.x, y=p.y))
            moves.append(move_retract(setup.safe_z))
            z = z_next
            continue

        current_depth = z_next
        window_iter = iter(tab_windows)
        try:
            current_window = next(window_iter)
        except StopIteration:
            current_window = None

        dist = 0.0
        moves.append(move_cut(x=start_point.x, y=start_point.y))

        for (seg_start, seg_end), seg_len in zip(segments, lengths):
            if seg_len <= 0.0:
                continue

            seg_offset = 0.0
            while current_window and current_window[0] < dist + seg_len + 1e-9:
                win_start, win_end = current_window
                win_start = max(win_start, dist)
                win_end = min(win_end, dist + seg_len)
                if win_end <= win_start + 1e-9:
                    try:
                        current_window = next(window_iter)
                        continue
                    except StopIteration:
                        current_window = None
                        break

                start_frac = (win_start - dist) / seg_len
                end_frac = (win_end - dist) / seg_len

                if start_frac > seg_offset + 1e-9:
                    lead_point = _lerp_vec(seg_start, seg_end, start_frac)
                    moves.append(move_cut(x=lead_point.x, y=lead_point.y))

                lifts_to = max(tab_z, z_next)
                moves.append(move_cut(z=lifts_to))
                tab_point = _lerp_vec(seg_start, seg_end, end_frac)
                moves.append(move_cut(x=tab_point.x, y=tab_point.y))
                moves.append(move_cut(z=current_depth))

                seg_offset = end_frac
                try:
                    current_window = next(window_iter)
                except StopIteration:
                    current_window = None
                    break

            if seg_offset < 1.0 - 1e-9:
                moves.append(move_cut(x=seg_end.x, y=seg_end.y))
            dist += seg_len

        moves.append(move_retract(setup.safe_z))
        z = z_next

    return moves

# ---------------------------------------------------------------------------
# Pockets: rough (shrunken) then finish profile on the true boundary
# ---------------------------------------------------------------------------

def pocket_then_finish_profile(
    shape: Shape2D,
    setup: Setup,
    *,
    total_depth_mm: float,
    stepover_mm: Optional[float] = None,
    step_down_mm: Optional[float] = None,
    cleanup_offset_mm: float = 0.25,
    start_depth_mm: float = 0.0,
) -> List[dict]:
    """
    For internal pockets (e.g., panel recess):
      1) Raster pocket on a shrunken boundary that leaves cleanup_offset at the true wall.
      2) Full-depth profile on the true inside boundary to clean the wall.
    """
    # Compute true bounds and center
    xs = [p.x for p in shape.points]
    ys = [p.y for p in shape.points]
    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)
    cx = 0.5 * (minx + maxx)
    cy = 0.5 * (miny + maxy)
    w = maxx - minx
    h = maxy - miny

    total = abs(float(total_depth_mm))
    start = max(0.0, float(start_depth_mm))
    if total <= start + 1e-9:
        return []
    cut_depth = total - start

    # Tool and pass parameters
    tool_d = float(getattr(setup.tool, "diameter", 3.0))
    tool_r = 0.5 * tool_d
    sd = step_down_mm if step_down_mm is not None else stepdown_for(tool_diameter=tool_d, cap_mm=3.0)
    so = stepover_mm if stepover_mm is not None else stepover_for(tool_diameter=tool_d)

    moves: List[dict] = []

    # 1) Rough pocket: shrink by (tool_radius + cleanup_offset)
    #    This keeps the outermost raster tool-center at: boundary - (tool_r + cleanup_offset)
    shrink = tool_r + float(cleanup_offset_mm)
    w_rough = max(0.0, w - 2.0 * shrink)
    h_rough = max(0.0, h - 2.0 * shrink)
    if w_rough > 0.0 and h_rough > 0.0:
        rough = rectangle(w_rough, h_rough)
        rough = place(rough, Transform2D(tx=cx - 0.5 * w_rough, ty=cy - 0.5 * h_rough))
        moves.append(move_comment(f"BEGIN rough pocket cleanup={cleanup_offset_mm:.3f}mm sd={sd:.3f} so={so:.3f}"))
        moves += pocket_raster(rough, setup, depth=cut_depth, stepover=so, stepdown=sd)

    # 2) Full-depth finish profile: inside boundary = (W - tool_d) x (H - tool_d)
    w_fin = max(0.0, w - tool_d)
    h_fin = max(0.0, h - tool_d)
    if w_fin > 0.0 and h_fin > 0.0:
        finish = rectangle(w_fin, h_fin)
        finish = place(finish, Transform2D(tx=cx - 0.5 * w_fin, ty=cy - 0.5 * h_fin))
        moves.append(move_comment("BEGIN finish profile pass"))
        moves += profile_outline(finish, setup, depth=cut_depth, step_down=sd)

    return _offset_moves_z(moves, start)
