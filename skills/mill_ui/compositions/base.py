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
    """
    Expand template items into concrete shapes and ensure child IDs are UNIQUE per template.

    Why: seam-merging in the planner uses 'rect_id' to avoid pairing edges from the SAME rectangle.
    If different rectangles reuse the same child id (e.g., 'door:outer'), they will be treated
    as one part and internal seams won't merge. Prefixing with base template id fixes this.
    """
    out: List[Dict[str, Any]] = []
    for it in items:
        if it.get("kind") != "template":
            out.append(it)
            continue

        tname = it.get("type")
        params = it.get("params") or {}

        # placement center (applied to all children)
        center = None
        plc = it.get("placement") or {}
        v = plc.get("center_xy_mm")
        if isinstance(v, (list, tuple)) and len(v) == 2:
            center = (float(v[0]), float(v[1]))

        cls = REGISTRY.get(str(tname))
        if not cls:
            continue

        inst: TemplateBase = cls()
        built = inst.expand(params, sheet_thickness_mm)
        if center is not None:
            built = _offset_items(built, center)

        # --- ID threading: ALWAYS prefix child ids with the template's id ---
        base_id = (it.get("id") or "").strip()
        if base_id:
            for k, b in enumerate(built, start=1):
                child = (b.get("id") or "").strip()
                b["id"] = f"{base_id}:{child}" if child else f"{base_id}:{k}"
        else:
            # Ensure stable unique ids even if the template has no id
            for k, b in enumerate(built, start=1):
                if not b.get("id"):
                    b["id"] = f"item:{k}"

        out.extend(built)
    return out
