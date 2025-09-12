# path: skills/mill_ui/cam/path/strategies.py
from __future__ import annotations
from typing import List, Set, Optional

from skills.mill_ui.cad.shape import Shape2D
from skills.mill_ui.cad.primitives import rectangle
from skills.mill_ui.cad.transforms import Transform2D, place

from skills.mill_ui.cam.model.setup import Setup
from skills.mill_ui.cam.ops.profile import profile_outline
from skills.mill_ui.cam.ops.pocket import pocket_raster
from skills.mill_ui.cam.planner.params import stepdown_for, stepover_for
from skills.mill_ui.cam.path.toolpath import (
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

# ---------------------------------------------------------------------------
# Profiles: tabs on the final pass
# ---------------------------------------------------------------------------

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
    Profile with tabs on the final pass: insert small Z lifts (tab_height) at
    k evenly spaced edges. Tabs applied only on the bottom pass.
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
                    lift_z = -max(0.0, total - float(tab_height_mm))
                    moves.append(move_cut(z=lift_z))
                    moves.append(move_cut(z=target))
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
        moves += pocket_raster(rough, setup, depth=total_depth_mm, stepover=so, stepdown=sd)

    # 2) Full-depth finish profile: inside boundary = (W - tool_d) x (H - tool_d)
    w_fin = max(0.0, w - tool_d)
    h_fin = max(0.0, h - tool_d)
    if w_fin > 0.0 and h_fin > 0.0:
        finish = rectangle(w_fin, h_fin)
        finish = place(finish, Transform2D(tx=cx - 0.5 * w_fin, ty=cy - 0.5 * h_fin))
        moves.append(move_comment("BEGIN finish profile pass"))
        moves += profile_outline(finish, setup, depth=total_depth_mm, step_down=sd)

    return moves
