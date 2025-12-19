"""Canonical LayoutAST dataclasses for v2.

All dimensions in millimeters.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Sheet:
    """Sheet stock specification."""
    width_mm: float
    height_mm: float
    thickness_mm: float


@dataclass(frozen=True)
class Placement:
    """Item placement on sheet."""
    center_xy_mm: tuple[float, float]


@dataclass(frozen=True)
class Geometry:
    """Shape geometry specification."""
    # Minimal representation - specific fields depend on shape type
    # Rect uses w_mm, h_mm
    # Circle uses diameter_mm or radius_mm
    data: dict[str, Any]


@dataclass(frozen=True)
class Feature:
    """CAM feature specification (profile, pocket, hole, engrave)."""
    type: str
    depth: str | float  # "through" or numeric depth_mm
    side: str | None = None  # "inside" | "outside" | "on" for profiles
    depth_mm: float | None = None  # Alternative to depth for numeric values


@dataclass(frozen=True)
class Item:
    """Layout item (shape or template).

    For shapes: kind="shape", requires geometry, placement, feature
    For templates: kind="template", requires params, id is optional
    """
    kind: str  # "shape" | "template"
    type: str  # Shape type: "Rect", "Circle", etc. or template name
    geometry: Geometry | None = None  # Required for shapes, unused for templates
    placement: Placement | None = None  # Required for shapes, optional for templates
    feature: Feature | None = None  # Required for shapes, unused for templates
    params: dict[str, Any] | None = None  # Required for templates, unused for shapes
    shape_id: str | None = None  # Optional identifier for shapes
    id: str | None = None  # Optional identifier for templates


@dataclass(frozen=True)
class LayoutAST:
    """Canonical layout AST.

    Captures both shape-based layouts and template-based layouts (v1 structure).
    """
    sheet: Sheet
    items: tuple[Item, ...]
    # Top-level configuration from v1 layouts
    project: str | None = None
    kerf_width_mm: float | None = None
    cam: dict[str, Any] | None = None
    layout: dict[str, Any] | None = None
    config: dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def from_json(path: str) -> LayoutAST:
        """Parse layout from JSON file.

        Deferred to parsers.py to keep dataclasses pure.
        """
        from layout_ast.parsers import parse_layout_json
        return parse_layout_json(path)

    def to_json(self, path: str | None = None) -> str:
        """Emit LayoutAST to canonical JSON.

        Deferred to emitters.py to keep dataclasses pure.

        Args:
            path: Optional path to write JSON file. If None, returns JSON string.

        Returns:
            Canonical JSON string
        """
        from layout_ast.emitters import emit_layout_json
        return emit_layout_json(self, path)
