from __future__ import annotations
from typing import Dict, Any, List, Optional
from skills.mill_ui_cq.shapes.base import ShapeSpec

class TemplateBase:
    """
    Expand params -> list of ShapeSpec in template-local coords (center at 0,0).
    The engine applies template placement/rotation to each emitted shape.
    """
    def expand(self, params: Dict[str, Any], stock_thickness_mm: float) -> List[ShapeSpec]:
        raise NotImplementedError

def _apply_template_placement(specs: List[ShapeSpec],
                              placement: Optional[Dict[str, Any]],
                              template_id: Optional[str]) -> List[ShapeSpec]:
    out: List[ShapeSpec] = []
    for i, s in enumerate(specs):
        # Keep each shape's own placement; template placement is applied by the engine
        # We only propagate id namespace
        sid = s.id or (f"{template_id}:{i}" if template_id else None)
        out.append(ShapeSpec(s.type, s.geometry, s.placement, s.feature, sid))
    return out
