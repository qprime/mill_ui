# path: skills/mill_ui/compositions/base.py
"""Composable template framework used by mill_ui.

Design notes (optimized for Codex-generated templates):

- Treat every template like a UI tree: collect params into small dataclasses,
  build semantic regions, then emit primitive shapes via helpers.
- Prefer pure functions that return dictionaries; avoid mutating shared state.
- Keep helpers here so generated templates naturally follow the same pattern.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any, List, Tuple
import copy

REGISTRY: Dict[str, type] = {}

def register_template(name: str):
    def deco(cls):
        # Register with exact key and a lowercase alias so canonicalized
        # template types (e.g., from ingest) still resolve.
        REGISTRY[name] = cls
        REGISTRY.setdefault(name.lower(), cls)
        return cls
    return deco

class TemplateBase:
    def expand(self, params: Dict[str, Any], thickness_mm: float) -> List[Dict[str, Any]]:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Primitive helpers
# ---------------------------------------------------------------------------

def rect_shape(center_xy_mm: Tuple[float, float], *, width_mm: float, height_mm: float,
               feature: Dict[str, Any], shape_id: str) -> Dict[str, Any]:
    cx, cy = float(center_xy_mm[0]), float(center_xy_mm[1])
    return {
        "kind": "shape",
        "type": "Rect",
        "id": shape_id,
        "geometry": {"w_mm": float(width_mm), "h_mm": float(height_mm)},
        "placement": {"center_xy_mm": (cx, cy)},
        "feature": feature,
    }


def circle_shape(center_xy_mm: Tuple[float, float], *, diameter_mm: float,
                 feature: Dict[str, Any], shape_id: str) -> Dict[str, Any]:
    cx, cy = float(center_xy_mm[0]), float(center_xy_mm[1])
    return {
        "kind": "shape",
        "type": "Circle",
        "id": shape_id,
        "geometry": {"diameter_mm": float(diameter_mm)},
        "placement": {"center_xy_mm": (cx, cy)},
        "feature": feature,
    }


@dataclass(frozen=True)
class CenterRegion:
    """Simple centered rectangle region used by multiple templates."""

    width_mm: float
    height_mm: float

    @property
    def half_width(self) -> float:
        return float(self.width_mm) * 0.5

    @property
    def half_height(self) -> float:
        return float(self.height_mm) * 0.5

    def anchor_points(self, offsets: Dict[str, float]) -> List[Tuple[float, float]]:
        left = float(offsets.get("left", 0.0))
        right = float(offsets.get("right", 0.0))
        top = float(offsets.get("top", 0.0))
        bottom = float(offsets.get("bottom", 0.0))
        hx, hy = self.half_width, self.half_height
        return [
            (-hx + left,  +hy - top),
            (+hx - right, +hy - top),
            (-hx + left,  -hy + bottom),
            (+hx - right, -hy + bottom),
        ]

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
