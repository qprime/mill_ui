
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from domains.domain import Bounds2D


@dataclass(frozen=True)
class DepthProfile:
    mode: str
    z_top: float
    z_bottom: float
    gradient_direction_deg: float | None = None
    v_angle_deg: float | None = None

    def __post_init__(self):
        valid_modes = ("constant", "linear_gradient", "v_carve")
        if self.mode not in valid_modes:
            raise ValueError(f"Invalid depth mode '{self.mode}'. Must be one of: {valid_modes}")
        if self.z_bottom > self.z_top:
            raise ValueError(f"z_bottom ({self.z_bottom}) > z_top ({self.z_top})")
        if self.mode == "linear_gradient" and self.gradient_direction_deg is None:
            raise ValueError("gradient_direction_deg required for linear_gradient mode")
        if self.mode == "v_carve" and self.v_angle_deg is None:
            raise ValueError("v_angle_deg required for v_carve mode")
        if self.mode == "v_carve" and (self.v_angle_deg <= 0 or self.v_angle_deg >= 180):
            raise ValueError(f"v_angle_deg must be between 0 and 180, got {self.v_angle_deg}")

    def depth_mm(self) -> float:
        return self.z_top - self.z_bottom

    @classmethod
    def constant(cls, z_top: float, z_bottom: float) -> "DepthProfile":
        return cls(mode="constant", z_top=z_top, z_bottom=z_bottom)

    @classmethod
    def linear_gradient(
        cls,
        z_top: float,
        z_bottom: float,
        direction_deg: float,
    ) -> "DepthProfile":
        return cls(
            mode="linear_gradient",
            z_top=z_top,
            z_bottom=z_bottom,
            gradient_direction_deg=direction_deg,
        )

    @classmethod
    def v_carve(cls, z_top: float, z_bottom: float, v_angle_deg: float) -> "DepthProfile":
        return cls(
            mode="v_carve",
            z_top=z_top,
            z_bottom=z_bottom,
            v_angle_deg=v_angle_deg,
        )

    def to_dict(self) -> dict[str, Any]:
        result = {
            "mode": self.mode,
            "z_top": self.z_top,
            "z_bottom": self.z_bottom,
            "depth_mm": self.depth_mm(),
        }
        if self.gradient_direction_deg is not None:
            result["gradient_direction_deg"] = self.gradient_direction_deg
        if self.v_angle_deg is not None:
            result["v_angle_deg"] = self.v_angle_deg
        return result


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
    depth_profile: DepthProfile
    allowance: Allowance = field(default_factory=Allowance)
    constraints: Constraints = field(default_factory=Constraints)
    metadata: dict[str, Any] = field(default_factory=dict)

    def depth_mm(self) -> float:
        return self.depth_profile.depth_mm()

    def to_dict(self) -> dict[str, Any]:
        return {
            "region_id": self.region_id,
            "bounds": {
                "x_min": self.bounds.x_min,
                "x_max": self.bounds.x_max,
                "y_min": self.bounds.y_min,
                "y_max": self.bounds.y_max,
            },
            "depth_profile": self.depth_profile.to_dict(),
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
