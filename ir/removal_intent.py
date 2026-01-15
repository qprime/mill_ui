
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Bounds2D:
    x_min: float
    x_max: float
    y_min: float
    y_max: float

    def __post_init__(self):
        if self.x_max < self.x_min:
            raise ValueError(f"x_max ({self.x_max}) < x_min ({self.x_min})")
        if self.y_max < self.y_min:
            raise ValueError(f"y_max ({self.y_max}) < y_min ({self.y_min})")


@dataclass(frozen=True)
class Allowance:
    inside: float = 0.0
    outside: float = 0.0
    on: float = 0.0
    kerf_compensation: float = 0.0


@dataclass(frozen=True)
class TabConstraint:
    count: int
    height_mm: float
    width_mm: float


@dataclass(frozen=True)
class KeepoutRegion:
    bounds: Bounds2D
    reason: str = "keepout"


@dataclass(frozen=True)
class Island:
    bounds: Bounds2D
    label: str | None = None


@dataclass(frozen=True)
class EdgeTreatment:
    type: str

    radius_mm: float | None = None
    distance_mm: float | None = None

    rough_allowance_mm: float | None = None
    finish_allowance_mm: float | None = None


@dataclass(frozen=True)
class Constraints:
    tabs: TabConstraint | None = None
    keepouts: tuple[KeepoutRegion, ...] = field(default_factory=tuple)
    islands: tuple[Island, ...] = field(default_factory=tuple)
    edge_treatment: EdgeTreatment | None = None
    tolerance_mm: float = 0.1
    safe_z_mm: float = 5.0


@dataclass(frozen=True)
class RemovalIntent:
    region_id: str
    bounds: Bounds2D
    z_top: float
    z_bottom: float
    allowance: Allowance = field(default_factory=Allowance)
    constraints: Constraints = field(default_factory=Constraints)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.z_bottom > self.z_top:
            raise ValueError(f"z_bottom ({self.z_bottom}) > z_top ({self.z_top})")

    def depth_mm(self) -> float:
        return self.z_top - self.z_bottom

    def to_dict(self) -> dict[str, Any]:
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
