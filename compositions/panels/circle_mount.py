# path: skills/mill_ui/compositions/panels/circle_mount.py
from __future__ import annotations
from typing import Dict, Any, List, Tuple
import math
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

@register_template("CircleMount")
class CircleMount(TemplateBase):
    def expand(self, params: Dict[str, Any], thickness_mm: float) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []

        # Disk (optional). If provided, cut a round blank with outside profile.
        disk = params.get("disk") or {}
        if "diameter_mm" in disk:
            d_disk = float(disk.get("diameter_mm", 0.0))
            if d_disk > 0:
                out.append(_circle((0.0, 0.0), d_disk, {"type": "profile", "depth": "through", "side": "outside"}, id_="mount:disk"))

        # Center port (required for a mount use-case)
        port = params.get("port") or {}
        d_port = float(port.get("diameter_mm", port.get("diameter", 0.0)))
        if d_port > 0:
            out.append(_circle((0.0, 0.0), d_port, {"type": "hole", "depth": "through"}, id_="mount:port"))

        # Optional bolt circle: through holes and optional counterbores
        bc = params.get("bolt_circle") or {}
        bc_d = float(bc.get("diameter_mm", 0.0))
        bc_n = int(bc.get("count", 0))
        thru_d = float(bc.get("through_d_mm", 0.0))
        cb_d = float(bc.get("counterbore_d_mm", 0.0))
        cb_depth = float(bc.get("counterbore_depth_mm", 0.0))
        if bc_d > 0 and bc_n > 0 and thru_d > 0:
            r = bc_d * 0.5
            for i in range(bc_n):
                t = 2.0 * math.pi * (i / bc_n)
                x = r * math.cos(t)
                y = r * math.sin(t)
                if cb_d > 0 and cb_depth > 0:
                    out.append(_circle((x, y), cb_d, {"type": "pocket", "depth_mm": cb_depth}, id_=f"mount:cb:{i+1}"))
                out.append(_circle((x, y), thru_d, {"type": "hole", "depth": "through"}, id_=f"mount:hole:{i+1}"))

        return out
