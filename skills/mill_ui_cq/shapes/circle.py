from __future__ import annotations
import cadquery as cq
from . import register_shape
from .base import ShapeBase

@register_shape("Circle")
class Circle(ShapeBase):
    def profile(self) -> cq.Workplane:
        d = float(self.spec.geometry["diameter_mm"])
        # Just return the circle wire - let the feature handler deal with it
        return cq.Workplane("XY").circle(d / 2.0)