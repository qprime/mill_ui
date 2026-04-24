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


@dataclass(frozen=True)
class RoundoverSpec:
    radius_mm: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "roundover",
            "radius_mm": self.radius_mm,
        }


EdgeFeatureSpec = BevelSpec | ChamferSpec | RoundoverSpec


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
    image_path: str | None = None
    white_is_high: bool = True

    def __post_init__(self) -> None:
        valid_modes = ("constant", "linear_gradient", "v_carve", "heightfield")
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
        if self.mode == "heightfield" and self.image_path is None:
            raise ValueError("image_path required for heightfield mode")
        if self.mode != "heightfield" and self.image_path is not None:
            raise ValueError(f"image_path only valid for heightfield mode, got mode={self.mode!r}")

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

    @classmethod
    def heightfield(
        cls,
        z_top: float,
        z_bottom: float,
        image_path: str,
        white_is_high: bool = True,
    ) -> DepthProfile:
        return cls(
            mode="heightfield",
            z_top=z_top,
            z_bottom=z_bottom,
            image_path=image_path,
            white_is_high=white_is_high,
        )

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "mode": self.mode,
            "z_top": self.z_top,
            "z_bottom": self.z_bottom,
            "depth_mm": self.depth_mm(),
        }
        if self.gradient_direction_deg is not None:
            result["gradient_direction_deg"] = self.gradient_direction_deg
        if self.v_angle_deg is not None:
            result["v_angle_deg"] = self.v_angle_deg
        if self.mode == "heightfield":
            result["image_path"] = self.image_path
            result["white_is_high"] = self.white_is_high
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DepthProfile:
        mode = data["mode"]
        z_top = float(data["z_top"])
        z_bottom = float(data["z_bottom"])
        if mode == "constant":
            return cls.constant(z_top=z_top, z_bottom=z_bottom)
        if mode == "linear_gradient":
            return cls.linear_gradient(
                z_top=z_top,
                z_bottom=z_bottom,
                direction_deg=float(data["gradient_direction_deg"]),
            )
        if mode == "v_carve":
            return cls.v_carve(
                z_top=z_top,
                z_bottom=z_bottom,
                v_angle_deg=float(data["v_angle_deg"]),
            )
        if mode == "heightfield":
            if "image_path" not in data:
                raise ValueError("DepthProfile.from_dict: heightfield mode requires 'image_path'")
            if "white_is_high" not in data:
                raise ValueError("DepthProfile.from_dict: heightfield mode requires 'white_is_high'")
            return cls.heightfield(
                z_top=z_top,
                z_bottom=z_bottom,
                image_path=str(data["image_path"]),
                white_is_high=bool(data["white_is_high"]),
            )
        raise ValueError(f"Unknown depth profile mode: {mode!r}")


