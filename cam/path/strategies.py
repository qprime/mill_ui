from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from itertools import pairwise

from cam.model.setup import Setup
from cam.moves import Move
from cam.ops.pocket import pocket_raster
from cam.ops.profile import profile_outline
from cam.path.toolpath import (
    move_comment,
    move_cut,
    move_rapid,
    move_retract,
    move_set_feed,
    move_set_rpm,
    offset_moves_z,
)
from cam.planner.params import stepdown_for, stepover_for
from cam.primitives import rectangle
from cam.shape import Shape2D
from cam.transforms import Transform2D, place
from cam.types import Vec2


def onion_skin_then_finish(
    shape: Shape2D,
    setup: Setup,
    total_depth_mm: float,
    *,
    skin_mm: float = 0.5,
    step_down_mm: float | None = None,
    spring_pass: bool = False,
    cut_through_mm: float = 0.2,
) -> list[Move]:
    rough_moves, finish_depth = onion_skin_rough(
        shape,
        setup,
        total_depth_mm,
        skin_mm=skin_mm,
        step_down_mm=step_down_mm,
        cut_through_mm=cut_through_mm,
    )
    moves = list(rough_moves)
    moves.append(move_comment("finish_profile_pass"))
    moves += profile_outline(shape, setup, depth_mm=finish_depth, step_down=finish_depth)
    if spring_pass:
        moves.append(move_comment("finish_profile_pass"))
        moves += profile_outline(shape, setup, depth_mm=finish_depth, step_down=finish_depth)
    return moves


def onion_skin_rough(
    shape: Shape2D,
    setup: Setup,
    total_depth_mm: float,
    *,
    skin_mm: float = 0.5,
    step_down_mm: float | None = None,
    cut_through_mm: float = 0.2,
) -> tuple[list[Move], float]:
    total = abs(float(total_depth_mm))
    skin = max(0.0, float(skin_mm))
    sd = step_down_mm or stepdown_for(tool_diameter=setup.tool.diameter, cap_mm=3.0)

    if skin <= 0.0:
        moves = profile_outline(shape, setup, depth_mm=total, step_down=sd)
        return moves, total + max(0.0, float(cut_through_mm))

    rough_depth = max(0.0, total - skin)
    finish_depth = total + max(0.0, float(cut_through_mm))
    moves: list[Move] = []
    moves.append(move_comment(f"onion_skin_rough rough={rough_depth:.3f} finish_depth={finish_depth:.3f}"))
    if rough_depth > 0:
        moves += profile_outline(shape, setup, depth_mm=rough_depth, step_down=sd)
    return moves, finish_depth


def _segment_length(a: Vec2, b: Vec2) -> float:
    return math.hypot(b.x - a.x, b.y - a.y)


def _lerp_vec(a: Vec2, b: Vec2, t: float) -> Vec2:
    return Vec2(a.x + (b.x - a.x) * t, a.y + (b.y - a.y) * t)


@dataclass(frozen=True)
class _TabSegment:
    start: Vec2
    end: Vec2
    held: bool

    @property
    def length(self) -> float:
        return _segment_length(self.start, self.end)


def _tab_segments(pts: Sequence[Vec2], windows: Sequence[tuple[float, float]]) -> list[_TabSegment]:
    segments: list[_TabSegment] = []
    distance = 0.0
    for start, end in pairwise(pts):
        length = _segment_length(start, end)
        if length < 1e-9:
            continue
        splits = sorted(
            {
                0.0,
                length,
                *(
                    boundary - distance
                    for window in windows
                    for boundary in window
                    if distance < boundary < distance + length
                ),
            }
        )
        for lo, hi in pairwise(splits):
            midpoint = distance + (lo + hi) / 2
            segments.append(
                _TabSegment(
                    _lerp_vec(start, end, lo / length),
                    _lerp_vec(start, end, hi / length),
                    any(a <= midpoint <= b for a, b in windows),
                )
            )
        distance += length
    return segments


def _tab_path_moves(
    segments: Sequence[_TabSegment], start_z: float, end_z: float, tab_z: float, setup: Setup
) -> list[Move]:
    length = sum(segment.length for segment in segments)
    if length < 1e-9:
        return []
    moves: list[Move] = []
    distance = 0.0
    current_z = start_z
    for segment in segments:
        z0 = start_z + (end_z - start_z) * distance / length
        distance += segment.length
        z1 = start_z + (end_z - start_z) * distance / length
        if segment.held:
            z0, z1 = max(z0, tab_z), max(z1, tab_z)
        if abs(z0 - current_z) > 1e-9:
            moves.append(move_cut(z=z0, feed=setup.tool.feed_z))
        moves.append(
            move_cut(
                x=segment.end.x,
                y=segment.end.y,
                z=z1 if abs(z1 - z0) > 1e-9 else None,
                feed=setup.tool.feed_xy,
            )
        )
        current_z = z1
    return moves


