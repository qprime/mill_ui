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
                sb = _get_shape_bounds(shape)
                if sb is None:
                    continue
                if (
                    sb.x_min < self.bounds.x_min - 0.1
                    or sb.x_max > self.bounds.x_max + 0.1
                    or sb.y_min < self.bounds.y_min - 0.1
                    or sb.y_max > self.bounds.y_max + 0.1
                ):
                    shape_id = getattr(shape, "id", None) or "unnamed"
                    raise ValueError(
                        f"Shape '{shape_id}' in layer '{layer.name}' exceeds diagram bounds. "
                        f"Shape bounds: ({sb.x_min:.1f}, {sb.y_min:.1f}) to ({sb.x_max:.1f}, {sb.y_max:.1f}), "
                        f"Diagram bounds: ({self.bounds.x_min:.1f}, {self.bounds.y_min:.1f}) to "
                        f"({self.bounds.x_max:.1f}, {self.bounds.y_max:.1f})"
                    )


def _get_shape_bounds(shape: Shape) -> Bounds2D | None:
    if isinstance(shape, Rect):
        return Bounds2D(x_min=shape.x, x_max=shape.x + shape.width, y_min=shape.y, y_max=shape.y + shape.height)
    elif isinstance(shape, Line):
        return Bounds2D(
            x_min=min(shape.x1, shape.x2),
            x_max=max(shape.x1, shape.x2),
            y_min=min(shape.y1, shape.y2),
            y_max=max(shape.y1, shape.y2),
        )
    elif isinstance(shape, Circle):
        return Bounds2D(
            x_min=shape.cx - shape.radius,
            x_max=shape.cx + shape.radius,
            y_min=shape.cy - shape.radius,
            y_max=shape.cy + shape.radius,
        )
    elif isinstance(shape, Polyline):
        if not shape.points:
            return None
        xs = [p.x for p in shape.points]
        ys = [p.y for p in shape.points]
        return Bounds2D(x_min=min(xs), x_max=max(xs), y_min=min(ys), y_max=max(ys))
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
