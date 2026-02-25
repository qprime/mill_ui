from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Sheet:
    width_mm: float
    height_mm: float
    thickness_mm: float
    margin_mm: float = 0.0
    show_dimensions: bool = True
    material: str = "mdf"

    @property
    def working_width_mm(self) -> float:
        return self.width_mm - 2 * self.margin_mm

    @property
    def working_height_mm(self) -> float:
        return self.height_mm - 2 * self.margin_mm


@dataclass(frozen=True)
class Placement:
    center_xy_mm: tuple[float, float]


@dataclass(frozen=True)
class Geometry:
    data: dict[str, Any]


@dataclass(frozen=True)
class FeedsOverride:
    rpm: float | None = None
    feed_xy: float | None = None
    feed_z: float | None = None
    depth_per_pass: float | None = None
    stepover_percent: float | None = None


@dataclass(frozen=True)
class Feature:
    type: str
    depth_mm: float
    side: str | None = None
    is_through: bool = False
    corner_cleanup_tool_diameter_mm: float | None = None

    tab_count: int | None = None
    tab_height_mm: float | None = None
    tab_width_mm: float | None = None

    bevel_width_mm: float | None = None
    bevel_angle_deg: float | None = None
    bevel_inner_depth_mm: float | None = None

    chamfer_width_mm: float | None = None
    chamfer_angle_deg: float | None = None

    feeds_override: FeedsOverride | None = None


@dataclass(frozen=True)
class Item:
    kind: str
    type: str
    geometry: Geometry | None = None
    placement: Placement | None = None
    feature: Feature | None = None
    params: dict[str, Any] | None = None
    shape_id: str | None = None
    id: str | None = None
    label: str | None = None


@dataclass(frozen=True)
class LayoutAST:
    sheet: Sheet
    items: tuple[Item, ...]

    project: str | None = None
    kerf_width_mm: float | None = None
    cam: dict[str, Any] | None = None
    layout: dict[str, Any] | None = None
    config: dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def from_json(path: str) -> LayoutAST:
        from layout_ast.parsers import parse_layout_json

        return parse_layout_json(path)

    def to_json(self, path: str | None = None) -> str:
        from layout_ast.emitters import emit_layout_json

        return emit_layout_json(self, path)
