from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ir.removal_intent import EdgeFeatureSpec, EdgeTreatment, ShapeGeometry
from layout_ast.layout import FeedsOverride, RestSpec


@dataclass(frozen=True)
class EdgeTreatmentInput:
    type: str
    radius_mm: float | None = None
    distance_mm: float | None = None
    rough_allowance_mm: float | None = None
    finish_allowance_mm: float | None = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"type": self.type}
        if self.radius_mm is not None:
            result["radius_mm"] = self.radius_mm
        if self.distance_mm is not None:
            result["distance_mm"] = self.distance_mm
        if self.rough_allowance_mm is not None:
            result["rough_allowance_mm"] = self.rough_allowance_mm
        if self.finish_allowance_mm is not None:
            result["finish_allowance_mm"] = self.finish_allowance_mm
        return result

    @classmethod
    def from_edge_treatment(cls, et: EdgeTreatment) -> EdgeTreatmentInput:
        return cls(
            type=et.type,
            radius_mm=et.radius_mm,
            distance_mm=et.distance_mm,
            rough_allowance_mm=et.rough_allowance_mm,
            finish_allowance_mm=et.finish_allowance_mm,
        )


@dataclass(frozen=True)
class KeepoutInput:
    x_min: float
    x_max: float
    y_min: float
    y_max: float
    reason: str = "keepout"

    def to_dict(self) -> dict[str, Any]:
        return {
            "x_min": self.x_min,
            "x_max": self.x_max,
            "y_min": self.y_min,
            "y_max": self.y_max,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class TabsInput:
    count: int
    height_mm: float
    width_mm: float | None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "count": self.count,
            "height_mm": self.height_mm,
        }
        if self.width_mm is not None:
            result["width_mm"] = self.width_mm
        return result


@dataclass(frozen=True)
class GeometryInput:
    shape: str
    geometry: ShapeGeometry = field(default_factory=ShapeGeometry)

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        if self.geometry.w_mm is not None:
            result["w_mm"] = self.geometry.w_mm
        if self.geometry.h_mm is not None:
            result["h_mm"] = self.geometry.h_mm
        if self.geometry.diameter_mm is not None:
            result["diameter_mm"] = self.geometry.diameter_mm
        if self.geometry.points is not None:
            result["points"] = [list(p) for p in self.geometry.points]
        if self.geometry.radius_mm is not None:
            result["radius_mm"] = self.geometry.radius_mm
        if self.geometry.radius_tl_mm is not None:
            result["radius_tl_mm"] = self.geometry.radius_tl_mm
        if self.geometry.radius_tr_mm is not None:
            result["radius_tr_mm"] = self.geometry.radius_tr_mm
        if self.geometry.radius_br_mm is not None:
            result["radius_br_mm"] = self.geometry.radius_br_mm
        if self.geometry.radius_bl_mm is not None:
            result["radius_bl_mm"] = self.geometry.radius_bl_mm
        if self.geometry.start is not None:
            result["start"] = list(self.geometry.start)
        if self.geometry.end is not None:
            result["end"] = list(self.geometry.end)
        return result


@dataclass(frozen=True)
class FeatureInput:
    id: str
    shape: str
    geometry: GeometryInput
    center_xy_mm: tuple[float, float]
    depth_mm: float
    start_depth_mm: float = 0.0
    side: str | None = None
    tabs: TabsInput | None = None
    keepouts: tuple[KeepoutInput, ...] = field(default_factory=tuple)
    rest: RestSpec | None = None
    edge_treatment: EdgeTreatmentInput | None = None
    feeds_override: FeedsOverride | None = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "id": self.id,
            "shape": self.shape,
            "geometry": self.geometry.to_dict(),
            "center_xy_mm": self.center_xy_mm,
            "depth_mm": self.depth_mm,
        }
        if self.start_depth_mm > 0.0:
            result["start_depth_mm"] = self.start_depth_mm
        if self.side is not None:
            result["side"] = self.side
        if self.tabs is not None:
            result["tabs"] = self.tabs.to_dict()
        if self.keepouts:
            result["keepouts"] = [k.to_dict() for k in self.keepouts]
        if self.rest is not None:
            result["rest"] = {
                "tool_diameter_mm": self.rest.tool_diameter_mm,
                "rough_allowance_mm": self.rest.rough_allowance_mm,
                "finish_allowance_mm": self.rest.finish_allowance_mm,
            }
        if self.edge_treatment is not None:
            result["edge_treatment"] = self.edge_treatment.to_dict()
        return result


