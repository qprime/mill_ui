from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

VALID_GCODE_OUTPUT_MODES = ("per-operation", "per-tool")
VALID_FACES = ("front", "back")
DEFAULT_MIN_WEB_MM = 3.0


@dataclass(frozen=True)
class Sheet:
    width_mm: float
    height_mm: float
    thickness_mm: float
    margin_mm: float = 0.0
    show_dimensions: bool = True
    material: str = "mdf"
    gcode_output: str = "per-operation"
    min_web_mm: float = DEFAULT_MIN_WEB_MM

    def __post_init__(self) -> None:
        if self.gcode_output not in VALID_GCODE_OUTPUT_MODES:
            raise ValueError(f"Invalid gcode_output '{self.gcode_output}'. Must be one of: {VALID_GCODE_OUTPUT_MODES}")
        if self.min_web_mm < 0.0:
            raise ValueError(f"Sheet min_web_mm must be >= 0, got {self.min_web_mm}")
        from config.machine_loader import available_materials

        valid = available_materials()
        if self.material.lower() not in valid:
            raise ValueError(f"Unknown material {self.material!r}. Available materials in feeds.yml: {sorted(valid)}")

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
class DogboneSpec:
    style: str = "dogbone"
    diameter_mm: float | None = None
    overcut_mm: float = 0.0

    def __post_init__(self) -> None:
        valid_styles = ("dogbone", "t-bone_x", "t-bone_y")
        if self.style not in valid_styles:
            raise ValueError(f"Invalid dogbone style '{self.style}'. Must be one of: {valid_styles}")
        if self.diameter_mm is not None and self.diameter_mm <= 0.0:
            raise ValueError(f"dogbone diameter_mm must be positive, got {self.diameter_mm}")
        if self.overcut_mm < 0.0:
            raise ValueError(f"dogbone overcut_mm must be >= 0, got {self.overcut_mm}")


@dataclass(frozen=True)
class RestSpec:
    tool_diameter_mm: float
    rough_allowance_mm: float = 0.5
    finish_allowance_mm: float = 0.0

    def __post_init__(self) -> None:
        if self.tool_diameter_mm <= 0.0:
            raise ValueError(f"rest tool_diameter_mm must be positive, got {self.tool_diameter_mm}")
        if self.rough_allowance_mm < 0.0:
            raise ValueError(f"rest rough_allowance_mm must be >= 0, got {self.rough_allowance_mm}")
        if self.finish_allowance_mm < 0.0:
            raise ValueError(f"rest finish_allowance_mm must be >= 0, got {self.finish_allowance_mm}")


@dataclass(frozen=True)
class Feature:
    type: str
    depth_mm: float
    side: str | None = None
    face: str = "front"
    is_through: bool = False
    corner_cleanup_tool_diameter_mm: float | None = None
    dogbone: DogboneSpec | None = None
    dogbone_corners: tuple[tuple[float, float], ...] | None = None
    dogbone_reference_point: tuple[float, float] | None = None
    rest: RestSpec | None = None

    tab_count: int | None = None
    tab_height_mm: float | None = None
    tab_width_mm: float | None = None
    onion_skin_mm: float | None = None

    bevel_width_mm: float | None = None
    bevel_angle_deg: float | None = None
    bevel_inner_depth_mm: float | None = None

    chamfer_width_mm: float | None = None
    chamfer_angle_deg: float | None = None

    roundover_radius_mm: float | None = None

    feeds_override: FeedsOverride | None = None

    ramp_mm: float | None = None

    def __post_init__(self) -> None:
        if self.face not in VALID_FACES:
            raise ValueError(f"Invalid face '{self.face}'. Must be one of: {VALID_FACES}")


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

    def face_items(self, face: str) -> tuple[Item, ...]:
        return tuple(i for i in self.items if item_face(i) == face)

    @staticmethod
    def from_json(path: str) -> LayoutAST:
        from layout_ast.parsers import parse_layout_json

        return parse_layout_json(path)

    def to_json(self, path: str | None = None) -> str:
        from layout_ast.emitters import emit_layout_json

        return emit_layout_json(self, path)


def item_face(item: Item) -> str:
    return item.feature.face if item.feature is not None else "front"


_MIRROR_INVARIANT_KEYS = frozenset(
    {
        "w_mm",
        "h_mm",
        "diameter_mm",
        "radius_mm",
        "corner_radius_mm",
        "edge_treatment",
        "width_mm",
        "is_open",
        "spline_source",
        "spline_tolerance_mm",
    }
)

_MIRROR_RADIUS_SWAP = {
    "radius_tl_mm": "radius_bl_mm",
    "radius_bl_mm": "radius_tl_mm",
    "radius_tr_mm": "radius_br_mm",
    "radius_br_mm": "radius_tr_mm",
}


def mirror_item_about_x(item: Item, working_height_mm: float) -> Item:
    if item.feature is not None and (
        item.feature.dogbone_corners is not None or item.feature.dogbone_reference_point is not None
    ):
        raise ValueError(
            f"Cannot mirror item {item.shape_id!r}: dogbone_corners/dogbone_reference_point "
            f"hold absolute-frame coordinates that the back-face mirror does not remap"
        )

    placement = item.placement
    if placement is not None:
        cx, cy = placement.center_xy_mm
        placement = Placement(center_xy_mm=(cx, working_height_mm - cy))

    geometry = item.geometry
    if geometry is not None:
        geometry = Geometry(data=_mirror_geometry_data(geometry.data, working_height_mm, item.shape_id))

    return replace(item, placement=placement, geometry=geometry)


def _mirror_geometry_data(data: dict[str, Any], working_height_mm: float, shape_id: str | None) -> dict[str, Any]:
    mirrored: dict[str, Any] = {}
    for key, value in data.items():
        if key in _MIRROR_INVARIANT_KEYS:
            mirrored[key] = value
        elif key in _MIRROR_RADIUS_SWAP:
            mirrored[_MIRROR_RADIUS_SWAP[key]] = value
        elif key == "points":
            mirrored[key] = _mirror_ring(value)
        elif key == "holes":
            mirrored[key] = [_mirror_ring(ring) for ring in value]
        elif key in ("start", "end"):
            mirrored[key] = [value[0], -value[1]]
        elif key == "islands":
            mirrored[key] = [
                {
                    **bounds,
                    "y_min": working_height_mm - bounds["y_max"],
                    "y_max": working_height_mm - bounds["y_min"],
                }
                for bounds in value
            ]
        else:
            raise ValueError(
                f"Cannot mirror item {shape_id!r}: unrecognized geometry key {key!r} has no back-face mapping"
            )
    return mirrored


def _mirror_ring(points: Any) -> list[list[float]]:
    return [[point[0], -point[1]] for point in reversed(list(points))]
