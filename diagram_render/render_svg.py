from __future__ import annotations

from dataclasses import dataclass
from xml.etree import ElementTree as ET

from diagram_ir import DiagramIR, ViewportSpec, LayerIR
from diagram_ir.shapes import Shape, Rect, Line, Polyline, Circle, Text, Path
from export.dimensions import (
    place_on_rails,
    PlacedDimension,
    DimensionRequest,
)


@dataclass(frozen=True)
class DiagramTheme:
    background: str = "#1a1a1a"
    foreground: str = "#e8e8e8"
    style_map: dict[str, dict[str, str]] | None = None

    def get_style(self, token: str) -> dict[str, str]:
        if self.style_map and token in self.style_map:
            return self.style_map[token]
        return {"stroke": self.foreground, "fill": "none", "stroke-width": "1"}


DARK_DIAGRAM_THEME = DiagramTheme(
    background="#1a1a1a",
    foreground="#e8e8e8",
    style_map={
        "default": {"stroke": "#e8e8e8", "fill": "none", "stroke-width": "1"},
        "sheet-outline": {"stroke": "#6b8e7f", "fill": "none", "stroke-width": "1", "stroke-dasharray": "2,2"},
        "profile": {"stroke": "#e8e8e8", "fill": "none", "stroke-width": "2"},
        "pocket": {"stroke": "#6496c8", "fill": "#6496c8", "fill-opacity": "0.2", "stroke-width": "1.5"},
        "hole": {"stroke": "#e8e8e8", "fill": "none", "stroke-width": "1.5"},
        "engrave": {"stroke": "#888888", "fill": "none", "stroke-width": "0.25"},
        "waste": {"stroke": "#ff9500", "fill": "none", "stroke-width": "2", "stroke-dasharray": "8,4"},
        "toolpath": {"stroke": "#5ab9ea", "fill": "none", "stroke-width": "1", "stroke-dasharray": "4,2"},
        "dimension": {"stroke": "#5ab9ea", "fill": "none", "stroke-width": "1"},
        "dimension-text": {"fill": "#5ab9ea", "font-family": "monospace", "font-size": "10px"},
        "construction": {"stroke": "#6b8e7f", "fill": "none", "stroke-width": "0.5", "stroke-dasharray": "2,2"},
        "label": {"fill": "#ffcc00", "font-family": "monospace", "font-size": "8px", "font-weight": "bold"},
        "notes": {"fill": "#cccccc", "font-family": "monospace", "font-size": "10px"},
        "envelope": {"stroke": "#ff6b6b", "fill": "none", "stroke-width": "2"},
        "wasteboard": {"stroke": "#4ecdc4", "fill": "#4ecdc4", "fill-opacity": "0.1", "stroke-width": "1.5"},
        "effective-envelope": {"stroke": "#ffd93d", "fill": "none", "stroke-width": "1", "stroke-dasharray": "4,2"},
        "origin": {"stroke": "#ff6b6b", "fill": "#ff6b6b", "stroke-width": "1"},
        "centerline": {"stroke": "#6b8e7f", "fill": "none", "stroke-width": "0.5", "stroke-dasharray": "8,4"},
        "margin-zone": {"fill": "#6b8e7f", "fill-opacity": "0.15"},
    },
)

