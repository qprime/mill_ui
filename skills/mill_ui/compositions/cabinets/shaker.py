# path: skills/mill_ui/compositions/cabinets/shaker.py
from __future__ import annotations
from typing import Dict, Any, List, Tuple
from skills.mill_ui.compositions.base import TemplateBase, register_template

def _rect(center: Tuple[float, float], w: float, h: float, feature: Dict[str, Any], id_: str = "") -> Dict[str, Any]:
    cx, cy = float(center[0]), float(center[1])
    return {
        "kind": "shape",
        "type": "Rect",
        "id": id_,
        "geometry": {"w_mm": float(w), "h_mm": float(h)},
        "placement": {"center_xy_mm": (cx, cy)},
        "feature": feature,
    }

def _circle(center: Tuple[float, float], d: float, feature: Dict[str, Any], id_: str = "") -> Dict[str, Any]:
    cx, cy = float(center[0]), float(center[1])
    return {
        "kind": "shape",
        "type": "Circle",
        "id": id_,
        "geometry": {"diameter_mm": float(d)},
        "placement": {"center_xy_mm": (cx, cy)},
        "feature": feature,
    }

@register_template("Shaker")
class Shaker(TemplateBase):
    def expand(self, params: Dict[str, Any], thickness_mm: float) -> List[Dict[str, Any]]:
        w = float(params.get("outer_w", 0.0))
        h = float(params.get("outer_h", 0.0))
        stile_w = float(params.get("stile_w", 0.0))
        rail_h  = float(params.get("rail_h", 0.0))
        panel_recess = float(params.get("panel_recess", 0.0))

        out: List[Dict[str, Any]] = []

        # Outer perimeter profile (through), offset handled by planner via side="outside"
        out.append(_rect((0.0, 0.0), w, h, {"type": "profile", "depth": "through", "side": "outside"}, id_="door:outer"))

        # Panel recess pocket
        if panel_recess > 0.0 and w > 2 * stile_w and h > 2 * rail_h:
            in_w = max(0.0, w - 2 * stile_w)
            in_h = max(0.0, h - 2 * rail_h)
            out.append(_rect((0.0, 0.0), in_w, in_h, {"type": "pocket", "depth_mm": panel_recess}, id_="door:panel"))

        # Optional anchor recess pockets in corners
        ar = params.get("anchor_recess") or {}
        if ar.get("enabled"):
            ar_d = float(ar.get("diameter_mm", 0.0))
            extra_depth = float(ar.get("extra_depth_mm", 0.0))
            offs = ar.get("offsets_mm") or {}
            off_l = float(offs.get("left", 0.0))
            off_r = float(offs.get("right", 0.0))
            off_t = float(offs.get("top", 0.0))
            off_b = float(offs.get("bottom", 0.0))
            hx = w * 0.5
            hy = h * 0.5
            pts = [
                (-(hx - off_l),  (hy - off_t)),
                ( (hx - off_r),  (hy - off_t)),
                (-(hx - off_l), -(hy - off_b)),
                ( (hx - off_r), -(hy - off_b)),
            ]
            for i, p in enumerate(pts, start=1):
                out.append(_circle(p, ar_d, {"type": "pocket", "depth_mm": extra_depth}, id_=f"door:anchor:{i}"))

        return out
