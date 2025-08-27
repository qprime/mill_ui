# path: cliff_ai/skills/cabinet_door_cam/compute_geometry.py
# desc: Pure math: derive border/panel rects, anchors, and hinge XY from merged config.
# api: compute_geometry(cfg: MergedConfig) -> Geometry
# tags: geometry, cabinet, door, anchors, hinges

from __future__ import annotations
from typing import List, Tuple
from skills.cabinet_door_cam.types import MergedConfig, Geometry, Rect, Circle
from skills.cabinet_door_cam.util import clamp, round_mm

def _border_width_mm(cfg: MergedConfig) -> float:
    s = cfg.style
    w = cfg.order.width_mm
    h = cfg.order.height_mm
    target = s.border_target_ratio * min(w, h)
    return round_mm(clamp(target, s.border_min_mm, s.border_max_mm))

def _panel_depth_mm(cfg: MergedConfig) -> float:
    o, s = cfg.order, cfg.style
    t = o.thickness_mm
    target = (o.panel_depth_mm if o.panel_depth_mm is not None
              else s.panel_target_of_thickness * t)
    d = clamp(target, s.panel_min_mm, s.panel_max_mm)
    # enforce safety floor
    d = max(d, s.panel_safety_floor_mm)
    return round_mm(d)

def _panel_and_border_rects(cfg: MergedConfig, bw: float) -> tuple[Rect, Rect, Rect]:
    W, H = cfg.order.width_mm, cfg.order.height_mm
    stock = Rect(0.0, 0.0, round_mm(W), round_mm(H))
    border = Rect(bw, bw, round_mm(W - 2*bw), round_mm(H - 2*bw))
    # clearance between border pocket and panel raster
    c = cfg.style.border_clearance_mm
    panel = Rect(border.x + c, border.y + c, round_mm(border.w - 2*c), round_mm(border.h - 2*c))
    return stock, border, panel

def _anchor_positions(cfg: MergedConfig, panel: Rect) -> List[Circle]:
    o, s = cfg.order, cfg.style
    if not o.anchors_enabled:
        return []
    d = o.anchors_diameter_mm
    r = d / 2.0
    inset_dx = o.anchors_inset_dx + s.anchors_clearance_mm
    inset_dy = o.anchors_inset_dy + s.anchors_clearance_mm
    # Four corners inset from panel rect (not stock)
    pts = [
        (panel.x + inset_dx,              panel.y + inset_dy),
        (panel.x + panel.w - inset_dx,    panel.y + inset_dy),
        (panel.x + inset_dx,              panel.y + panel.h - inset_dy),
        (panel.x + panel.w - inset_dx,    panel.y + panel.h - inset_dy),
    ]
    return [
        Circle(x=round_mm(px), y=round_mm(py), r=round_mm(r),
               depth_mm=round_mm(o.anchors_depth_mm))
        for (px, py) in pts
    ]

def _hinge_centers(cfg: MergedConfig, stock: Rect, bw: float) -> List[tuple[float, float]]:
    """Front-view semantics: hinge_side = left/right as seen from front.
    Centers lie at X along hinge stile centerline, Y at given offsets from edges."""
    if not cfg.order.hinge_bores:
        return []
    side = cfg.order.hinge_side  # "left" or "right"
    # place hinge cup centers along stile centerline at border center (half border width in from edge)
    stile_center_x = (bw / 2.0) if side == "left" else (stock.w - bw / 2.0)
    offsets = cfg.order.hinge_offsets_mm
    # If style's second offset is "mirror", compute mirror from far edge
    if len(offsets) == 2 and isinstance(offsets[1], str):
        # shouldn't happen from order; safe-guard for style semantics
        top = float(offsets[0])
        bottom = round_mm(stock.h - top)
        positions = [top, bottom]
    else:
        positions = [float(v) for v in offsets]
    centers = [(round_mm(stile_center_x), round_mm(y)) for y in positions]
    return centers

def compute_geometry(cfg: MergedConfig) -> Geometry:
    bw = _border_width_mm(cfg)
    stock, border, panel = _panel_and_border_rects(cfg, bw)
    panel_depth = _panel_depth_mm(cfg)
    anchors = _anchor_positions(cfg, panel)   # ← use panel instead of stock
    hinges = _hinge_centers(cfg, stock, bw)
    return Geometry(
        stock_rect=stock,
        border_rect=border,
        panel_rect=panel,
        panel_depth_mm=panel_depth,
        anchors=anchors,
        hinge_centers=hinges,
        hinge_diameter_mm=cfg.style.hinge_diameter_mm,
        hinge_depth_mm=cfg.style.hinge_depth_mm,
    )