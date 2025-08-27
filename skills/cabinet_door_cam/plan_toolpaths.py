# path: skills/cabinet_door_cam/plan_toolpaths.py
# desc: Stepdown-aware rough raster, finish wall contour, helical spiral pockets for anchors/hinges, and outside-offset onion-skin profile.
# api: plan_toolpaths(cfg: MergedConfig, geo: Geometry) -> dict[str, JobPlan]
# tags: planning, raster, spiral, profile, hinges, anchors, tabs, deterministic

from __future__ import annotations
import math
from typing import Dict, List, Tuple, Optional
from skills.cabinet_door_cam.types import (
    MergedConfig, Geometry, JobPlan, Move, Rect, Circle, ToolPack
)
from skills.cabinet_door_cam.util import round_mm

# ----------------------------
# Small internal helpers
# ----------------------------

def _safe_z(cfg: MergedConfig) -> float:
    return round_mm(cfg.order.safe_z_override_mm or cfg.machine.safe_z_mm)

def _clamp_feed(cfg: MergedConfig, xy: float, z: float) -> tuple[float, float]:
    return (min(xy, cfg.machine.max_feed_xy_mm_min),
            min(z, cfg.machine.max_plunge_z_mm_min))

def _with_spindle_preamble(tool: ToolPack) -> List[Move]:
    return [Move("set_spindle", s=tool.rpm), Move("set_feed", f=tool.feed_xy_mm_min)]

def _z_passes(total: float, tool_step: float, material_step: float) -> List[float]:
    """Return negative Z targets from 0 down to -total using min(tool, material) stepdowns."""
    step = max(0.1, min(tool_step, material_step))
    z, out = 0.0, []
    while z + step < total - 1e-6:
        z += step
        out.append(-z)
    out.append(-total)
    return out

# ----------------------------
# 2D pockets and contours
# ----------------------------

def _raster_pocket(
    rect: Rect,
    total_depth_mm: float,
    tool: ToolPack,
    material_max_step: float,
    feed_xy: float,
    feed_z: float,
    safe_z: float,
) -> List[Move]:
    """Deterministic rectangular raster with stepdowns capped by tool+material."""
    moves: List[Move] = []
    if total_depth_mm <= 0.0:
        return moves

    stepover = max(0.1, round_mm(tool.diameter_mm * tool.stepover_factor))
    y_start = rect.y + stepover / 2.0
    y_limit = rect.y + rect.h - stepover / 2.0

    for target_z in _z_passes(total_depth_mm, tool.max_stepdown_mm, material_max_step):
        moves += [Move("rapid", x=rect.x, y=y_start, z=safe_z),
                  Move("set_feed", f=feed_z),
                  Move("plunge", z=target_z)]
        left_to_right = True
        y = y_start
        while y <= y_limit + 1e-6:
            x0, x1 = (rect.x, rect.x + rect.w) if left_to_right else (rect.x + rect.w, rect.x)
            moves += [Move("set_feed", f=feed_xy), Move("cut", x=x1, y=y, z=target_z)]
            y += stepover
            if y <= y_limit + 1e-6:
                moves += [Move("rapid", x=x1, y=y, z=target_z)]
            left_to_right = not left_to_right
        moves += [Move("retract", z=safe_z)]
    return moves

def _rect_contour_stepdown(
    rect: Rect,
    total_depth_mm: float,
    tool: ToolPack,
    material_max_step: float,
    feed_xy: float,
    feed_z: float,
    safe_z: float,
) -> List[Move]:
    """Contour the inner pocket wall at final size with multiple stepdowns."""
    if total_depth_mm <= 0.0:
        return []
    r = tool.diameter_mm / 2.0
    rect = Rect(rect.x + r, rect.y + r, rect.w - 2 * r, rect.h - 2 * r)
    corners = [
        (rect.x, rect.y),
        (rect.x + rect.w, rect.y),
        (rect.x + rect.w, rect.y + rect.h),
        (rect.x, rect.y + rect.h),
        (rect.x, rect.y),
    ]
    moves: List[Move] = []
    for z in _z_passes(total_depth_mm, tool.max_stepdown_mm, material_max_step):
        moves += [Move("rapid", x=corners[0][0], y=corners[0][1], z=safe_z),
                  Move("set_feed", f=feed_z),
                  Move("plunge", z=z)]
        for (x, y) in corners[1:]:
            moves += [Move("set_feed", f=feed_xy), Move("cut", x=x, y=y, z=z)]
        moves += [Move("retract", z=safe_z)]
    return moves

