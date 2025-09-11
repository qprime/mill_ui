# path: skills/mill_ui/cam/ops/pocket_region.py
from __future__ import annotations
from typing import Dict, Any, List, Tuple, Optional
from skills.mill_ui.cam.model.setup import Setup
from skills.mill_ui.cam.path.toolpath import (
    move_comment, move_set_rpm, move_set_feed, move_rapid, move_cut, move_retract
)

def _rect_bounds(center: Tuple[float, float], w: float, h: float) -> Tuple[float, float, float, float]:
    cx, cy = center
    return (cx - w * 0.5, cy - h * 0.5, cx + w * 0.5, cy + h * 0.5)

def _center_of(sub: Dict[str, Any], fallback: Tuple[float, float]) -> Tuple[float, float]:
    c = sub.get("center_xy_mm")
    if isinstance(c, (list, tuple)) and len(c) == 2:
        return float(c[0]), float(c[1])
    return fallback

def _interval_subtract(base: List[Tuple[float, float]], cut: Tuple[float, float]) -> List[Tuple[float, float]]:
    """Subtract one closed interval [a,b] from possibly-many base intervals. Returns merged result."""
    a, b = cut
    if a > b:
        a, b = b, a
    out: List[Tuple[float, float]] = []
    for (x0, x1) in base:
        # no overlap
        if x1 <= a or x0 >= b:
            out.append((x0, x1))
            continue
        # cut splits the interval
        if x0 < a:
            out.append((x0, max(x0, a)))
        if x1 > b:
            out.append((min(x1, b), x1))
    # normalize (merge touching)
    out.sort()
    merged: List[Tuple[float, float]] = []
    for seg in out:
        if not merged or seg[0] > merged[-1][1]:
            merged.append(seg)
        else:
            merged[-1] = (merged[-1][0], max(merged[-1][1], seg[1]))
    return merged

def pocket_region_rect_raster(
    region: Dict[str, Any],
    setup: Setup,
    *,
    default_center_xy: Optional[Tuple[float, float]],
    depth_mm: float,
    stepover_mm: float,
) -> List[dict]:
    """
    Raster pocket for a rectangular Region with rectangular holes.
    - region geometry:
        {"outer": {"type":"Rect","geometry":{"w_mm","h_mm"},"center_xy_mm"?:(x,y)},
         "holes": [{"type":"Rect","geometry":{"w_mm","h_mm"},"center_xy_mm"?:(x,y)}, ...]}
    - If sub 'center_xy_mm' missing, default_center_xy is used.
    """
    geom = region.get("geometry") or {}
    outer = geom.get("outer") or {}
    holes = geom.get("holes") or []

    if (outer.get("type") or "").lower() != "rect":
        raise NotImplementedError("pocket_region_rect_raster supports Rect outer only")

    oc = _center_of(outer, default_center_xy or (0.0, 0.0))
    og = outer.get("geometry") or {}
    ow = float(og.get("w_mm", 0.0))
    oh = float(og.get("h_mm", 0.0))
    ominx, ominy, omaxx, omaxy = _rect_bounds(oc, ow, oh)

    hole_rects: List[Tuple[float, float, float, float]] = []
    for h in holes:
        if (h.get("type") or "").lower() != "rect":
            raise NotImplementedError("holes must be Rect for pocket_region_rect_raster")
        hc = _center_of(h, default_center_xy or (0.0, 0.0))
        hg = h.get("geometry") or {}
        hw = float(hg.get("w_mm", 0.0))
        hh = float(hg.get("h_mm", 0.0))
        hole_rects.append(_rect_bounds(hc, hw, hh))

    z_target = -abs(float(depth_mm))
    so = max(0.1, float(stepover_mm))

    moves: List[dict] = []
    moves.append(move_comment("pocket_region_rect_raster"))
    moves.append(move_set_rpm(setup.tool.rpm))
    moves.append(move_set_feed(setup.tool.feed_xy))

    y = ominy
    left_to_right = True
    while y <= omaxy + 1e-9:
        # start with whole outer span
        spans: List[Tuple[float, float]] = [(ominx, omaxx)]
        # subtract any hole spans that intersect this scanline
        for (hx0, hy0, hx1, hy1) in hole_rects:
            if y < hy0 or y > hy1:
                continue
            spans = _interval_subtract(spans, (hx0, hx1))
            if not spans:
                break
        if spans:
            spans.sort()
            if not left_to_right:
                spans = [(b, a) for (a, b) in reversed(spans)]
            for (xs, xe) in spans:
                # exact start/end for the chosen direction
                x0, x1 = (xs, xe)
                moves.append(move_rapid(x=x0, y=y, z=setup.safe_z))
                moves.append(move_cut(z=z_target, feed=setup.tool.feed_z))
                moves.append(move_set_feed(setup.tool.feed_xy))
                moves.append(move_cut(x=x1, y=y))
                moves.append(move_retract(setup.safe_z))
        y += so
        left_to_right = not left_to_right

    return moves