def _ramp_entry_moves(
    segments: Sequence[_TabSegment],
    target_z: float,
    prev_z: float,
    ramp_angle_deg: float,
    tab_z: float,
    setup: Setup,
) -> list[Move]:
    start = segments[0].start
    step_down = abs(target_z - prev_z)
    ramp_dist = step_down / math.tan(math.radians(ramp_angle_deg)) if ramp_angle_deg > 0 else 0.0
    if ramp_dist < 1e-9 or sum(segment.length for segment in segments) < ramp_dist - 1e-9:
        return [move_rapid(x=start.x, y=start.y, z=setup.safe_z), move_cut(z=target_z, feed=setup.tool.feed_z)]

    entry: list[_TabSegment] = []
    remaining = ramp_dist
    for segment in reversed(segments):
        length = min(segment.length, remaining)
        end = _lerp_vec(segment.end, segment.start, length / segment.length)
        entry.append(_TabSegment(segment.end, end, segment.held))
        remaining -= length
        if remaining < 1e-9:
            break
    return_path = [_TabSegment(segment.end, segment.start, segment.held) for segment in reversed(entry)]
    return [
        move_rapid(x=start.x, y=start.y, z=setup.safe_z),
        move_cut(z=prev_z, feed=setup.tool.feed_z),
        *_tab_path_moves(entry, prev_z, target_z, tab_z, setup),
        *_tab_path_moves(return_path, target_z, target_z, tab_z, setup),
    ]


def _tab_windows(perimeter: float, count: int, width: float) -> list[tuple[float, float]]:
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
    step_down_mm: float | None = None,
    tab_count: int = 4,
    tab_height_mm: float = 3.0,
    tab_width_mm: float | None = None,
) -> list[Move]:
    pts = shape.points
    if not pts:
        return []

    total = abs(float(depth_mm))
    sd = step_down_mm or stepdown_for(tool_diameter=setup.tool.diameter, cap_mm=3.0)

    perimeter_pts = pts[:-1] if pts[0] == pts[-1] else pts
    if len(perimeter_pts) < 2 or tab_count <= 0:
        return profile_outline(shape, setup, depth_mm=total, step_down=sd)

    closed_pts = (*perimeter_pts, perimeter_pts[0])
    perimeter = sum(_segment_length(a, b) for a, b in pairwise(closed_pts))
    if perimeter <= 0.0:
        return profile_outline(shape, setup, depth_mm=total, step_down=sd)

    width = tab_width_mm if tab_width_mm is not None else max(setup.tool.diameter * 2.0, 6.0)
    tab_windows = _tab_windows(perimeter, tab_count, width)
    if not tab_windows:
        return profile_outline(shape, setup, depth_mm=total, step_down=sd)

    segments = _tab_segments(closed_pts, tab_windows)
    clear_segments = _tab_segments(closed_pts, ())
    moves: list[Move] = [
        move_comment(f"profile_with_tabs depth={total:.3f} tabs={tab_count}"),
        move_set_rpm(setup.tool.rpm),
        move_set_feed(setup.tool.feed_xy),
    ]
    target = -total
    tab_z = min(0.0, target + max(0.0, float(tab_height_mm)))
    z = 0.0
    while z > target + 1e-9:
        z_next = max(target, z - sd)
        layer_segments = segments if z_next < tab_z else clear_segments
        moves += _ramp_entry_moves(layer_segments, z_next, z, float(setup.ramp_angle_deg), tab_z, setup)
        moves += _tab_path_moves(layer_segments, z_next, z_next, tab_z, setup)
        moves.append(move_retract(setup.safe_z))
        z = z_next
    return moves


def pocket_then_finish_profile(
    shape: Shape2D,
    setup: Setup,
    *,
    total_depth_mm: float,
    stepover_mm: float | None = None,
    step_down_mm: float | None = None,
    cleanup_offset_mm: float = 0.25,
    start_depth_mm: float = 0.0,
    finish_perimeter: bool = True,
    pocket_strategy: str = "spiral",
) -> list[Move]:

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

    tool_d = float(getattr(setup.tool, "diameter", 3.0))
    tool_r = 0.5 * tool_d
    sd = step_down_mm if step_down_mm is not None else stepdown_for(tool_diameter=tool_d, cap_mm=3.0)
    so = stepover_mm if stepover_mm is not None else stepover_for(tool_diameter=tool_d)

    moves: list[Move] = []

    if pocket_strategy == "spiral":
        moves.append(move_comment(f"BEGIN spiral pocket sd={sd:.3f} so={so:.3f}"))
        moves += pocket_raster(shape, setup, depth_mm=cut_depth, stepover=so, stepdown=sd, strategy="spiral")
    elif finish_perimeter:
        shrink = tool_r + float(cleanup_offset_mm)
        w_rough = max(0.0, w - 2.0 * shrink)
        h_rough = max(0.0, h - 2.0 * shrink)
        if w_rough > 0.0 and h_rough > 0.0:
            rough = rectangle(w_rough, h_rough)
            rough = place(rough, Transform2D(tx=cx - 0.5 * w_rough, ty=cy - 0.5 * h_rough))
            moves.append(move_comment(f"BEGIN rough pocket cleanup={cleanup_offset_mm:.3f}mm sd={sd:.3f} so={so:.3f}"))
            moves += pocket_raster(rough, setup, depth_mm=cut_depth, stepover=so, stepdown=sd, strategy="raster")
        w_fin = max(0.0, w - tool_d)
        h_fin = max(0.0, h - tool_d)
        if w_fin > 0.0 and h_fin > 0.0:
            finish = rectangle(w_fin, h_fin)
            finish = place(finish, Transform2D(tx=cx - 0.5 * w_fin, ty=cy - 0.5 * h_fin))
            moves.append(move_comment("BEGIN finish profile pass"))
            moves += profile_outline(finish, setup, depth_mm=cut_depth, step_down=sd)
    else:
        moves.append(move_comment(f"BEGIN pocket (no finish) sd={sd:.3f} so={so:.3f}"))
        moves += pocket_raster(shape, setup, depth_mm=cut_depth, stepover=so, stepdown=sd, strategy="raster")

    return offset_moves_z(moves, start)
