from __future__ import annotations
from typing import Dict, Type
import cadquery as cq
from .base import ShapeSpec, ShapeBase

_registry: Dict[str, Type[ShapeBase]] = {}

def register_shape(name: str):
    def _wrap(cls: Type[ShapeBase]):
        _registry[name] = cls
        return cls
    return _wrap

def resolve_profile(spec: ShapeSpec) -> cq.Workplane:
    cls = _registry.get(spec.type)
    if not cls:
        raise ValueError(f"Unknown shape type: {spec.type}")
    return cls(spec).profile()

# Register built-ins
from .circle import Circle   # noqa: F401
from .rect import Rect       # noqa: F401
from .polyline import Polyline  # noqa: F401