@dataclass(frozen=True)
class HeightfieldToolAssignment:
    tool_name: str
    role: str
    stepover_frac: float
    stepdown_mm: float | None = None
    angle_deg: float | None = None

    def __post_init__(self) -> None:
        from math import isfinite as _isfinite

        if self.role not in ("rough", "finish"):
            raise ValueError(f"HeightfieldToolAssignment: role must be 'rough' or 'finish', got {self.role!r}")
        if not self.tool_name:
            raise ValueError("HeightfieldToolAssignment: tool_name cannot be empty")
        if not (0.0 < self.stepover_frac <= 1.0):
            raise ValueError(f"HeightfieldToolAssignment: stepover_frac must be in (0, 1], got {self.stepover_frac}")
        if self.stepdown_mm is not None and self.stepdown_mm <= 0.0:
            raise ValueError(f"HeightfieldToolAssignment: stepdown_mm must be positive, got {self.stepdown_mm}")
        if self.role == "finish" and self.stepdown_mm is not None:
            raise ValueError("HeightfieldToolAssignment: stepdown_mm not valid for finish role (single-pass)")
        if self.role == "rough" and self.angle_deg is not None:
            raise ValueError("HeightfieldToolAssignment: angle_deg only valid for finish role")
        if self.role == "finish" and self.angle_deg is None:
            raise ValueError("HeightfieldToolAssignment: finish role requires angle_deg")
        if self.angle_deg is not None and not _isfinite(self.angle_deg):
            raise ValueError(f"HeightfieldToolAssignment: angle_deg must be finite, got {self.angle_deg}")
        if self.angle_deg is not None and not (0.0 <= self.angle_deg < 180.0):
            raise ValueError(f"HeightfieldToolAssignment: angle_deg must be in [0, 180), got {self.angle_deg}")

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "tool_name": self.tool_name,
            "role": self.role,
            "stepover_frac": self.stepover_frac,
        }
        if self.stepdown_mm is not None:
            result["stepdown_mm"] = self.stepdown_mm
        if self.role == "finish":
            result["angle_deg"] = self.angle_deg
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> HeightfieldToolAssignment:
        sd = data.get("stepdown_mm")
        role = str(data["role"])
        angle_raw = data.get("angle_deg")
        if role == "finish" and angle_raw is None:
            raise ValueError("HeightfieldToolAssignment.from_dict: finish role requires angle_deg")
        return cls(
            tool_name=str(data["tool_name"]),
            role=role,
            stepover_frac=float(data["stepover_frac"]),
            stepdown_mm=float(sd) if sd is not None else None,
            angle_deg=float(angle_raw) if angle_raw is not None else None,
        )


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
    onion_skin_mm: float | None = None
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
    ramp_mm: float | None = None
    heightfield_tools: tuple[HeightfieldToolAssignment, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.depth_profile.mode == "heightfield" and not self.heightfield_tools:
            raise ValueError(
                f"RemovalIntent '{self.region_id}': heightfield mode requires at least one tool assignment"
            )
        if self.depth_profile.mode != "heightfield" and self.heightfield_tools:
            raise ValueError(
                f"RemovalIntent '{self.region_id}': heightfield_tools only valid for heightfield mode, "
                f"got mode={self.depth_profile.mode!r}"
            )
        seen_names: set[str] = set()
        for t in self.heightfield_tools:
            if t.tool_name in seen_names:
                raise ValueError(f"RemovalIntent '{self.region_id}': duplicate heightfield tool name {t.tool_name!r}")
            seen_names.add(t.tool_name)

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
                "onion_skin_mm": self.constraints.onion_skin_mm,
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
        if self.dogbone_corners is not None:
            result["dogbone_corners"] = self.dogbone_corners
        if self.dogbone_reference_point is not None:
            result["dogbone_reference_point"] = self.dogbone_reference_point
        self._serialize_shape_geometry(result)
        self._serialize_feeds_override(result)
        if self.ramp_mm is not None:
            result["ramp_mm"] = self.ramp_mm
        if self.heightfield_tools:
            result["heightfield_tools"] = [t.to_dict() for t in self.heightfield_tools]
        return result

    def _serialize_shape_geometry(self, result: dict[str, Any]) -> None:
        geo: dict[str, Any] = {}
        for fld in (
            "w_mm",
            "h_mm",
            "diameter_mm",
            "points",
            "radius_mm",
            "radius_tl_mm",
            "radius_tr_mm",
            "radius_br_mm",
            "radius_bl_mm",
            "start",
            "end",
        ):
            val = getattr(self.shape_geometry, fld)
            if val is not None:
                geo[fld] = val
        if geo:
            result["shape_geometry"] = geo

    def _serialize_feeds_override(self, result: dict[str, Any]) -> None:
        if self.feeds_override is None:
            return
        feeds: dict[str, Any] = {}
        for fld in (
            "rpm",
            "feed_xy",
            "feed_z",
            "depth_per_pass",
            "stepover_percent",
        ):
            val = getattr(self.feeds_override, fld)
            if val is not None:
                feeds[fld] = val
        if feeds:
            result["feeds_override"] = feeds


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
    "HeightfieldToolAssignment",
    "Island",
    "KeepoutRegion",
    "RemovalIntent",
    "RestSpec",
    "RoundoverSpec",
    "ShapeGeometry",
    "TabConstraint",
]