PRINT_DIAGRAM_THEME = DiagramTheme(
    background="#ffffff",
    foreground="#000000",
    style_map={
        "default": {"stroke": "#000000", "fill": "none", "stroke-width": "1"},
        "sheet-outline": {"stroke": "#666666", "fill": "none", "stroke-width": "1", "stroke-dasharray": "2,2"},
        "profile": {"stroke": "#000000", "fill": "none", "stroke-width": "2"},
        "pocket": {"stroke": "#000000", "fill": "#f0f0f0", "fill-opacity": "0.5", "stroke-width": "1.5"},
        "hole": {"stroke": "#000000", "fill": "none", "stroke-width": "1.5"},
        "engrave": {"stroke": "#000000", "fill": "none", "stroke-width": "0.25"},
        "waste": {"stroke": "#cc6600", "fill": "none", "stroke-width": "2", "stroke-dasharray": "8,4"},
        "toolpath": {"stroke": "#333333", "fill": "none", "stroke-width": "1", "stroke-dasharray": "4,2"},
        "dimension": {"stroke": "#333333", "fill": "none", "stroke-width": "1"},
        "dimension-text": {"fill": "#333333", "font-family": "monospace", "font-size": "10px"},
        "construction": {"stroke": "#666666", "fill": "none", "stroke-width": "0.5", "stroke-dasharray": "2,2"},
        "label": {"fill": "#333333", "font-family": "monospace", "font-size": "8px", "font-weight": "bold"},
        "notes": {"fill": "#000000", "font-family": "monospace", "font-size": "10px"},
        "envelope": {"stroke": "#cc0000", "fill": "none", "stroke-width": "2"},
        "wasteboard": {"stroke": "#009999", "fill": "#009999", "fill-opacity": "0.1", "stroke-width": "1.5"},
        "effective-envelope": {"stroke": "#cc9900", "fill": "none", "stroke-width": "1", "stroke-dasharray": "4,2"},
        "origin": {"stroke": "#cc0000", "fill": "#cc0000", "stroke-width": "1"},
        "centerline": {"stroke": "#666666", "fill": "none", "stroke-width": "0.5", "stroke-dasharray": "8,4"},
        "margin-zone": {"fill": "#666666", "fill-opacity": "0.15"},
    },
)

DIAGRAM_THEMES = {
    "dark": DARK_DIAGRAM_THEME,
    "print": PRINT_DIAGRAM_THEME,
}


def render_diagram_svg(
    diagram: DiagramIR,
    viewport: ViewportSpec | None = None,
    theme: DiagramTheme | str = "dark",
) -> str:
    if viewport is None:
        viewport = ViewportSpec()

    if isinstance(theme, str):
        theme = DIAGRAM_THEMES.get(theme, DARK_DIAGRAM_THEME)

    bounds = diagram.bounds
    padding = _compute_padding(bounds, viewport)

    if viewport.y_flip:
        transform_y = lambda y: bounds.y_max - (y - bounds.y_min)
    else:
        transform_y = lambda y: y

    viewbox_x = bounds.x_min - padding
    viewbox_y = bounds.y_min - padding
    viewbox_width = (bounds.x_max - bounds.x_min) + 2 * padding
    viewbox_height = (bounds.y_max - bounds.y_min) + 2 * padding

    svg = ET.Element(
        "svg",
        {
            "xmlns": "http://www.w3.org/2000/svg",
            "viewBox": f"{viewbox_x:.3f} {viewbox_y:.3f} {viewbox_width:.3f} {viewbox_height:.3f}",
            "width": f"{viewbox_width}mm",
            "height": f"{viewbox_height}mm",
        },
    )

    style = ET.SubElement(svg, "style")
    style.text = _generate_stylesheet(theme)

    ET.SubElement(
        svg,
        "rect",
        {
            "x": str(viewbox_x),
            "y": str(viewbox_y),
            "width": str(viewbox_width),
            "height": str(viewbox_height),
            "fill": theme.background,
        },
    )

    for layer in diagram.layers:
        if not layer.items:
            continue
        layer_group = ET.SubElement(svg, "g", {"id": layer.name, "class": _layer_name_to_class(layer.name)})
        for shape in layer.items:
            _render_shape(layer_group, shape, theme, transform_y, viewport.y_flip)

    if diagram.dims:
        _render_dimensions(svg, diagram.dims, bounds, padding, theme, transform_y)

    if diagram.notes:
        notes_group = ET.SubElement(svg, "g", {"id": "NOTES", "class": "notes"})
        for note in diagram.notes:
            _render_shape(notes_group, note, theme, transform_y, viewport.y_flip)

    ET.indent(svg, space="  ")
    return ET.tostring(svg, encoding="unicode")


def _compute_padding(bounds, viewport: ViewportSpec) -> float:
    if viewport.padding_percent is not None:
        width = bounds.x_max - bounds.x_min
        height = bounds.y_max - bounds.y_min
        return max(width, height) * viewport.padding_percent / 100.0
    return viewport.padding_mm


