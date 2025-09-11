# path: skills/mill_ui/cam/ops/bore.py
from __future__ import annotations
import math
from typing import List, Tuple
from skills.mill_ui.cam.model.setup import Setup
from skills.mill_ui.cam.path.toolpath import (
    move_comment, move_set_rpm, move_set_feed, move_rapid, move_cut, move_retract
)
from skills.mill_ui.cad.primitives import circle as circle_shape
from skills.mill_ui.core.types import Vec2
from skills.mill_ui.cam.ops.profile import profile_outline

def _circle_points(cx: float, cy: float, r: float, segments: int = 80) -> List[Tuple[float, float]]:
    pts: List[Tuple[float, float]] = []
    for i in range(segments + 1):
        t = 2.0 * math.pi * (i / segments)
        pts.append((cx + r * math.cos(t), cy + r * math.sin(t)))
    return pts

def bore_helical(center_xy: Tuple[float, float], hole_d_mm: float, setup: Setup, *, depth: float,
                 stepdown_mm: float = 2.5, segments: int = 60) -> List[dict]:
    """
    Medium holes (tool_d < D ≤ ~3*tool_d): descend in a helical path and circle at each layer.
    This uses segmented moves (no G2/G3), but keeps the tool center at constant radius.
    """
    cx, cy = center_xy
    tool_d = float(setup.tool.diameter)
    D = float(hole_d_mm)
    target = -abs(float(depth))
    if D <= tool_d:
        return []  # let planner choose drill instead

    r_eff = max(0.01, (D - tool_d) * 0.5)
    sd = max(0.1, float(stepdown_mm))

    moves: List[dict] = []
    moves.append(move_comment(f"bore_helical D={D:.3f} tool={tool_d:.3f} r_eff={r_eff:.3f}"))
    moves.append(move_set_rpm(setup.tool.rpm))
    moves.append(move_set_feed(setup.tool.feed_xy))

    # move to start at safe Z
    start_x, start_y = cx + r_eff, cy
    moves.append(move_rapid(x=start_x, y=start_y, z=setup.safe_z))

    z = 0.0
    while z > target + 1e-9:
        z_next = max(target, z - sd)
        # small helical ramp over one revolution down to z_next
        for i in range(1, segments + 1):
            t0 = 2.0 * math.pi * (i - 1) / segments
            t1 = 2.0 * math.pi * (i) / segments
            # linear Z interpolation over the circle
            z_i = z + (z_next - z) * (i / segments)
            x_i = cx + r_eff * math.cos(t1)
            y_i = cy + r_eff * math.sin(t1)
            if i == 1:
                # begin ramp down; use plunge feed for first move
                moves.append(move_cut(z=z_i, feed=setup.tool.feed_z))
                moves.append(move_set_feed(setup.tool.feed_xy))
            moves.append(move_cut(x=x_i, y=y_i, z=z_i))
        z = z_next
        # one circle at constant depth to clean the wall
        ring = _circle_points(cx, cy, r_eff, segments)
        moves.append(move_cut(x=ring[0][0], y=ring[0][1]))
        for (x, y) in ring[1:]:
            moves.append(move_cut(x=x, y=y))
    moves.append(move_retract(setup.safe_z))
    return moves

def pocket_circle_concentric(center_xy: Tuple[float, float], circle_d_mm: float, setup: Setup, *,
                             depth: float, stepover_mm: float, stepdown_mm: float = 3.0,
                             segments: int = 90, finish: bool = True) -> List[dict]:
    """
    Large circular pockets (D > ~3*tool_d): clear with concentric rings from center outwards,
    then (optionally) finish the wall with an inside profile.
    """
    cx, cy = center_xy
    D = float(circle_d_mm)
    tool_d = float(setup.tool.diameter)
    r_wall = max(0.0, D * 0.5 - tool_d * 0.5)  # tool-center limit at the wall
    if r_wall <= 0.0:
        return []

    sd = max(0.1, float(stepdown_mm))
    so = max(0.1, float(stepover_mm))

    moves: List[dict] = []
    moves.append(move_comment(f"pocket_circle_concentric D={D:.3f} tool={tool_d:.3f} so={so:.3f}"))
    moves.append(move_set_rpm(setup.tool.rpm))
    moves.append(move_set_feed(setup.tool.feed_xy))

    # radii from inner to outer
    radii: List[float] = []
    r = max(so * 0.5, tool_d * 0.25)
    while r < r_wall - 1e-6:
        radii.append(r)
        r += so
    radii.append(r_wall)

    z = 0.0
    target = -abs(float(depth))
    while z > target + 1e-9:
        z_next = max(target, z - sd)
        for ri in radii:
            ring = _circle_points(cx, cy, ri, segments)
            # position to ring start
            moves.append(move_rapid(x=ring[0][0], y=ring[0][1], z=setup.safe_z))
            moves.append(move_cut(z=z_next, feed=setup.tool.feed_z))
            moves.append(move_set_feed(setup.tool.feed_xy))
            # cut the ring
            for (x, y) in ring[1:]:
                moves.append(move_cut(x=x, y=y))
            moves.append(move_retract(setup.safe_z))
        z = z_next

    if finish:
        # finish the wall with an inside profile at bottom depth
        # build a tool-center circle at (D - tool_d)
        finish_d = max(0.0, D - tool_d)
        shp = circle_shape(Vec2(cx, cy), finish_d * 0.5)
        moves += profile_outline(shp, setup, depth=abs(target), step_down=abs(target))  # single pass at bottom

    return moves
