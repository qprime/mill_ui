from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Any, Optional
import cadquery as cq

@dataclass
class ShapeSpec:
    type: str
    geometry: Dict[str, Any]
    placement: Optional[Dict[str, Any]]
    feature: Dict[str, Any]
    id: Optional[str] = None

class ShapeBase:
    """Primitives return a 2D profile (wire/face) on XY at Z=0. Interpreter extrudes/cuts."""
    def __init__(self, spec: ShapeSpec):
        self.spec = spec

    def profile(self) -> cq.Workplane:
        raise NotImplementedError  # return Workplane with a pending 2D profile (no extrude)
