from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from layout_ast.layout import DogboneSpec, FeedsOverride


@dataclass(frozen=True)
class Panel:
    children: tuple[Any, ...] = ()
    id: str | None = None


@dataclass(frozen=True)
class Inset:
    amount_mm: float
    children: tuple[Any, ...] = ()


@dataclass(frozen=True)
class Frame:
    width_mm: float
    children: tuple[Any, ...] = ()


@dataclass(frozen=True)
class Grid:
    rows: int
    cols: int
    gap_mm: float = 0.0
    children: tuple[Any, ...] = ()


@dataclass(frozen=True)
class Cell:
    children: tuple[Any, ...] = ()
    inset_mm: float = 0.0


@dataclass(frozen=True)
class Split:
    rows: int
    cols: int
    rail_mm: float = 0.0
    mullion_mm: float = 0.0
    children: tuple[Any, ...] = ()


@dataclass(frozen=True)
class ComponentDef:
    name: str
    params: dict[str, Any] = field(default_factory=dict)
    body: Any = None


@dataclass(frozen=True)
class UseComponent:
    component_name: str
    args: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Place:
    layout: Any
    children: tuple[Any, ...] = ()


@dataclass(frozen=True)
class Rect:
    children: tuple[Any, ...] = ()
    feature: Any = None
    id: str | None = None
    label: str | None = None


@dataclass(frozen=True)
class Circle:
    diameter_mm: float | None = None
    radius_mm: float | None = None
    children: tuple[Any, ...] = ()
    feature: Any = None
    id: str | None = None
    label: str | None = None


@dataclass(frozen=True)
class RoundedRect:
    radius_mm: float
    children: tuple[Any, ...] = ()
    feature: Any = None
    id: str | None = None
    label: str | None = None
    corners: frozenset[str] | None = None


@dataclass(frozen=True)
class Line:
    orientation: str
    feature: Any = None
    id: str | None = None
    label: str | None = None


@dataclass(frozen=True)
class Polyline:
    points: tuple[tuple[float, float], ...]
    feature: Any = None
    id: str | None = None
    label: str | None = None

    def __post_init__(self):
        if len(self.points) < 2:
            raise ValueError(f"Polyline requires at least 2 points, got {len(self.points)}")

        for i, (x, y) in enumerate(self.points):
            if not (0.0 <= x <= 1.0):
                raise ValueError(f"Point {i} x-coordinate {x} out of range [0, 1]")
            if not (0.0 <= y <= 1.0):
                raise ValueError(f"Point {i} y-coordinate {y} out of range [0, 1]")


@dataclass(frozen=True)
class Keepout:
    children: tuple[Any, ...] = ()
    id: str | None = None


@dataclass(frozen=True)
class Edge:
    treatment_type: str
    rough_allowance_mm: float | None = None
    finish_allowance_mm: float | None = None
    radius_mm: float | None = None
    distance_mm: float | None = None
    id: str | None = None


@dataclass(frozen=True)
class SplinePath:
    points: tuple[tuple[float, float], ...]
    feature: Any = None
    tolerance_mm: float = 0.1
    id: str | None = None
    label: str | None = None

    def __post_init__(self):
        if len(self.points) < 2:
            raise ValueError(f"SplinePath requires at least 2 control points, got {len(self.points)}")

        for i, (x, y) in enumerate(self.points):
            if not (0.0 <= x <= 1.0):
                raise ValueError(f"SplinePath point {i} x-coordinate {x} out of range [0, 1]")
            if not (0.0 <= y <= 1.0):
                raise ValueError(f"SplinePath point {i} y-coordinate {y} out of range [0, 1]")

        if self.tolerance_mm <= 0:
            raise ValueError(f"SplinePath tolerance_mm must be positive, got {self.tolerance_mm}")


@dataclass(frozen=True)
class ProfileGen:
    side: str
    depth: str | float
    tab_count: int | None = None
    tab_height_mm: float | None = None
    tab_width_mm: float | None = None
    onion_skin_mm: float | None = None
    feeds_override: FeedsOverride | None = None


@dataclass(frozen=True)
class PocketGen:
    depth_mm: float
    feeds_override: FeedsOverride | None = None


@dataclass(frozen=True)
class RaisedPanelGen:
    border_width_mm: float
    border_depth_mm: float
    field_depth_mm: float


@dataclass(frozen=True)
class ChamferGen:
    width_mm: float
    depth_mm: float


@dataclass(frozen=True)
class RoundoverGen:
    radius_mm: float


@dataclass(frozen=True)
class WaveGen:
    wave_count: int
    amplitude_mm: float
    wavelength_mm: float
    groove_width_mm: float
    depth_mm: float


