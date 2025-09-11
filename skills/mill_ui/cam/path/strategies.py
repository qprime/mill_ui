# path: skills/mill_ui/cam/path/strategies.py
from __future__ import annotations
from typing import List, Set, Optional
from skills.mill_ui.cad.shape import Shape2D
from skills.mill_ui.cam.model.setup import Setup
from skills.mill_ui.cam.ops.profile import profile_outline
from skills.mill_ui.cam.ops.pocket import pocket_raster
from skills.mill_ui.cam.planner.params import stepdown_for, stepover_for
from skills.mill_ui.cam.path.toolpath import (
    move_comment, move_set_rpm, move_set_feed, move_rapid, move_cut, move_retract
)

def _finish_profile_pass(shape: Shape2D, setup: Setup, depth_mm: float) -> List[dict]:
    """One finish loop at target depth."""
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
    Rough to (total_depth - skin), then do a single finish pass at total_depth.
    Optionally add a duplicate finish 'spring' pass to clean deflection.
    """
    total = abs(float(total_depth_mm))
    skin  = max(0.0, float(skin_mm))
    if skin == 0.0:
        # simple profile
        sd = step_down_mm or stepdown_for(tool_diameter=setup.tool.diameter, cap_mm=3.0)
        return profile_outline(shape, setup, depth=total, step_down=sd)

    rough_depth = max(0.0, total - skin)
    sd = step_down_mm or stepdown_for(tool_diameter=setup.tool.diameter, cap_mm=3.0)

    moves: List[dict] = []
    moves.append(move_comment(f"onion_skin_then_finish rough={rough_depth:.3f} finish={total:.3f}"))
    if rough_depth > 0:
        moves += profile_outline(shape, setup, depth=rough_depth, step_down=sd)
    moves += _finish_profile_pass(shape, setup, depth_mm=total)
    if spring_pass:
        moves += _finish_profile_pass(shape, setup, depth_mm=total)
    return moves

def _evenly_spaced_indices(n: int, k: int) -> Set[int]:
    if k <= 0 or n <= 0:
        return set()
    # spread k indices across 0..n-1 (skip 0 to avoid first plunge)
    return {max(1, round(i * (n - 1) / k)) for i in range(1, k + 1)}

def profile_outline_with_tabs(
    shape: Shape2D,
    setup: Setup,
    *,
    depth_mm: float,
    step_down_mm: Optional[float] = None,
    tab_count: int = 4,
    tab_height_mm: float = 3.0,
) -> List[dict]:
    """
    Profile with tabs on the final pass: insert small Z lifts (tab_height) at k evenly spaced edges.
    """
    pts = shape.points
    if not pts:
        return []

    total = abs(float(depth_mm))
    sd = step_down_mm or stepdown_for(tool_diameter=setup.tool.diameter, cap_mm=3.0)

    moves: List[dict] = []
    moves.append(move_comment(f"profile_with_tabs depth={total:.3f} tabs={tab_count}"))
    moves.append(move_set_rpm(setup.tool.rpm))
    moves.append(move_set_feed(setup.tool.feed_xy))

    target = -total
    z = 0.0
    p0 = pts[0]

    while z > target + 1e-9:
        z_next = max(target, z - sd)
        # one pass loop
        moves.append(move_rapid(x=p0.x, y=p0.y, z=setup.safe_z))
        moves.append(move_cut(z=z_next, feed=setup.tool.feed_z))
        moves.append(move_set_feed(setup.tool.feed_xy))   # restore XY feed

        if z_next > target + 1e-9:
            # roughing pass: no tabs, just trace
            for p in pts[1:]:
                moves.append(move_cut(x=p.x, y=p.y))
        else:
            # final pass: add tab lifts
            idxs = _evenly_spaced_indices(len(pts) - 1, tab_count)
            for i, p in enumerate(pts[1:], start=1):
                moves.append(move_cut(x=p.x, y=p.y))
                if i in idxs:
                    # lift up towards stock by tab_height, then back down to bottom
                    lift_z = -max(0.0, total - float(tab_height_mm))
                    moves.append(move_cut(z=lift_z))
                    moves.append(move_cut(z=target))
        moves.append(move_retract(setup.safe_z))
        z = z_next

    return moves

# ------------------------------------------------------------------
# Helper requested by tests:
#   - Pocket the interior, then onion-skin profile finish.
#   - Accepts total_depth_mm (as tests use), but also tolerates depth_mm.
#   - If stepover not provided, derive from tool diameter.
# ------------------------------------------------------------------
def pocket_then_onion_skin_profile(
    shape: Shape2D,
    setup: Setup,
    *,
    total_depth_mm: Optional[float] = None,
    skin_mm: float = 0.5,
    spring_pass: bool = False,
    stepover_mm: Optional[float] = None,
    step_down_mm: Optional[float] = None,
    depth_mm: Optional[float] = None,   # legacy alias
) -> List[dict]:
    # Resolve total depth from either name
    total = total_depth_mm if total_depth_mm is not None else depth_mm
    if total is None:
        raise ValueError("pocket_then_onion_skin_profile requires total_depth_mm (or depth_mm).")
    total = float(total)

    # Default stepover if not supplied
    so = stepover_mm if stepover_mm is not None else stepover_for(tool_diameter=setup.tool.diameter)

    moves: List[dict] = []
    moves.append(move_comment("pocket_then_onion_skin_profile"))
    # Clear area first
    moves += pocket_raster(shape, setup, depth=total, stepover=so)
    # Then perimeter finish with skin
    moves += onion_skin_then_finish(
        shape, setup,
        total_depth_mm=total,
        skin_mm=skin_mm,
        step_down_mm=step_down_mm,
        spring_pass=spring_pass,
    )
    return moves
