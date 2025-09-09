from __future__ import annotations
from typing import Dict, Type, List, Any, Optional
from skills.mill_ui_cq.shapes.base import ShapeSpec
from .base import TemplateBase

_registry: Dict[str, Type[TemplateBase]] = {}

def register_template(name: str):
    def _wrap(cls: Type[TemplateBase]):
        _registry[name] = cls
        return cls
    return _wrap

def _combine_placements(shape_placement: Optional[Dict[str, Any]], 
                       template_placement: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Combine shape placement (relative to template) with template placement (relative to sheet)."""
    if not template_placement:
        return shape_placement
    if not shape_placement:
        return template_placement
    
    # Both exist - need to combine them
    result = {}
    
    # Get template center
    tx, ty = 0, 0
    if "center_xy_mm" in template_placement:
        tx, ty = template_placement["center_xy_mm"]
    
    # Get shape's relative position
    sx, sy = 0, 0
    if "center_xy_mm" in shape_placement:
        sx, sy = shape_placement["center_xy_mm"]
    
    # Combine positions - shape position is relative to template center
    result["center_xy_mm"] = [tx + sx, ty + sy]
    
    # Handle rotation (additive)
    shape_rot = float(shape_placement.get("rotation_deg", 0.0)) if shape_placement else 0.0
    template_rot = float(template_placement.get("rotation_deg", 0.0)) if template_placement else 0.0
    if shape_rot or template_rot:
        result["rotation_deg"] = shape_rot + template_rot
    
    return result

def expand_template(name: str,
                    params: Dict[str, Any],
                    stock_thickness_mm: float,
                    template_placement: Optional[Dict[str, Any]],
                    template_id: Optional[str]) -> List[ShapeSpec]:
    cls = _registry.get(name)
    if not cls:
        raise ValueError(f"Unknown template: {name}")
    
    # Get specs from template (these have positions relative to template center [0,0])
    specs = cls().expand(params, stock_thickness_mm)
    
    # Apply template placement to each shape
    out: List[ShapeSpec] = []
    for i, s in enumerate(specs):
        # Combine the shape's relative placement with the template's absolute placement
        combined_placement = _combine_placements(s.placement, template_placement)
        
        # Create ID
        sid = s.id or (f"{template_id}:{i}" if template_id else None)
        if template_id and s.id:
            sid = f"{template_id}:{s.id}"
        
        # Create new spec with combined placement
        out.append(ShapeSpec(
            type=s.type,
            geometry=s.geometry,
            placement=combined_placement,
            feature=s.feature,
            id=sid
        ))
    
    return out

# Register built-ins
from .shaker import Shaker  # noqa: F401