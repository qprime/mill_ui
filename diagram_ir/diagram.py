from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from diagram_ir.dimensions import DimensionRequest
from diagram_ir.shapes import Circle, Line, Path, Polyline, Rect, Shape, Text
from ir.removal_intent import Bounds2D


@dataclass(frozen=True)
class LayerIR:
    name: str
    items: tuple[Shape, ...]

    def __post_init__(self):
        if not self.name:
            raise ValueError("Layer name cannot be empty")


@dataclass(frozen=True)
class DiagramIR:
    bounds: Bounds2D
    layers: tuple[LayerIR, ...]
    dims: tuple[DimensionRequest, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        self._validate_unique_layer_names()
        self._validate_shapes_in_bounds()

    def _validate_unique_layer_names(self) -> None:
        names = [layer.name for layer in self.layers]
        if len(names) != len(set(names)):
            seen = set()
            duplicates = []
            for name in names:
                if name in seen:
                    duplicates.append(name)
                seen.add(name)
            raise ValueError(f"Duplicate layer names: {duplicates}")

    def _validate_shapes_in_bounds(self) -> None:
        for layer in self.layers:
            for shape in layer.items:
                shape_bounds = _get_shape_bounds(shape)
                if shape_bounds is None:
                    continue
                x_min, y_min, x_max, y_max = shape_bounds
                if (
                    x_min < self.bounds.x_min - 0.1
                    or x_max > self.bounds.x_max + 0.1
                    or y_min < self.bounds.y_min - 0.1
                    or y_max > self.bounds.y_max + 0.1
                ):
                    shape_id = getattr(shape, "id", None) or "unnamed"
                    raise ValueError(
                        f"Shape '{shape_id}' in layer '{layer.name}' exceeds diagram bounds. "
                        f"Shape bounds: ({x_min:.1f}, {y_min:.1f}) to ({x_max:.1f}, {y_max:.1f}), "
                        f"Diagram bounds: ({self.bounds.x_min:.1f}, {self.bounds.y_min:.1f}) to "
                        f"({self.bounds.x_max:.1f}, {self.bounds.y_max:.1f})"
                    )


def _get_shape_bounds(shape: Shape) -> tuple[float, float, float, float] | None:
    if isinstance(shape, Rect):
        return (shape.x, shape.y, shape.x + shape.width, shape.y + shape.height)
    elif isinstance(shape, Line):
        return (min(shape.x1, shape.x2), min(shape.y1, shape.y2), max(shape.x1, shape.x2), max(shape.y1, shape.y2))
    elif isinstance(shape, Circle):
        return (shape.cx - shape.radius, shape.cy - shape.radius, shape.cx + shape.radius, shape.cy + shape.radius)
    elif isinstance(shape, Polyline):
        if not shape.points:
            return None
        xs = [p.x for p in shape.points]
        ys = [p.y for p in shape.points]
        return (min(xs), min(ys), max(xs), max(ys))
    elif isinstance(shape, (Text, Path)):
        return None
    return None


@dataclass(frozen=True)
class ViewportSpec:
    padding_mm: float = 10.0
    padding_percent: float | None = None
    scale: float | None = None
    fit_width: float | None = None
    fit_height: float | None = None
    y_flip: bool = True


def validate_diagram_ir(diagram: DiagramIR, available_style_tokens: set[str] | None = None) -> list[str]:
    errors: list[str] = []

    if available_style_tokens:
        for layer in diagram.layers:
            for shape in layer.items:
                token = getattr(shape, "style_token", "default")
                if token not in available_style_tokens:
                    errors.append(f"Unknown style_token '{token}' in layer '{layer.name}'")

    return errors


__all__ = [
    "DiagramIR",
    "LayerIR",
    "ViewportSpec",
    "validate_diagram_ir",
]