# ----------------------------
# Helical spiral pockets (anchors/hinges)
# ----------------------------

def _spiral_pocket(
    cx: float,
    cy: float,
    radius_mm: float,
    total_depth_mm: float,
    tool: ToolPack,
    material_max_step: float,
    stepover_factor: float,
    feed_xy: float,
    feed_z: float,
    safe_z: float,
    segments_per_rev: int = 64,
    wall_skim: bool = True,
) -> List[Move]:
    """
    Helical (approx.) spiral pocket:
      - XY follows an Archimedean spiral from wall toward center,
      - Z ramps continuously from 0 to -total_depth_mm,
      - No G2/G3: emitted as small linear segments for GRBL,
      - Optional wall skim at full depth to clean the circular wall.
    """
    moves: List[Move] = []
    if total_depth_mm <= 0.0:
        return moves

    tool_r = tool.diameter_mm / 2.0
    # Slightly inside the wall to avoid chattering on the exact boundary during descent
    wall_r = max(0.0, radius_mm - tool_r * 0.1)
    core_r = tool_r * 0.5  # stop radius threshold
    # Radial stepover per revolution
    step_over = max(0.2, tool.diameter_mm * stepover_factor)
    # Vertical pitch per revolution limited by tool/material stepdown
    pitch = max(0.2, min(tool.max_stepdown_mm, material_max_step))
    # How many revolutions to reach target depth
    revs = max(1, math.ceil(total_depth_mm / pitch))
    # How far inward we should travel over all revolutions
    radial_travel = max(0.0, wall_r - core_r)
    k_per_rad = (radial_travel / (2.0 * math.pi * revs)) if radial_travel > 0 else 0.0

    # Start point at wall
    start_x, start_y = cx + wall_r, cy
    moves += [Move("rapid", x=start_x, y=start_y, z=safe_z),
              Move("set_feed", f=feed_xy)]
    # Optional tiny "pre-plunge" to avoid immediate full-depth Z move on first segment
    pre_z = -min(0.5, total_depth_mm * 0.05)
    moves += [Move("set_feed", f=feed_z), Move("plunge", z=pre_z)]

    total_segments = segments_per_rev * revs
    for i in range(1, total_segments + 1):
        theta = (2.0 * math.pi) * (i / segments_per_rev)
        rev_idx = (i // segments_per_rev)
        # radius decreases linearly with angle (Archimedean spiral)
        r = max(core_r, wall_r - k_per_rad * (theta + 2.0 * math.pi * max(0, rev_idx - 1)))
        # linear Z interpolation over the whole path
        z = -min(total_depth_mm, abs(pre_z) + (total_depth_mm - abs(pre_z)) * (i / total_segments))
        x = cx + r * math.cos(theta)
        y = cy + r * math.sin(theta)
        moves += [Move("set_feed", f=feed_xy), Move("cut", x=x, y=y, z=z)]

    # Retract to safe Z
    moves += [Move("retract", z=safe_z)]

    # Optional clean wall skim at full depth
    if wall_skim and wall_r > 0:
        pts = _circle_polyline(cx, cy, wall_r, segments_per_rev)
        sx, sy = pts[0]
        z = -total_depth_mm
        moves += [Move("rapid", x=sx, y=sy, z=safe_z),
                  Move("set_feed", f=feed_z),
                  Move("plunge", z=z)]
        for (x, y) in pts[1:]:
            moves += [Move("set_feed", f=feed_xy), Move("cut", x=x, y=y, z=z)]
        moves += [Move("retract", z=safe_z)]

    return moves

def _circle_polyline(cx: float, cy: float, r: float, segments: int = 64) -> List[Tuple[float, float]]:
    pts: List[Tuple[float, float]] = []
    for i in range(segments + 1):  # closed loop
        a = (2.0 * math.pi) * (i / segments)
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts

# ----------------------------
# Outside-offset perimeter/profile
# ----------------------------

def _perimeter_with_onion_skin(
    stock: Rect,
    thickness_mm: float,
    onion_mm: float,
    tool: ToolPack,
    material_max_step: float,
    feed_xy: float,
    feed_z: float,
    safe_z: float,
    use_tabs: bool,
    tab_count: int,
    tab_w: float,
    tab_h: float,
) -> List[Move]:
    """Exterior contour offset outward by tool radius; stepdowns to (thickness - onion)."""
    moves: List[Move] = []
    final_depth = -(max(0.0, thickness_mm - onion_mm))
    if final_depth == 0.0:
        return moves

    r = tool.diameter_mm / 2.0
    rect = Rect(stock.x - r, stock.y - r, stock.w + 2 * r, stock.h + 2 * r)
    corners = [
        (rect.x, rect.y),
        (rect.x + rect.w, rect.y),
        (rect.x + rect.w, rect.y + rect.h),
        (rect.x, rect.y + rect.h),
        (rect.x, rect.y),
    ]

    for z in _z_passes(abs(final_depth), tool.max_stepdown_mm, material_max_step):
        z = -abs(z)
        moves += [Move("rapid", x=corners[0][0], y=corners[0][1], z=safe_z),
                  Move("set_feed", f=feed_z),
                  Move("plunge", z=z)]
        for (x, y) in corners[1:]:
            moves += [Move("set_feed", f=feed_xy), Move("cut", x=x, y=y, z=z)]
        moves += [Move("retract", z=safe_z)]
    return moves

def _tool(cfg: MergedConfig, tool_id: str) -> ToolPack:
    for _role, pack in cfg.tools.items():
        if pack.tool_id == tool_id:
            return pack
    return cfg.tools["finish"]

# ----------------------------
# Planner
# ----------------------------

def plan_toolpaths(cfg: MergedConfig, geo: Geometry) -> Dict[str, JobPlan]:
    safe_z = _safe_z(cfg)
    style = cfg.style
    material = cfg.material
    order = cfg.order

    jobs: Dict[str, JobPlan] = {}

    # Resolve tools from style stages
    rough_tool   = _tool(cfg, style.stages.rough_tool_id)
    finish_tool  = _tool(cfg, style.stages.finish_tool_id)
    profile_tool = _tool(cfg, style.stages.profile_tool_id)
    hinge_tool   = _tool(cfg, style.stages.hinge_tool_id)

    # Clamp feeds by machine
    rough_xy,  rough_z  = _clamp_feed(cfg, rough_tool.feed_xy_mm_min,   rough_tool.feed_z_mm_min)
    fin_xy,    fin_z    = _clamp_feed(cfg, (finish_tool.finish_xy_mm_min or finish_tool.feed_xy_mm_min), finish_tool.feed_z_mm_min)
    prof_xy,   prof_z   = _clamp_feed(cfg, profile_tool.feed_xy_mm_min, profile_tool.feed_z_mm_min)
    hinge_xy,  hinge_z  = _clamp_feed(cfg, hinge_tool.feed_xy_mm_min,   hinge_tool.feed_z_mm_min)

    # ---------------- FRONT: rough panel (raster, stepdown) ----------------
    front_rough_moves: List[Move] = []
    if order.tool_strategy == "multi":
        rough_depth = max(0.0, geo.panel_depth_mm - style.stages.rough_stock_to_leave_mm)
        if rough_depth > 0.0:
            front_rough_moves += _with_spindle_preamble(rough_tool)
            front_rough_moves += _raster_pocket(
                rect=geo.panel_rect,
                total_depth_mm=rough_depth,
                tool=rough_tool,
                material_max_step=material.max_stepdown_mm,
                feed_xy=rough_xy,
                feed_z=rough_z,
                safe_z=safe_z,
            )
    jobs["front_rough"] = JobPlan(name="front_rough", tool=rough_tool, moves=front_rough_moves, face="front")

    # ---------------- FRONT: finish contour (wall cleanup, stepdown) + FRONT anchors (spiral) ----------------
    front_finish_moves: List[Move] = []
    if geo.panel_depth_mm > 0.0:
        front_finish_moves += _with_spindle_preamble(finish_tool)
        front_finish_moves += _rect_contour_stepdown(
            rect=geo.panel_rect,
            total_depth_mm=geo.panel_depth_mm,
            tool=finish_tool,
            material_max_step=material.max_stepdown_mm,
            feed_xy=fin_xy,
            feed_z=fin_z,
            safe_z=safe_z,
        )

    if order.anchors_enabled and order.anchors_face == "front" and geo.anchors:
        if not front_finish_moves:
            front_finish_moves += _with_spindle_preamble(finish_tool)
        for c in geo.anchors:
            front_finish_moves += _spiral_pocket(
                cx=c.x, cy=c.y, radius_mm=c.r, total_depth_mm=c.depth_mm,
                tool=finish_tool, material_max_step=material.max_stepdown_mm,
                stepover_factor=finish_tool.stepover_factor,
                feed_xy=fin_xy, feed_z=fin_z, safe_z=safe_z,
                segments_per_rev=64, wall_skim=True,
            )
    jobs["front_finish"] = JobPlan(name="front_finish", tool=finish_tool, moves=front_finish_moves, face="front")

    # ---------------- FRONT: perimeter/profile with onion skin (outside offset, stepdown) ----------------
    onion = style.stages.onion_skin_mm if style.stages.onion_skin_mm else style.default_onion_skin_mm
    use_tabs  = bool(style.defaults_tabs)
    tab_w     = style.default_tab_width_mm if use_tabs else 0.0
    tab_h     = style.default_tab_height_mm if use_tabs else 0.0
    tab_count = style.default_tab_count if use_tabs else 0

    front_profile_moves: List[Move] = []
    front_profile_moves += _with_spindle_preamble(profile_tool)
    front_profile_moves += _perimeter_with_onion_skin(
        stock=geo.stock_rect,
        thickness_mm=order.thickness_mm,
        onion_mm=onion,
        tool=profile_tool,
        material_max_step=material.max_stepdown_mm,
        feed_xy=prof_xy,
        feed_z=prof_z,
        safe_z=safe_z,
        use_tabs=use_tabs,
        tab_count=tab_count,
        tab_w=tab_w,
        tab_h=tab_h,
    )
    jobs["front_profile"] = JobPlan(name="front_profile", tool=profile_tool, moves=front_profile_moves, face="front")

    # ---------------- BACK: hinges (spiral) ----------------
    back_hinges_moves: List[Move] = []
    if order.use_back_hinge_job and order.hinge_bores and geo.hinge_centers:
        back_hinges_moves += _with_spindle_preamble(hinge_tool)
        # For flip_about_Y_keep_left_fence: XY remain aligned for a rectangular part.
        for (hx, hy) in geo.hinge_centers:
            c = Circle(x=hx, y=hy, r=geo.hinge_diameter_mm / 2.0, depth_mm=geo.hinge_depth_mm)
            back_hinges_moves += _spiral_pocket(
                cx=c.x, cy=c.y, radius_mm=c.r, total_depth_mm=c.depth_mm,
                tool=hinge_tool, material_max_step=material.max_stepdown_mm,
                stepover_factor=max(0.20, min(hinge_tool.stepover_factor, 0.45)),
                feed_xy=hinge_xy, feed_z=hinge_z, safe_z=safe_z,
                segments_per_rev=96, wall_skim=True,
            )
    jobs["back_hinges"] = JobPlan(name="back_hinges", tool=hinge_tool, moves=back_hinges_moves, face="back")

    # ---------------- BACK: anchors (optional) ----------------
    back_anchors_moves: List[Move] = []
    if order.anchors_enabled and order.anchors_face == "back" and geo.anchors:
        back_anchors_moves += _with_spindle_preamble(finish_tool)
        for c in geo.anchors:
            back_anchors_moves += _spiral_pocket(
                cx=c.x, cy=c.y, radius_mm=c.r, total_depth_mm=c.depth_mm,
                tool=finish_tool, material_max_step=material.max_stepdown_mm,
                stepover_factor=finish_tool.stepover_factor,
                feed_xy=fin_xy, feed_z=fin_z, safe_z=safe_z,
                segments_per_rev=64, wall_skim=True,
            )
    jobs["back_anchors"] = JobPlan(name="back_anchors", tool=finish_tool, moves=back_anchors_moves, face="back")

    return jobs