@dataclass(frozen=True)
class CornerCleanupInput:
    id: str
    pocket_id: str
    shape: str
    geometry: GeometryInput
    center_xy_mm: tuple[float, float]
    corners: tuple[tuple[float, float], ...]
    corner_tool_diameter_mm: float
    depth_mm: float
    start_depth_mm: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "pocket_id": self.pocket_id,
            "shape": self.shape,
            "geometry": self.geometry.to_dict(),
            "center_xy_mm": self.center_xy_mm,
            "corners": list(self.corners),
            "corner_tool_diameter_mm": self.corner_tool_diameter_mm,
            "depth_mm": self.depth_mm,
            "start_depth_mm": self.start_depth_mm,
        }


@dataclass(frozen=True)
class DogboneInput:
    id: str
    pocket_id: str
    corners: tuple[tuple[float, float], ...]
    style: str
    tool_diameter_mm: float | None
    depth_mm: float
    start_depth_mm: float = 0.0
    overcut_mm: float = 0.0
    reference_point: tuple[float, float] | None = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "id": self.id,
            "pocket_id": self.pocket_id,
            "corners": list(self.corners),
            "style": self.style,
            "tool_diameter_mm": self.tool_diameter_mm,
            "depth_mm": self.depth_mm,
            "start_depth_mm": self.start_depth_mm,
            "overcut_mm": self.overcut_mm,
        }
        if self.reference_point is not None:
            result["reference_point"] = list(self.reference_point)
        return result


@dataclass(frozen=True)
class EdgeFeatureInput:
    id: str
    shape: str
    geometry: GeometryInput
    center_xy_mm: tuple[float, float]
    depth_mm: float
    start_depth_mm: float = 0.0
    side: str | None = None
    edge_feature: EdgeFeatureSpec | None = None

    def to_dict(self) -> dict[str, Any]:
        from ir.removal_intent import BevelSpec, ChamferSpec

        result: dict[str, Any] = {
            "id": self.id,
            "shape": self.shape,
            "geometry": self.geometry.to_dict(),
            "center_xy_mm": self.center_xy_mm,
            "depth_mm": self.depth_mm,
        }
        if self.start_depth_mm > 0.0:
            result["start_depth_mm"] = self.start_depth_mm
        if self.side is not None:
            result["side"] = self.side
        if self.edge_feature is not None:
            if isinstance(self.edge_feature, BevelSpec):
                result["edge_feature"] = {
                    "type": "bevel",
                    "width_mm": self.edge_feature.width_mm,
                    "angle_deg": self.edge_feature.angle_deg,
                    "inner_depth_mm": self.edge_feature.inner_depth_mm,
                }
            elif isinstance(self.edge_feature, ChamferSpec):
                result["edge_feature"] = {
                    "type": "chamfer",
                    "width_mm": self.edge_feature.width_mm,
                    "angle_deg": self.edge_feature.angle_deg,
                }
            else:
                raise TypeError(f"Unknown EdgeFeatureSpec type: {type(self.edge_feature)}")
        return result


