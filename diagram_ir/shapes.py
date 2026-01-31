from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence


@dataclass(frozen=True)
class Point2D:
    x: float
    y: float

    def __post_init__(self):
        if not isinstance(self.x, (int, float)) or not isinstance(self.y, (int, float)):
            raise ValueError(f"Point2D coordinates must be numeric, got x={self.x!r}, y={self.y!r}")
        if self.x != self.x or self.y != self.y:
            raise ValueError(f"Point2D coordinates must not be NaN")


@dataclass(frozen=True)
class Rect:
    x: float
    y: float
    width: float
    height: float
    style_token: str = "default"
    id: str | None = None

    def __post_init__(self):
        if self.width < 0:
            raise ValueError(f"Rect width must be non-negative, got {self.width}")
        if self.height < 0:
            raise ValueError(f"Rect height must be non-negative, got {self.height}")
        for coord in (self.x, self.y, self.width, self.height):
            if coord != coord:
                raise ValueError("Rect coordinates must not be NaN")


@dataclass(frozen=True)
class Line:
    x1: float
    y1: float
    x2: float
    y2: float
    style_token: str = "default"
    id: str | None = None

    def __post_init__(self):
        for coord in (self.x1, self.y1, self.x2, self.y2):
            if coord != coord:
                raise ValueError("Line coordinates must not be NaN")


@dataclass(frozen=True)
class Polyline:
    points: tuple[Point2D, ...]
    closed: bool = False
    style_token: str = "default"
    id: str | None = None

    def __post_init__(self):
        if not self.points:
            raise ValueError("Polyline must have at least one point")

    @classmethod
    def from_coords(cls, coords: Sequence[tuple[float, float]], closed: bool = False,
                    style_token: str = "default", id: str | None = None) -> Polyline:
        points = tuple(Point2D(x, y) for x, y in coords)
        return cls(points=points, closed=closed, style_token=style_token, id=id)


@dataclass(frozen=True)
class Circle:
    cx: float
    cy: float
    radius: float
    style_token: str = "default"
    id: str | None = None

    def __post_init__(self):
        if self.radius < 0:
            raise ValueError(f"Circle radius must be non-negative, got {self.radius}")
        for coord in (self.cx, self.cy, self.radius):
            if coord != coord:
                raise ValueError("Circle coordinates must not be NaN")


@dataclass(frozen=True)
class Text:
    x: float
    y: float
    content: str
    style_token: str = "default"
    anchor: str = "middle"
    baseline: str = "middle"
    rotation: float = 0.0
    id: str | None = None

    def __post_init__(self):
        for coord in (self.x, self.y, self.rotation):
            if coord != coord:
                raise ValueError("Text coordinates must not be NaN")


@dataclass(frozen=True)
class Path:
    d: str
    style_token: str = "default"
    fill_rule: str | None = None
    id: str | None = None


Shape = Rect | Line | Polyline | Circle | Text | Path


__all__ = [
    "Point2D",
    "Rect",
    "Line",
    "Polyline",
    "Circle",
    "Text",
    "Path",
    "Shape",
]
