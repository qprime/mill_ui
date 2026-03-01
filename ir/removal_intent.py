from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from domains.domain import Bounds2D
from layout_ast.layout import DogboneSpec, FeedsOverride, RestSpec


@dataclass(frozen=True)
class BevelSpec:
    width_mm: float
    angle_deg: float
    inner_depth_mm: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "bevel",
            "width_mm": self.width_mm,
            "angle_deg": self.angle_deg,
            "inner_depth_mm": self.inner_depth_mm,
        }


@dataclass(frozen=True)
class ChamferSpec:
    width_mm: float
    angle_deg: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "chamfer",
            "width_mm": self.width_mm,
            "angle_deg": self.angle_deg,
        }


EdgeFeatureSpec = BevelSpec | ChamferSpec


@dataclass(frozen=True)
class ShapeGeometry:
    w_mm: float | None = None
    h_mm: float | None = None
    diameter_mm: float | None = None
    points: tuple[tuple[float, float], ...] | None = None
    radius_mm: float | None = None
    radius_tl_mm: float | None = None
    radius_tr_mm: float | None = None
    radius_br_mm: float | None = None
    radius_bl_mm: float | None = None
    start: tuple[float, float] | None = None
    end: tuple[float, float] | None = None


@dataclass(frozen=True)
class DepthProfile:
    mode: str
    z_top: float
    z_bottom: float
    gradient_direction_deg: float | None = None
    v_angle_deg: float | None = None

    def __post_init__(self) -> None:
        valid_modes = ("constant", "linear_gradient", "v_carve")
        if self.mode not in valid_modes:
            raise ValueError(f"Invalid depth mode '{self.mode}'. Must be one of: {valid_modes}")
        if self.z_bottom > self.z_top:
            raise ValueError(f"z_bottom ({self.z_bottom}) > z_top ({self.z_top})")
        if self.mode == "linear_gradient" and self.gradient_direction_deg is None:
            raise ValueError("gradient_direction_deg required for linear_gradient mode")
        if self.mode == "v_carve" and self.v_angle_deg is None:
            raise ValueError("v_angle_deg required for v_carve mode")
        if (
            self.mode == "v_carve"
            and self.v_angle_deg is not None
            and (self.v_angle_deg <= 0 or self.v_angle_deg >= 180)
        ):
            raise ValueError(f"v_angle_deg must be between 0 and 180, got {self.v_angle_deg}")

    def depth_mm(self) -> float:
        return self.z_top - self.z_bottom

    @classmethod
    def constant(cls, z_top: float, z_bottom: float) -> DepthProfile:
        return cls(mode="constant", z_top=z_top, z_bottom=z_bottom)

    @classmethod
    def linear_gradient(
        cls,
        z_top: float,
        z_bottom: float,
        direction_deg: float,
    ) -> DepthProfile:
        return cls(
            mode="linear_gradient",
            z_top=z_top,
            z_bottom=z_bottom,
            gradient_direction_deg=direction_deg,
        )

    @classmethod
    def v_carve(cls, z_top: float, z_bottom: float, v_angle_deg: float) -> DepthProfile:
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
    width_mm: float | None


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
    hint_type: str = ""
    shape: str = ""
    side: str | None = None
    original_id: str | None = None
    shape_geometry: ShapeGeometry = field(default_factory=ShapeGeometry)
    corner_cleanup_tool_diameter_mm: float | None = None
    dogbone: DogboneSpec | None = None
    dogbone_corners: tuple[tuple[float, float], ...] | None = None
    dogbone_reference_point: tuple[float, float] | None = None
    rest: RestSpec | None = None
    edge_feature: EdgeFeatureSpec | None = None
    item_type: str | None = None
    feature_type: str | None = None
    shape_id: str | None = None
    allowance: Allowance = field(default_factory=Allowance)
    constraints: Constraints = field(default_factory=Constraints)
    feeds_override: FeedsOverride | None = None

    def depth_mm(self) -> float:
        return self.depth_profile.depth_mm()

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "region_id": self.region_id,
            "bounds": {
                "x_min": self.bounds.x_min,
                "x_max": self.bounds.x_max,
                "y_min": self.bounds.y_min,
                "y_max": self.bounds.y_max,
            },
            "depth_profile": self.depth_profile.to_dict(),
            "hint_type": self.hint_type,
            "shape": self.shape,
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
                }
                if self.constraints.tabs
                else None,
                "keepouts": len(self.constraints.keepouts),
                "islands": len(self.constraints.islands),
                "edge_treatment": {
                    "type": self.constraints.edge_treatment.type,
                    "radius_mm": self.constraints.edge_treatment.radius_mm,
                    "distance_mm": self.constraints.edge_treatment.distance_mm,
                    "rough_allowance_mm": self.constraints.edge_treatment.rough_allowance_mm,
                    "finish_allowance_mm": self.constraints.edge_treatment.finish_allowance_mm,
                }
                if self.constraints.edge_treatment
                else None,
                "tolerance_mm": self.constraints.tolerance_mm,
                "safe_z_mm": self.constraints.safe_z_mm,
            },
        }
        if self.side is not None:
            result["side"] = self.side
        if self.original_id is not None:
            result["original_id"] = self.original_id
        if self.corner_cleanup_tool_diameter_mm is not None:
            result["corner_cleanup_tool_diameter_mm"] = self.corner_cleanup_tool_diameter_mm
        if self.rest is not None:
            result["rest"] = {
                "tool_diameter_mm": self.rest.tool_diameter_mm,
                "rough_allowance_mm": self.rest.rough_allowance_mm,
                "finish_allowance_mm": self.rest.finish_allowance_mm,
            }
        if self.dogbone is not None:
            result["dogbone"] = {
                "style": self.dogbone.style,
                "diameter_mm": self.dogbone.diameter_mm,
                "overcut_mm": self.dogbone.overcut_mm,
            }
        if self.edge_feature is not None:
            result["edge_feature"] = self.edge_feature.to_dict()
        if self.item_type is not None:
            result["item_type"] = self.item_type
        if self.feature_type is not None:
            result["feature_type"] = self.feature_type
        if self.shape_id is not None:
            result["shape_id"] = self.shape_id
        return result


__all__ = [
    "Allowance",
    "BevelSpec",
    "Bounds2D",
    "ChamferSpec",
    "Constraints",
    "DepthProfile",
    "DogboneSpec",
    "EdgeFeatureSpec",
    "EdgeTreatment",
    "Island",
    "KeepoutRegion",
    "RemovalIntent",
    "RestSpec",
    "ShapeGeometry",
    "TabConstraint",
]
