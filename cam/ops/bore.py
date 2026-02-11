
from __future__ import annotations
import math
from typing import List, Tuple
from cam.model.setup import Setup
from cam.native import core as native_core
from cam.path.toolpath import (
    move_comment,
    move_set_rpm,
    move_set_feed,
    move_rapid,
    move_cut,
    move_retract,
)
from cam.primitives import circle as circle_shape
from cam.types import Vec2
from cam.ops.profile import profile_outline

def _circle_points(cx: float, cy: float, r: float, segments: int = 80) -> List[Tuple[float, float]]:
    pts: List[Tuple[float, float]] = []
    for i in range(segments + 1):
        t = 2.0 * math.pi * (i / segments)
        pts.append((cx + r * math.cos(t), cy + r * math.sin(t)))
    return pts
def bore_helical(center_xy: Tuple[float, float], hole_d_mm: float, setup: Setup, *, depth_mm: float,
                 stepdown_mm: float = 2.5, segments: int = 60) -> List[dict]:

    return native_core.bore_helical(
        center_xy,
        hole_d_mm,
        setup,
        depth_mm=float(depth_mm),
        stepdown_mm=float(stepdown_mm),
    )

def pocket_circle_concentric(center_xy: Tuple[float, float], circle_d_mm: float, setup: Setup, *,
                             depth_mm: float, stepover_mm: float, stepdown_mm: float = 3.0,
                             segments: int = 90, finish: bool = True) -> List[dict]:
    cx, cy = center_xy
    D = float(circle_d_mm)
    tool_d = float(setup.tool.diameter)
    r_wall = max(0.0, D * 0.5 - tool_d * 0.5)
    if r_wall <= 0.0:
        return []

    sd = max(0.1, float(stepdown_mm))
    so = max(0.1, float(stepover_mm))

    moves: List[dict] = []
    moves.append(move_comment(f"pocket_circle_concentric D={D:.3f} tool={tool_d:.3f} so={so:.3f}"))
    moves.append(move_set_rpm(setup.tool.rpm))
    moves.append(move_set_feed(setup.tool.feed_xy))


    radii: List[float] = []
    r = max(so * 0.5, tool_d * 0.25)
    while r < r_wall - 1e-6:
        radii.append(r)
        r += so
    radii.append(r_wall)

    z = 0.0
    target = -abs(float(depth_mm))
    while z > target + 1e-9:
        z_next = max(target, z - sd)
        for ri in radii:
            ring = _circle_points(cx, cy, ri, segments)

            moves.append(move_rapid(x=ring[0][0], y=ring[0][1], z=setup.safe_z))
            moves.append(move_cut(z=z_next, feed=setup.tool.feed_z))
            moves.append(move_set_feed(setup.tool.feed_xy))

            for (x, y) in ring[1:]:
                moves.append(move_cut(x=x, y=y))
            moves.append(move_retract(setup.safe_z))
        z = z_next

    if finish:


        finish_d = max(0.0, D - tool_d)
        shp = circle_shape(Vec2(cx, cy), finish_d * 0.5)
        moves += profile_outline(shp, setup, depth_mm=abs(target), step_down=abs(target))

    return moves
