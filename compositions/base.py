# path: skills/mill_ui/compositions/base.py
from __future__ import annotations
from typing import Dict, Any, List, Tuple
import copy

REGISTRY: Dict[str, type] = {}

def register_template(name: str):
    def deco(cls):
        REGISTRY[name] = cls
        return cls
    return deco

class TemplateBase:
    def expand(self, params: Dict[str, Any], thickness_mm: float) -> List[Dict[str, Any]]:
        raise NotImplementedError

def _offset_items(items: List[Dict[str, Any]], center_xy_mm: Tuple[float, float]) -> List[Dict[str, Any]]:
        cx, cy = float(center_xy_mm[0]), float(center_xy_mm[1])
        out: List[Dict[str, Any]] = []
        for it in items:
            j = copy.deepcopy(it)
            plc = j.get("placement") or {}
            inner = plc.get("center_xy_mm")
            if isinstance(inner, (list, tuple)) and len(inner) == 2:
                j.setdefault("placement", {})["center_xy_mm"] = (float(inner[0]) + cx, float(inner[1]) + cy)
            else:
                j["placement"] = {"center_xy_mm": (cx, cy)}
            out.append(j)
        return out

def resolve_templates(items: List[Dict[str, Any]], *, sheet_thickness_mm: float) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for it in items:
        if it.get("kind") != "template":
            out.append(it)
            continue
        tname = it.get("type")
        params = it.get("params") or {}
        center = None
        plc = it.get("placement") or {}
        if isinstance(plc.get("center_xy_mm"), (list, tuple)) and len(plc["center_xy_mm"]) == 2:
            center = (float(plc["center_xy_mm"][0]), float(plc["center_xy_mm"][1]))
        cls = REGISTRY.get(str(tname))
        if not cls:
            continue
        inst: TemplateBase = cls()
        built = inst.expand(params, sheet_thickness_mm)
        if center is not None:
            built = _offset_items(built, center)
        # id threading
        base_id = it.get("id") or ""
        if base_id:
            for k, b in enumerate(built):
                if "id" not in b or not b["id"]:
                    b["id"] = f"{base_id}:{k+1}"
        out.extend(built)
    return out
