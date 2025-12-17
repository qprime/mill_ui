"""RemovalIntent IR: Canonical representation for material removal operations.

All dimensions in millimeters. Z-axis: positive up, negative down into material.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Bounds2D:
    """2D bounding box in XY plane.

    Represents the planar extent of a removal region.
    """
    x_min: float
    x_max: float
    y_min: float
    y_max: float

    def __post_init__(self):
        """Validate bounds."""
        if self.x_max < self.x_min:
            raise ValueError(f"x_max ({self.x_max}) < x_min ({self.x_min})")
        if self.y_max < self.y_min:
            raise ValueError(f"y_max ({self.y_max}) < y_min ({self.y_min})")


@dataclass(frozen=True)
class Allowance:
    """Material allowance specification for removal operations.

    Defines how much material to leave or remove beyond nominal boundaries.
    """
    inside: float = 0.0  # Material to leave inside boundary (negative = remove more)
    outside: float = 0.0  # Material to leave outside boundary (negative = remove more)
    on: float = 0.0  # Material to leave on boundary (for 'on' side profiles)
    kerf_compensation: float = 0.0  # Tool kerf compensation (typically kerf_width_mm / 2)


@dataclass(frozen=True)
class TabConstraint:
    """Tab (holding bridge) specification."""
    count: int  # Number of tabs
    height_mm: float  # Tab height (extends up from z_bottom)
    width_mm: float  # Tab width along boundary


@dataclass(frozen=True)
class KeepoutRegion:
    """Region where toolpath must not enter."""
    bounds: Bounds2D
    reason: str = "keepout"  # Descriptive reason (e.g., "clamp zone", "fixture")


@dataclass(frozen=True)
class Island:
    """Material island within removal region (material to preserve)."""
    bounds: Bounds2D
    label: str | None = None


@dataclass(frozen=True)
class EdgeTreatment:
    """Edge treatment specification for finish operations.

    Describes decorative or functional edge modifications that affect
    toolpath planning (multi-pass, specialized bits, etc.).
    """
    type: str  # "fillet", "chamfer", "allowance"
    # For fillet/chamfer
    radius_mm: float | None = None  # Fillet radius
    distance_mm: float | None = None  # Chamfer distance
    # For allowance (multi-pass semantics)
    rough_allowance_mm: float | None = None  # Stock to leave for rough pass
    finish_allowance_mm: float | None = None  # Final allowance after finish pass


@dataclass(frozen=True)
class Constraints:
    """Constraints on removal operation."""
    tabs: TabConstraint | None = None
    keepouts: tuple[KeepoutRegion, ...] = field(default_factory=tuple)
    islands: tuple[Island, ...] = field(default_factory=tuple)
    edge_treatment: EdgeTreatment | None = None  # Edge finish/decorative hints
    tolerance_mm: float = 0.1  # Allowable deviation from nominal geometry
    safe_z_mm: float = 5.0  # Safe Z height for rapid moves


@dataclass(frozen=True)
class RemovalIntent:
    """Canonical specification for material removal.

    Represents *what* volume to remove, independent of *how* (toolpath strategy).
    This is the fundamental IR for CAM operations.
    """
    region_id: str  # Unique identifier for this removal region
    bounds: Bounds2D  # Planar extent of removal
    z_top: float  # Top Z coordinate (typically 0.0 for stock surface)
    z_bottom: float  # Bottom Z coordinate (negative for removal depth)
    allowance: Allowance = field(default_factory=Allowance)  # Material allowance
    constraints: Constraints = field(default_factory=Constraints)  # Operational constraints
    metadata: dict[str, Any] = field(default_factory=dict)  # Optional metadata (shape_id, feature type, etc.)

    def __post_init__(self):
        """Validate removal intent."""
        if self.z_bottom > self.z_top:
            raise ValueError(f"z_bottom ({self.z_bottom}) > z_top ({self.z_top})")

    def depth_mm(self) -> float:
        """Calculate removal depth."""
        return self.z_top - self.z_bottom

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for inspection/testing."""
        return {
            "region_id": self.region_id,
            "bounds": {
                "x_min": self.bounds.x_min,
                "x_max": self.bounds.x_max,
                "y_min": self.bounds.y_min,
                "y_max": self.bounds.y_max,
            },
            "z_top": self.z_top,
            "z_bottom": self.z_bottom,
            "depth_mm": self.depth_mm(),
            "allowance": {
                "inside": self.allowance.inside,
                "outside": self.allowance.outside,
                "on": self.allowance.on,
                "kerf_compensation": self.allowance.kerf_compensation,
            },
            "constraints": {
                "tabs": {
                    "count": self.constraints.tabs.count,
                    "height_mm": self.constraints.tabs.height_mm,
                    "width_mm": self.constraints.tabs.width_mm,
                } if self.constraints.tabs else None,
                "keepouts": len(self.constraints.keepouts),
                "islands": len(self.constraints.islands),
                "edge_treatment": {
                    "type": self.constraints.edge_treatment.type,
                    "radius_mm": self.constraints.edge_treatment.radius_mm,
                    "distance_mm": self.constraints.edge_treatment.distance_mm,
                    "rough_allowance_mm": self.constraints.edge_treatment.rough_allowance_mm,
                    "finish_allowance_mm": self.constraints.edge_treatment.finish_allowance_mm,
                } if self.constraints.edge_treatment else None,
                "tolerance_mm": self.constraints.tolerance_mm,
                "safe_z_mm": self.constraints.safe_z_mm,
            },
            "metadata": self.metadata,
        }
