from __future__ import annotations
from typing import Dict, Any, Optional, Tuple
from skills.mill_ui.cad.layout.panel import Panel

def _sf(v: Any, d: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return d

def rect_from_variant(geom: Dict[str, Any]) -> Optional[Dict[str, float]]:
    """
    Normalize various rectangle specs to {min_x,min_y,max_x,max_y} in mm.
    Accepted forms: explicit bounds; alt 'bounds'/'bbox'; point arrays; x/y/width/height.
    """
    if not isinstance(geom, dict):
        return None
    keys = ("min_x", "min_y", "max_x", "max_y")
    if all(k in geom for k in keys):
        return {k: _sf(geom[k]) for k in keys}
    alt = geom.get("bounds") or geom.get("bbox") or {}
    if isinstance(alt, dict):
        cand = {
            "min_x": alt.get("min_x") or alt.get("xmin"),
            "min_y": alt.get("min_y") or alt.get("ymin"),
            "max_x": alt.get("max_x") or alt.get("xmax"),
            "max_y": alt.get("max_y") or alt.get("ymax"),
        }
        if all(v is not None for v in cand.values()):
            return {k: _sf(v) for k, v in cand.items()}
    pts = geom.get("points")
    if isinstance(pts, list) and len(pts) >= 2:
        xs = [_sf(p[0]) for p in pts]
        ys = [_sf(p[1]) for p in pts]
        return {"min_x": min(xs), "min_y": min(ys), "max_x": max(xs), "max_y": max(ys)}
    if {"x", "y", "width", "height"} <= set(geom.keys()):
        x = _sf(geom["x"]); y = _sf(geom["y"])
        w = _sf(geom["width"]); h = _sf(geom["height"])
        return {"min_x": x, "min_y": y, "max_x": x + w, "max_y": y + h}
    return None

def circle_from_variant(g: Dict[str, Any]) -> Optional[Tuple[float, float, float]]:
    """
    (cx, cy, r) from {center_x/center_y,radius_mm} or {center:{x,y},diameter_mm}, etc.
    """
    if not isinstance(g, dict):
        return None
    if "center_x" in g and "center_y" in g:
        if "radius_mm" in g:
            return _sf(g["center_x"]), _sf(g["center_y"]), _sf(g["radius_mm"])
        if "diameter_mm" in g:
            return _sf(g["center_x"]), _sf(g["center_y"]), _sf(g["diameter_mm"]) / 2.0
    c = g.get("center")
    if isinstance(c, dict) and "x" in c and "y" in c:
        if "radius_mm" in g:
            return _sf(c["x"]), _sf(c["y"]), _sf(g["radius_mm"])
        if "diameter_mm" in g:
            return _sf(c["x"]), _sf(c["y"]), _sf(g["diameter_mm"]) / 2.0
    return None

def is_stock_boundary_rect(rect: Dict[str, float], panel: Panel, tol: float = 0.5) -> bool:
    """
    True if rect approximately equals the full sheet bounds [0,0]..[W,H] within tolerance.
    """
    return (
        abs(_sf(rect["min_x"]) - 0.0) <= tol and
        abs(_sf(rect["min_y"]) - 0.0) <= tol and
        abs(_sf(rect["max_x"]) - panel.width)  <= tol and
        abs(_sf(rect["max_y"]) - panel.height) <= tol
    )