@dataclass(frozen=True)
class PlannerInput:
    units: str = "mm"
    kerf_width_mm: float = 3.175
    min_channel_width_mm: float = 6.0
    profiles: tuple[FeatureInput, ...] = field(default_factory=tuple)
    pockets: tuple[FeatureInput, ...] = field(default_factory=tuple)
    holes: tuple[FeatureInput, ...] = field(default_factory=tuple)
    engraves: tuple[FeatureInput, ...] = field(default_factory=tuple)
    corner_cleanups: tuple[CornerCleanupInput, ...] = field(default_factory=tuple)
    dogbones: tuple[DogboneInput, ...] = field(default_factory=tuple)
    edge_features: tuple[EdgeFeatureInput, ...] = field(default_factory=tuple)
    keepouts: tuple[KeepoutInput, ...] = field(default_factory=tuple)

    def to_hints_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "units": self.units,
            "kerf_width_mm": self.kerf_width_mm,
            "min_channel_width_mm": self.min_channel_width_mm,
            "profiles": [p.to_dict() for p in self.profiles],
            "pockets": [p.to_dict() for p in self.pockets],
            "holes": [h.to_dict() for h in self.holes],
            "engraves": [e.to_dict() for e in self.engraves],
            "corner_cleanups": [c.to_dict() for c in self.corner_cleanups],
            "dogbones": [d.to_dict() for d in self.dogbones],
            "keepouts": [k.to_dict() for k in self.keepouts],
        }
        if self.edge_features:
            result["edge_features"] = [ef.to_dict() for ef in self.edge_features]
        return result

    @classmethod
    def from_hints_dict(cls, hints: dict[str, Any]) -> PlannerInput:
        def parse_keepout(k: dict[str, Any]) -> KeepoutInput:
            return KeepoutInput(
                x_min=float(k.get("x_min", 0.0)),
                x_max=float(k.get("x_max", 0.0)),
                y_min=float(k.get("y_min", 0.0)),
                y_max=float(k.get("y_max", 0.0)),
                reason=str(k.get("reason", "keepout")),
            )

        def parse_tabs(t: dict[str, Any] | None) -> TabsInput | None:
            if t is None:
                return None
            raw_width = t.get("width_mm")
            return TabsInput(
                count=int(t.get("count", 0)),
                height_mm=float(t.get("height_mm", 3.0)),
                width_mm=float(raw_width) if raw_width is not None else None,
            )

        def parse_geometry(g: dict[str, Any], shape: str) -> GeometryInput:
            points_raw = g.get("points")
            points: tuple[tuple[float, float], ...] | None = None
            if points_raw is not None:
                points = tuple((float(p[0]), float(p[1])) for p in points_raw)
            start_raw = g.get("start")
            start: tuple[float, float] | None = (
                (float(start_raw[0]), float(start_raw[1])) if start_raw is not None else None
            )
            end_raw = g.get("end")
            end: tuple[float, float] | None = (float(end_raw[0]), float(end_raw[1])) if end_raw is not None else None
            geom = ShapeGeometry(
                w_mm=float(g["w_mm"]) if "w_mm" in g else None,
                h_mm=float(g["h_mm"]) if "h_mm" in g else None,
                diameter_mm=float(g["diameter_mm"]) if "diameter_mm" in g else None,
                points=points,
                radius_mm=float(g["radius_mm"]) if "radius_mm" in g else None,
                radius_tl_mm=float(g["radius_tl_mm"]) if "radius_tl_mm" in g else None,
                radius_tr_mm=float(g["radius_tr_mm"]) if "radius_tr_mm" in g else None,
                radius_br_mm=float(g["radius_br_mm"]) if "radius_br_mm" in g else None,
                radius_bl_mm=float(g["radius_bl_mm"]) if "radius_bl_mm" in g else None,
                start=start,
                end=end,
            )
            return GeometryInput(shape=shape, geometry=geom)

        def parse_edge_treatment(et_raw: dict[str, Any] | None) -> EdgeTreatmentInput | None:
            if et_raw is None:
                return None
            return EdgeTreatmentInput(
                type=str(et_raw.get("type", "")),
                radius_mm=float(et_raw["radius_mm"]) if et_raw.get("radius_mm") is not None else None,
                distance_mm=float(et_raw["distance_mm"]) if et_raw.get("distance_mm") is not None else None,
                rough_allowance_mm=(
                    float(et_raw["rough_allowance_mm"]) if et_raw.get("rough_allowance_mm") is not None else None
                ),
                finish_allowance_mm=(
                    float(et_raw["finish_allowance_mm"]) if et_raw.get("finish_allowance_mm") is not None else None
                ),
            )

        def parse_rest(r: dict[str, Any] | None) -> RestSpec | None:
            if r is None:
                return None
            return RestSpec(
                tool_diameter_mm=float(r.get("tool_diameter_mm", 0.0)),
                rough_allowance_mm=float(r.get("rough_allowance_mm", 0.5)),
                finish_allowance_mm=float(r.get("finish_allowance_mm", 0.0)),
            )

        def parse_feature(f: dict[str, Any]) -> FeatureInput:
            shape = str(f.get("shape", "Rect"))
            geometry = parse_geometry(f.get("geometry", {}), shape)
            center = f.get("center_xy_mm", (0.0, 0.0))
            keepouts_raw = f.get("keepouts", [])
            keepouts = tuple(parse_keepout(k) for k in keepouts_raw)
            return FeatureInput(
                id=str(f.get("id", "")),
                shape=shape,
                geometry=geometry,
                center_xy_mm=(float(center[0]), float(center[1])),
                depth_mm=float(f.get("depth_mm", 0.0)),
                start_depth_mm=float(f.get("start_depth_mm", 0.0)),
                side=f.get("side"),
                tabs=parse_tabs(f.get("tabs")),
                keepouts=keepouts,
                rest=parse_rest(f.get("rest")),
                edge_treatment=parse_edge_treatment(f.get("edge_treatment")),
            )

        def parse_corner_cleanup(c: dict[str, Any]) -> CornerCleanupInput:
            shape = str(c.get("shape", "Rect"))
            geometry = parse_geometry(c.get("geometry", {}), shape)
            center = c.get("center_xy_mm", (0.0, 0.0))
            corners_raw = c.get("corners", [])
            corners = tuple((float(p[0]), float(p[1])) for p in corners_raw)
            return CornerCleanupInput(
                id=str(c.get("id", "")),
                pocket_id=str(c.get("pocket_id", "")),
                shape=shape,
                geometry=geometry,
                center_xy_mm=(float(center[0]), float(center[1])),
                corners=corners,
                corner_tool_diameter_mm=float(c.get("corner_tool_diameter_mm", 0.0)),
                depth_mm=float(c.get("depth_mm", 0.0)),
                start_depth_mm=float(c.get("start_depth_mm", 0.0)),
            )

        def parse_edge_feature_input(ef: dict[str, Any]) -> EdgeFeatureInput:
            from ir.removal_intent import BevelSpec, ChamferSpec

            shape = str(ef.get("shape", "Rect"))
            geometry = parse_geometry(ef.get("geometry", {}), shape)
            center = ef.get("center_xy_mm", (0.0, 0.0))
            ef_spec_raw = ef.get("edge_feature")
            edge_feature: EdgeFeatureSpec | None = None
            if isinstance(ef_spec_raw, dict):
                ef_type = ef_spec_raw.get("type")
                if ef_type == "bevel":
                    edge_feature = BevelSpec(
                        width_mm=float(ef_spec_raw.get("width_mm", 0.0)),
                        angle_deg=float(ef_spec_raw.get("angle_deg", 45.0)),
                        inner_depth_mm=float(ef_spec_raw.get("inner_depth_mm", 0.0)),
                    )
                elif ef_type == "chamfer":
                    edge_feature = ChamferSpec(
                        width_mm=float(ef_spec_raw.get("width_mm", 0.0)),
                        angle_deg=float(ef_spec_raw.get("angle_deg", 45.0)),
                    )
            return EdgeFeatureInput(
                id=str(ef.get("id", "")),
                shape=shape,
                geometry=geometry,
                center_xy_mm=(float(center[0]), float(center[1])),
                depth_mm=float(ef.get("depth_mm", 0.0)),
                start_depth_mm=float(ef.get("start_depth_mm", 0.0)),
                side=ef.get("side"),
                edge_feature=edge_feature,
            )

        def parse_dogbone(d: dict[str, Any]) -> DogboneInput:
            corners_raw = d.get("corners", [])
            corners = tuple((float(p[0]), float(p[1])) for p in corners_raw)
            ref_raw = d.get("reference_point")
            reference_point = (float(ref_raw[0]), float(ref_raw[1])) if ref_raw is not None else None
            return DogboneInput(
                id=str(d.get("id", "")),
                pocket_id=str(d.get("pocket_id", "")),
                corners=corners,
                style=str(d.get("style", "dogbone")),
                tool_diameter_mm=float(d["tool_diameter_mm"]) if d.get("tool_diameter_mm") is not None else None,
                depth_mm=float(d.get("depth_mm", 0.0)),
                start_depth_mm=float(d.get("start_depth_mm", 0.0)),
                overcut_mm=float(d.get("overcut_mm", 0.0)),
                reference_point=reference_point,
            )

        profiles = tuple(parse_feature(p) for p in hints.get("profiles", []))
        pockets = tuple(parse_feature(p) for p in hints.get("pockets", []))
        holes = tuple(parse_feature(h) for h in hints.get("holes", []))
        engraves = tuple(parse_feature(e) for e in hints.get("engraves", []))
        corner_cleanups = tuple(parse_corner_cleanup(c) for c in hints.get("corner_cleanups", []))
        dogbones = tuple(parse_dogbone(d) for d in hints.get("dogbones", []))
        edge_features = tuple(parse_edge_feature_input(ef) for ef in hints.get("edge_features", []))
        keepouts = tuple(parse_keepout(k) for k in hints.get("keepouts", []))

        return cls(
            units=str(hints.get("units", "mm")),
            kerf_width_mm=float(hints.get("kerf_width_mm", 3.175)),
            min_channel_width_mm=float(hints.get("min_channel_width_mm", 6.0)),
            profiles=profiles,
            pockets=pockets,
            holes=holes,
            engraves=engraves,
            corner_cleanups=corner_cleanups,
            dogbones=dogbones,
            edge_features=edge_features,
            keepouts=keepouts,
        )
