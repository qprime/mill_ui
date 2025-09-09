from __future__ import annotations
import cadquery as cq
from . import register_shape
from .base import ShapeBase

@register_shape("Rect")
class Rect(ShapeBase):
    def profile(self) -> cq.Workplane:
        g = self.spec.geometry
        w = float(g["w_mm"])
        h = float(g["h_mm"])
        r = float(g.get("corner_r_mm", 0.0))
        
        if r <= 0.0:
            # Simple rectangle
            return cq.Workplane("XY").rect(w, h)
        else:
            # Rounded rectangle - fillet the corners
            return cq.Workplane("XY").rect(w, h).vertices().fillet(r)