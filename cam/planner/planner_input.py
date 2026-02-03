from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


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
    width_mm: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "count": self.count,
            "height_mm": self.height_mm,
            "width_mm": self.width_mm,
        }


@dataclass(frozen=True)
class GeometryInput:
    shape: str
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return dict(self.data)


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
    corner_cleanup_tool_diameter_mm: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

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
        if self.corner_cleanup_tool_diameter_mm is not None:
            result["corner_cleanup_tool_diameter_mm"] = self.corner_cleanup_tool_diameter_mm
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
class PlannerInput:
    units: str = "mm"
    kerf_width_mm: float = 3.175
    min_channel_width_mm: float = 6.0
    profiles: tuple[FeatureInput, ...] = field(default_factory=tuple)
    pockets: tuple[FeatureInput, ...] = field(default_factory=tuple)
    holes: tuple[FeatureInput, ...] = field(default_factory=tuple)
    engraves: tuple[FeatureInput, ...] = field(default_factory=tuple)
    corner_cleanups: tuple[CornerCleanupInput, ...] = field(default_factory=tuple)
    keepouts: tuple[KeepoutInput, ...] = field(default_factory=tuple)

    def to_hints_dict(self) -> dict[str, Any]:
        return {
            "units": self.units,
            "kerf_width_mm": self.kerf_width_mm,
            "min_channel_width_mm": self.min_channel_width_mm,
            "profiles": [p.to_dict() for p in self.profiles],
            "pockets": [p.to_dict() for p in self.pockets],
            "holes": [h.to_dict() for h in self.holes],
            "engraves": [e.to_dict() for e in self.engraves],
            "corner_cleanups": [c.to_dict() for c in self.corner_cleanups],
            "keepouts": [k.to_dict() for k in self.keepouts],
        }

    @classmethod
    def from_hints_dict(cls, hints: dict[str, Any]) -> "PlannerInput":
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
            return TabsInput(
                count=int(t.get("count", 0)),
                height_mm=float(t.get("height_mm", 3.0)),
                width_mm=float(t.get("width_mm", 10.0)),
            )

        def parse_geometry(g: dict[str, Any], shape: str) -> GeometryInput:
            return GeometryInput(shape=shape, data=dict(g))

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
                corner_cleanup_tool_diameter_mm=f.get("corner_cleanup_tool_diameter_mm"),
                metadata={},
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

        profiles = tuple(parse_feature(p) for p in hints.get("profiles", []))
        pockets = tuple(parse_feature(p) for p in hints.get("pockets", []))
        holes = tuple(parse_feature(h) for h in hints.get("holes", []))
        engraves = tuple(parse_feature(e) for e in hints.get("engraves", []))
        corner_cleanups = tuple(parse_corner_cleanup(c) for c in hints.get("corner_cleanups", []))
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
            keepouts=keepouts,
        )
