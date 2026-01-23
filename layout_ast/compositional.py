
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


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


@dataclass(frozen=True)
class Circle:
    diameter_mm: float | None = None
    radius_mm: float | None = None
    children: tuple[Any, ...] = ()
    feature: Any = None
    id: str | None = None


@dataclass(frozen=True)
class RoundedRect:
    radius_mm: float
    children: tuple[Any, ...] = ()
    feature: Any = None
    id: str | None = None
    corners: frozenset[str] | None = None


@dataclass(frozen=True)
class Line:
    orientation: str
    feature: Any = None
    id: str | None = None


@dataclass(frozen=True)
class Polyline:
    points: tuple[tuple[float, float], ...]
    feature: Any = None
    id: str | None = None

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


# =============================================================================
# Generator AST Nodes (Stage 12: PML Generator Syntax)
# =============================================================================


@dataclass(frozen=True)
class ProfileGen:
    side: str
    depth: str | float
    tab_count: int | None = None
    tab_height_mm: float | None = None
    tab_width_mm: float | None = None


@dataclass(frozen=True)
class PocketGen:
    """Flat pocket generator node.

    Attributes:
        depth_mm: Depth of the pocket in mm
    """
    depth_mm: float


@dataclass(frozen=True)
class RaisedPanelGen:
    """Raised panel generator node.

    Attributes:
        border_width_mm: Width of the angled border
        border_depth_mm: Depth at outer edge of border
        field_depth_mm: Depth of center field
    """
    border_width_mm: float
    border_depth_mm: float
    field_depth_mm: float


@dataclass(frozen=True)
class ChamferGen:
    """Chamfer generator node.

    Attributes:
        width_mm: Horizontal width of chamfer
        depth_mm: Vertical depth of chamfer
    """
    width_mm: float
    depth_mm: float


@dataclass(frozen=True)
class WaveGen:
    """Wave pattern generator node.

    Attributes:
        wave_count: Number of waves
        amplitude_mm: Amplitude of waves
        wavelength_mm: Wavelength of waves
        groove_width_mm: Width of groove
        depth_mm: Depth of grooves
    """
    wave_count: int
    amplitude_mm: float
    wavelength_mm: float
    groove_width_mm: float
    depth_mm: float


@dataclass(frozen=True)
class XPanelGen:
    """X-panel generator node.

    Creates 4 triangular pockets forming an X pattern.

    Attributes:
        bar_width_mm: Width of the X bars (raised material between pockets)
        depth_mm: Depth of the triangular pockets
    """
    bar_width_mm: float
    depth_mm: float


@dataclass(frozen=True)
class SplitHorizontal:
    """Split domain horizontally into n rows.

    Attributes:
        n: Number of rows
        gap_mm: Gap between rows
        children: Content for each cell
    """
    n: int
    gap_mm: float = 0.0
    children: tuple[Any, ...] = ()


@dataclass(frozen=True)
class SplitVertical:
    """Split domain vertically into n columns.

    Attributes:
        n: Number of columns
        gap_mm: Gap between columns
        children: Content for each cell
    """
    n: int
    gap_mm: float = 0.0
    children: tuple[Any, ...] = ()


@dataclass(frozen=True)
class SplitGrid:
    """Split domain into a rows x cols grid.

    Attributes:
        rows: Number of rows
        cols: Number of columns
        gap_mm: Gap between cells
        children: Content for each cell
    """
    rows: int
    cols: int
    gap_mm: float = 0.0
    children: tuple[Any, ...] = ()


@dataclass(frozen=True)
class LinesGen:
    """Line pattern generator node.

    Attributes:
        angle_deg: Angle of lines (0=horizontal, 90=vertical, 45=diagonal)
        spacing_mm: Distance between line centers
        line_width_mm: Width of each line groove
        depth_mm: Depth of grooves
    """
    angle_deg: float
    spacing_mm: float
    line_width_mm: float
    depth_mm: float


@dataclass(frozen=True)
class ConcentricBorderGen:
    """Concentric border generator node.

    Attributes:
        insets_mm: Tuple of inset distances for each border ring
        groove_width_mm: Width of each groove
        depth_mm: Depth of grooves
    """
    insets_mm: tuple[float, ...]
    groove_width_mm: float
    depth_mm: float


@dataclass(frozen=True)
class SplitHorizontalGaps:
    """Split domain horizontally and apply children to gap regions.

    Used for louvers, shelf dados, and other patterns where the gaps
    between slats are the machined regions.

    Attributes:
        n: Number of slats (gaps = n - 1, but we treat this as n gaps)
        gap_mm: Height of each gap region
        children: Content applied to each gap
    """
    n: int
    gap_mm: float
    children: tuple[Any, ...] = ()


@dataclass(frozen=True)
class AtPosition:
    """Position a child at explicit coordinates with explicit size.

    Attributes:
        x_mm: X position (center of child)
        y_mm: Y position (center of child)
        width_mm: Width of the region (optional, uses parent width if None)
        height_mm: Height of the region (optional, uses parent height if None)
        child: The node to position
    """
    x_mm: float
    y_mm: float
    width_mm: float | None = None
    height_mm: float | None = None
    child: Any = None


@dataclass(frozen=True)
class Subtract:
    """Subtract inner region from outer region.

    The outer region is defined by the current region context.
    The inner region is defined by the first child.
    Remaining children are applied to the resulting ring domain.

    Attributes:
        inner_inset_mm: Inset from current region for inner boundary
        children: Operations to apply to the resulting ring
    """
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


@dataclass(frozen=True)
class Polygon:
    points: tuple[tuple[float, float], ...]
    children: tuple[Any, ...] = ()
    feature: Any = None
    id: str | None = None

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


@dataclass(frozen=True)
class HoleGridGen:
    spacing_mm: float
    diameter_mm: float
    depth: str | float
    pattern: str = "rectangular"
    inset_mm: float = 0.0
    align: str = "center"


@dataclass(frozen=True)
class TemplateDef:
    name: str
    params: dict[str, float | str] = field(default_factory=dict)
    body: Any = None


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

        total_gap_x = gap * (cols - 1) if cols > 1 else 0
        total_gap_y = gap * (rows - 1) if rows > 1 else 0

        cell_width = (self.width - total_gap_x) / cols
        cell_height = (self.height - total_gap_y) / rows

        cells = []
        for row in range(rows):
            for col in range(cols):
                x_offset = col * (cell_width + gap)
                y_offset = row * (cell_height + gap)

                cells.append(ResolvedRegion(
                    x_min=self.x_min + x_offset,
                    y_min=self.y_min + y_offset,
                    x_max=self.x_min + x_offset + cell_width,
                    y_max=self.y_min + y_offset + cell_height,
                ))

        return cells

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

                panes.append(ResolvedRegion(
                    x_min=self.x_min + x_offset,
                    y_min=self.y_min + y_offset,
                    x_max=self.x_min + x_offset + pane_width,
                    y_max=self.y_min + y_offset + pane_height,
                ))

        return panes


@dataclass(frozen=True)
class CompositionalLayoutAST:
    sheet: Any
    components: dict[str, ComponentDef] = field(default_factory=dict)
    root: Any = None
    project: str | None = None
    kerf_width_mm: float | None = None