def _generate_stylesheet(theme: DiagramTheme) -> str:
    lines = []
    if theme.style_map:
        for token, styles in theme.style_map.items():
            class_name = token.replace("-", "-")
            props = "; ".join(f"{k}: {v}" for k, v in styles.items())
            lines.append(f".{class_name} {{ {props}; }}")
    return "\n".join(lines)


def _layer_name_to_class(name: str) -> str:
    return name.lower().replace("_", "-")


def _render_shape(parent: ET.Element, shape: Shape, theme: DiagramTheme,
                  transform_y, y_flip: bool) -> None:
    style_attrs = theme.get_style(shape.style_token)

    if isinstance(shape, Rect):
        y = transform_y(shape.y + shape.height) if y_flip else shape.y
        attrs = {
            "x": f"{shape.x:.3f}",
            "y": f"{y:.3f}",
            "width": f"{shape.width:.3f}",
            "height": f"{shape.height:.3f}",
            **{k: v for k, v in style_attrs.items()},
        }
        if shape.id:
            attrs["id"] = shape.id
        ET.SubElement(parent, "rect", attrs)

    elif isinstance(shape, Line):
        y1 = transform_y(shape.y1) if y_flip else shape.y1
        y2 = transform_y(shape.y2) if y_flip else shape.y2
        attrs = {
            "x1": f"{shape.x1:.3f}",
            "y1": f"{y1:.3f}",
            "x2": f"{shape.x2:.3f}",
            "y2": f"{y2:.3f}",
            **{k: v for k, v in style_attrs.items()},
        }
        if shape.id:
            attrs["id"] = shape.id
        ET.SubElement(parent, "line", attrs)

    elif isinstance(shape, Circle):
        cy = transform_y(shape.cy) if y_flip else shape.cy
        attrs = {
            "cx": f"{shape.cx:.3f}",
            "cy": f"{cy:.3f}",
            "r": f"{shape.radius:.3f}",
            **{k: v for k, v in style_attrs.items()},
        }
        if shape.id:
            attrs["id"] = shape.id
        ET.SubElement(parent, "circle", attrs)

    elif isinstance(shape, Polyline):
        points = shape.points
        if y_flip:
            points_str = " ".join(f"{p.x:.3f},{transform_y(p.y):.3f}" for p in points)
        else:
            points_str = " ".join(f"{p.x:.3f},{p.y:.3f}" for p in points)

        if shape.closed:
            if y_flip:
                d_parts = [f"M {points[0].x:.3f} {transform_y(points[0].y):.3f}"]
                for p in points[1:]:
                    d_parts.append(f"L {p.x:.3f} {transform_y(p.y):.3f}")
                d_parts.append("Z")
            else:
                d_parts = [f"M {points[0].x:.3f} {points[0].y:.3f}"]
                for p in points[1:]:
                    d_parts.append(f"L {p.x:.3f} {p.y:.3f}")
                d_parts.append("Z")
            attrs = {"d": " ".join(d_parts), **{k: v for k, v in style_attrs.items()}}
            if shape.id:
                attrs["id"] = shape.id
            ET.SubElement(parent, "path", attrs)
        else:
            attrs = {"points": points_str, **{k: v for k, v in style_attrs.items()}}
            if shape.id:
                attrs["id"] = shape.id
            ET.SubElement(parent, "polyline", attrs)

    elif isinstance(shape, Text):
        y = transform_y(shape.y) if y_flip else shape.y
        attrs = {
            "x": f"{shape.x:.3f}",
            "y": f"{y:.3f}",
            "text-anchor": shape.anchor,
            "dominant-baseline": shape.baseline,
            **{k: v for k, v in style_attrs.items()},
        }
        if shape.rotation != 0.0:
            attrs["transform"] = f"rotate({-shape.rotation if y_flip else shape.rotation} {shape.x:.3f} {y:.3f})"
        if shape.id:
            attrs["id"] = shape.id
        text_elem = ET.SubElement(parent, "text", attrs)
        text_elem.text = shape.content

    elif isinstance(shape, Path):
        attrs = {"d": shape.d, **{k: v for k, v in style_attrs.items()}}
        if shape.fill_rule:
            attrs["fill-rule"] = shape.fill_rule
        if shape.id:
            attrs["id"] = shape.id
        ET.SubElement(parent, "path", attrs)