@dataclass(frozen=True)
class XPanelGen:
    bar_width_mm: float
    depth_mm: float


@dataclass(frozen=True)
class ShellGen:
    wall_mm: float
    interior: str
    depth: str | float
    children: tuple[Any, ...] = ()


@dataclass(frozen=True)
class SplitHorizontal:
    n: int
    gap_mm: float = 0.0
    children: tuple[Any, ...] = ()


@dataclass(frozen=True)
class SplitVertical:
    n: int
    gap_mm: float = 0.0
    children: tuple[Any, ...] = ()


@dataclass(frozen=True)
class SplitGrid:
    rows: int
    cols: int
    gap_mm: float = 0.0
    children: tuple[Any, ...] = ()


@dataclass(frozen=True)
class LinesGen:
    angle_deg: float
    spacing_mm: float
    line_width_mm: float
    depth_mm: float


@dataclass(frozen=True)
class ConcentricBorderGen:
    insets_mm: tuple[float, ...]
    groove_width_mm: float
    depth_mm: float


@dataclass(frozen=True)
class SplitHorizontalGaps:
    n: int
    gap_mm: float
    children: tuple[Any, ...] = ()


@dataclass(frozen=True)
class AtPosition:
    x_mm: float
    y_mm: float
    width_mm: float | None = None
    height_mm: float | None = None
    child: Any = None


@dataclass(frozen=True)
class Subtract:
    inner_inset_mm: float
    children: tuple[Any, ...] = ()


@dataclass(frozen=True)
class Arch:
    width_mm: float
    height_mm: float
    radius_mm: float
    children: tuple[Any, ...] = ()
    feature: Any = None
    id: str | None = None
    label: str | None = None


@dataclass(frozen=True)
class Polygon:
    points: tuple[tuple[float, float], ...]
    children: tuple[Any, ...] = ()
    feature: Any = None
    id: str | None = None
    label: str | None = None

    def __post_init__(self):
        if len(self.points) < 3:
            raise ValueError(f"Polygon requires at least 3 points, got {len(self.points)}")


@dataclass(frozen=True)
class Triangle:
    base_mm: float
    height_mm: float
    children: tuple[Any, ...] = ()
    feature: Any = None
    id: str | None = None
    label: str | None = None


@dataclass(frozen=True)
class HoleGridGen:
    spacing_mm: float
    diameter_mm: float
    depth: str | float
    pattern: str = "rectangular"
    inset_mm: float = 0.0
    align: str = "center"


@dataclass(frozen=True)
class MeasurementGridGen:
    unit: str = "metric"
    minor_spacing_mm: float | None = None
    major_spacing_mm: float | None = None
    minor_length_mm: float = 3.0
    major_length_mm: float = 6.0
    depth_mm: float = 0.5
    minor_ticks: bool = True
    labels: bool = False
    label_height_mm: float = 3.0
    label_offset_mm: float | None = None
    label_interval: int = 1
    label_start: int = 0


@dataclass(frozen=True)
class GridLinesGen:
    unit: str = "metric"
    spacing_mm: float | None = None
    minor_spacing_mm: float | None = None
    depth_mm: float = 0.3
    minor_lines: bool = False


@dataclass(frozen=True)
class MeasurementEdgeGen:
    edges: tuple[str, ...]
    unit: str = "metric"
    minor_spacing_mm: float | None = None
    major_spacing_mm: float | None = None
    minor_length_mm: float = 3.0
    major_length_mm: float = 6.0
    depth_mm: float = 0.3
    minor_ticks: bool = True
    labels: bool = False
    label_height_mm: float = 3.0
    label_offset_mm: float | None = None
    label_interval: int = 1
    label_start: int = 0


@dataclass(frozen=True)
class EngraveTextGen:
    text: str
    height_mm: float = 4.0
    depth_mm: float = 0.3
    font: str = "rowmans"
    alignment: str = "left"
    orientation: str = "horizontal"


@dataclass(frozen=True)
class TemplateDef:
    name: str
    params: dict[str, float | str] = field(default_factory=dict)
    body: Any = None


@dataclass(frozen=True)
class WasteCuts:
    min_width_mm: float
    min_height_mm: float
    margin_mm: float | None
    tab_count: int
    tab_height_mm: float
    strategy: str = "largest"


@dataclass(frozen=True)
class InterfaceConfig:
    joinery: str = "butt"
    finger_width_mm: float | None = None
    finger_count: int | None = None
    clearance_mm: float = 0.12
    dado_depth_mm: float | None = None
    inset_mm: float = 0.0
    receiving: str = "a"
    dogbone: DogboneSpec | bool | None = None


