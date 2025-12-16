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
    """Layout item (shape with placement and feature)."""
    kind: str  # "shape" | "template"
    type: str  # Shape type: "Rect", "Circle", etc. or template name
    geometry: Geometry
    placement: Placement
    feature: Feature
    shape_id: str | None = None  # Optional identifier


@dataclass(frozen=True)
class LayoutAST:
    """Canonical layout AST."""
    sheet: Sheet
    items: tuple[Item, ...]
    config: dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def from_json(path: str) -> LayoutAST:
        """Parse layout from JSON file.

        Deferred to parsers.py to keep dataclasses pure.
        """
        from skills.mill_ui.v2.ast.parsers import parse_layout_json
        return parse_layout_json(path)