def _render_dimensions(
    svg: ET.Element,
    dim_requests: tuple[DimensionRequest, ...],
    bounds,
    padding: float,
    theme: DiagramTheme,
    transform_y,
) -> None:
    dim_group = ET.SubElement(svg, "g", {"id": "DIMENSIONS", "class": "dimensions"})

    sheet_width = bounds.x_max - bounds.x_min
    offset_x = bounds.x_min
    offset_y = bounds.y_min

    placed = place_on_rails(
        list(dim_requests),
        sheet_width,
        offset_x,
        offset_y,
        margin=padding,
    )

    dim_style = theme.get_style("dimension")
    text_style = theme.get_style("dimension-text")
    stroke_color = dim_style.get("stroke", theme.foreground)

    for dim in placed:
        _render_placed_dimension(dim_group, dim, stroke_color, text_style, transform_y)


def _render_placed_dimension(
    parent: ET.Element,
    dim: PlacedDimension,
    stroke_color: str,
    text_style: dict[str, str],
    transform_y,
) -> None:
    if dim.orientation == "horizontal":
        x1, x2 = dim.a, dim.b
        y_anchor = transform_y(dim.anchor)
        y_dim = transform_y(dim.rail)

        _line_elem(parent, x1, y_anchor, x1, y_dim, stroke_color)
        _line_elem(parent, x2, y_anchor, x2, y_dim, stroke_color)
        _line_elem(parent, x1, y_dim, x2, y_dim, stroke_color)
        _arrow(parent, x1, y_dim, "left", stroke_color)
        _arrow(parent, x2, y_dim, "right", stroke_color)

        text_attrs = {
            "x": str((x1 + x2) / 2.0),
            "y": str(y_dim - 5.0),
            "text-anchor": "middle",
            "dominant-baseline": "middle",
            **{k: v for k, v in text_style.items()},
        }
        text_elem = ET.SubElement(parent, "text", text_attrs)
        text_elem.text = dim.text
    else:
        y1, y2 = transform_y(dim.a), transform_y(dim.b)
        x_anchor = dim.anchor
        x_dim = dim.rail

        _line_elem(parent, x_anchor, y1, x_dim, y1, stroke_color)
        _line_elem(parent, x_anchor, y2, x_dim, y2, stroke_color)
        _line_elem(parent, x_dim, y1, x_dim, y2, stroke_color)
        _arrow(parent, x_dim, y1, "up", stroke_color)
        _arrow(parent, x_dim, y2, "down", stroke_color)

        mid_y = (y1 + y2) / 2.0
        text_attrs = {
            "x": str(x_dim + 5.0),
            "y": str(mid_y),
            "text-anchor": "middle",
            "dominant-baseline": "middle",
            "transform": f"rotate(-90 {x_dim + 5.0} {mid_y})",
            **{k: v for k, v in text_style.items()},
        }
        text_elem = ET.SubElement(parent, "text", text_attrs)
        text_elem.text = dim.text


def _line_elem(parent: ET.Element, x1: float, y1: float, x2: float, y2: float, stroke: str) -> None:
    ET.SubElement(
        parent,
        "line",
        {
            "x1": str(x1),
            "y1": str(y1),
            "x2": str(x2),
            "y2": str(y2),
            "stroke": stroke,
            "stroke-width": "1",
        },
    )


def _arrow(parent: ET.Element, x: float, y: float, direction: str, color: str) -> None:
    size = 3.0
    if direction == "left":
        points = f"{x},{y} {x+size},{y-size} {x+size},{y+size}"
    elif direction == "right":
        points = f"{x},{y} {x-size},{y-size} {x-size},{y+size}"
    elif direction == "up":
        points = f"{x},{y} {x-size},{y+size} {x+size},{y+size}"
    elif direction == "down":
        points = f"{x},{y} {x-size},{y-size} {x+size},{y-size}"
    else:
        return
    ET.SubElement(parent, "polygon", {"points": points, "fill": color})


__all__ = [
    "render_diagram_svg",
    "DiagramTheme",
    "DARK_DIAGRAM_THEME",
    "PRINT_DIAGRAM_THEME",
    "DIAGRAM_THEMES",
]