@dataclass(frozen=True)
class AssemblyDecl:
    type: str
    width_mm: float
    depth_mm: float
    height_mm: float
    thickness_mm: float
    joinery: str = "finger"
    finger_width_mm: float | None = None
    finger_count: int | None = None
    clearance_mm: float = 0.12
    interfaces: dict[str, InterfaceConfig | str] | None = None
    top: str | InterfaceConfig | None = None
    bottom: str | InterfaceConfig | None = "captured"
    children: tuple[Any, ...] = ()
    layout_gap_mm: float = 10.0
    show_labels: bool = False
    show_edge_colors: bool = False
    show_dimensions: bool = True
    cap_style: str = "between_sides"
    back: str | InterfaceConfig | None = None
    back_thickness_mm: float | None = None
    back_inset_mm: float = 0.0
    back_joinery: str | InterfaceConfig | None = None
    back_rabbet_depth_mm: float | None = None
    back_internal_support: bool = True
    fixed_shelves: int = 0
    shelf_joinery: str | InterfaceConfig = "captured"
    shelf_dado_depth_mm: float | None = None
    shelf_back_support: bool = False
    vertical_partitions: int = 0
    partition_joinery: str | InterfaceConfig = "captured"
    partition_dado_depth_mm: float | None = None
    grid: tuple[int, int] | None = None
    perimeter_joinery: str = "finger"
    internal_joinery: str = "half_lap"
    toe_kick_height_mm: float | None = None
    toe_kick_depth_mm: float | None = None
    toe_kick_style: str = "open"
    toe_kick_cover: bool = False


@dataclass(frozen=True)
class ResolvedRegion:
    x_min: float
    y_min: float
    x_max: float
    y_max: float

    @property
    def width(self) -> float:
        return self.x_max - self.x_min

    @property
    def height(self) -> float:
        return self.y_max - self.y_min

    @property
    def center(self) -> tuple[float, float]:
        return (
            (self.x_min + self.x_max) / 2,
            (self.y_min + self.y_max) / 2,
        )

    def inset(self, amount: float) -> ResolvedRegion:
        return ResolvedRegion(
            x_min=self.x_min + amount,
            y_min=self.y_min + amount,
            x_max=self.x_max - amount,
            y_max=self.y_max - amount,
        )

    def subdivide_grid(self, rows: int, cols: int, gap: float) -> list[ResolvedRegion]:
        return self.subdivide_split(rows, cols, gap, gap)

    def subdivide_split(self, rows: int, cols: int, rail_mm: float, mullion_mm: float) -> list[ResolvedRegion]:

        total_mullion = mullion_mm * (cols - 1) if cols > 1 else 0
        total_rail = rail_mm * (rows - 1) if rows > 1 else 0

        pane_width = (self.width - total_mullion) / cols
        pane_height = (self.height - total_rail) / rows

        panes = []
        for row in range(rows):
            for col in range(cols):
                x_offset = col * (pane_width + mullion_mm)
                y_offset = row * (pane_height + rail_mm)

                panes.append(
                    ResolvedRegion(
                        x_min=self.x_min + x_offset,
                        y_min=self.y_min + y_offset,
                        x_max=self.x_min + x_offset + pane_width,
                        y_max=self.y_min + y_offset + pane_height,
                    )
                )

        return panes


@dataclass(frozen=True)
class BeamFeatureDecl:
    feature_type: str
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class BeamLayerDecl:
    length_mm: float
    offset_mm: float = 0.0
    cutouts: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True)
class BeamDecl:
    name: str
    length_mm: float
    width_mm: float
    thickness_mm: float
    layers: int | tuple[BeamLayerDecl, ...]
    role: str | None = None
    face_features: tuple[BeamFeatureDecl, ...] = ()
    end_features: tuple[BeamFeatureDecl, ...] = ()
    edge_features: tuple[BeamFeatureDecl, ...] = ()
    show_labels: bool = False


@dataclass(frozen=True)
class SurfaceDecl:
    depth_mm: float
    passes: int = 1
    stepover_pct: float = 70.0
    direction: str = "x"
    margin_mm: float = 0.0
    cool_every: int = 0
    cool_dwell_s: float = 0.0


@dataclass(frozen=True)
class CompositionalLayoutAST:
    sheet: Any
    components: dict[str, ComponentDef] = field(default_factory=dict)
    root: Any = None
    project: str | None = None
    kerf_width_mm: float | None = None
    surface: SurfaceDecl | None = None
