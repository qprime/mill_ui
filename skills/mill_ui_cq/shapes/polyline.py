from __future__ import annotations
import cadquery as cq
from . import register_shape
from .base import ShapeBase

@register_shape("Polyline")
class Polyline(ShapeBase):
    def profile(self) -> cq.Workplane:
        g = self.spec.geometry
        pts = [(float(x), float(y)) for x, y in g["points"]]
        closed = bool(g.get("closed", False))

        wp = cq.Workplane("XY").polyline(pts)

        # Area features (profile/pocket/engrave-as-trench) need a closed wire
        ftype = (self.spec.feature.get("type") or self.spec.feature.get("kind") or "profile").lower()
        if closed or ftype in ("profile", "pocket", "engrave"):
            wp = wp.close()

        return wp
