"""Core utilities and constants for mill_ui.

This module provides:
- String constants for hint dictionary keys (prevents typos, enables autocomplete)
- Feature type and shape type constants
- Depth mode constants and utilities
- Geometry utilities (bounds calculation)
"""

from core.constants import (
    HintKeys,
    GeometryKeys,
    FeatureType,
    ShapeType,
    Side,
    DepthMode,
    TabKeys,
    MetadataKeys,
)
from core.geometry import (
    compute_shape_bounds,
    compute_shape_bounds_dict,
)

__all__ = [
    "HintKeys",
    "GeometryKeys",
    "FeatureType",
    "ShapeType",
    "Side",
    "DepthMode",
    "TabKeys",
    "MetadataKeys",
    "compute_shape_bounds",
    "compute_shape_bounds_dict",
]
