
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
    profile_depth: str | float = "through"
    profile_side: str = "outside"


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
    children: tuple[Any, ...] = ()
    feature: Any = None
    id: str | None = None


@dataclass(frozen=True)
class RoundedRect:
    radius_mm: float
    children: tuple[Any, ...] = ()
    feature: Any = None
    id: str | None = None


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
