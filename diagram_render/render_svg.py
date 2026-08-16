from __future__ import annotations

from dataclasses import dataclass
from xml.etree import ElementTree as ET

from diagram_ir import DiagramIR, LayerIR, ViewportSpec
from diagram_ir.dimensions import (
    DimensionRequest,
    PlacedDimension,
    place_on_rails,
)
from diagram_ir.shapes import Circle, Image, Line, Path, Polyline, Rect, Shape, Text


@dataclass(frozen=True)
class StyleSpec:
    stroke: str | None = None
    stroke_width: float = 1.0
    stroke_dasharray: str | None = None
    fill: str | None = None
    fill_opacity: float = 1.0
    font_family: str | None = None
    font_size: str | None = None
    font_weight: str | None = None


@dataclass(frozen=True)
class DiagramTheme:
    background: str = "#1a1a1a"
    foreground: str = "#e8e8e8"
    style_map: dict[str, dict[str, str]] | None = None

    def get_style(self, token: str) -> dict[str, str]:
        if self.style_map and token in self.style_map:
            return self.style_map[token]
        return {"stroke": self.foreground, "fill": "none", "stroke-width": "1"}

    def style_attrs(self, token: str) -> dict[str, str]:
        return self.get_style(token)


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
        "table": {"stroke": "#5c4a32", "fill": "#c4a46c", "fill-opacity": "0.2", "stroke-width": "1"},
        "envelope": {"stroke": "#ff6b6b", "fill": "none", "stroke-width": "2"},
        "spoilboard": {"stroke": "none", "fill": "#4ecdc4", "fill-opacity": "0.1", "stroke-width": "0"},
        "effective-envelope": {"stroke": "#ffd93d", "fill": "none", "stroke-width": "1", "stroke-dasharray": "4,2"},
        "origin": {"stroke": "#ff6b6b", "fill": "#ff6b6b", "stroke-width": "1"},
        "centerline": {"stroke": "#6b8e7f", "fill": "none", "stroke-width": "0.5", "stroke-dasharray": "8,4"},
        "soft-limit": {"stroke": "#ff9500", "fill": "none", "stroke-width": "1.5", "stroke-dasharray": "6,3"},
        "t-track": {"stroke": "none", "fill": "#66cc88", "fill-opacity": "0.25", "stroke-width": "0"},
        "margin-zone": {"fill": "#6b8e7f", "fill-opacity": "0.15"},
        "legend": {"fill": "#cccccc", "font-family": "monospace", "font-size": "10px"},
        "title": {"fill": "#cccccc", "font-family": "monospace", "font-size": "14px", "font-weight": "bold"},
        "section-label": {"fill": "#5ab9ea", "font-family": "monospace", "font-size": "9px", "font-weight": "bold"},
        "callout-box": {"stroke": "#5ab9ea", "fill": "none", "stroke-width": "1"},
        "callout-detail": {"stroke": "#e8e8e8", "fill": "none", "stroke-width": "1.5"},
        "beam-assembly": {"stroke": "#e8e8e8", "fill": "none", "stroke-width": "1"},
        "beam-layer": {"stroke": "#6496c8", "fill": "#6496c8", "fill-opacity": "0.15", "stroke-width": "1"},
        "beam-splice": {"stroke": "#ff9500", "fill": "none", "stroke-width": "1.5", "stroke-dasharray": "4,2"},
        "title-subtitle": {"fill": "#cccccc", "font-family": "monospace", "font-size": "9px"},
        "callout-ref-text": {"fill": "#5ab9ea", "font-family": "monospace", "font-size": "7px"},
        "callout-dim-text": {"fill": "#5ab9ea", "font-family": "monospace", "font-size": "8px"},
        "beam-dim-text": {"fill": "#5ab9ea", "font-family": "monospace", "font-size": "8px"},
        "beam-segment-text": {"fill": "#5ab9ea", "font-family": "monospace", "font-size": "7px"},
        "heightfield-border": {"stroke": "#ffcc00", "fill": "none", "stroke-width": "1", "stroke-dasharray": "4,2"},
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
        "table": {"stroke": "#8b7355", "fill": "#d2b48c", "fill-opacity": "0.2", "stroke-width": "1"},
        "envelope": {"stroke": "#cc0000", "fill": "none", "stroke-width": "2"},
        "spoilboard": {"stroke": "none", "fill": "#009999", "fill-opacity": "0.1", "stroke-width": "0"},
        "effective-envelope": {"stroke": "#cc9900", "fill": "none", "stroke-width": "1", "stroke-dasharray": "4,2"},
        "origin": {"stroke": "#cc0000", "fill": "#cc0000", "stroke-width": "1"},
        "centerline": {"stroke": "#666666", "fill": "none", "stroke-width": "0.5", "stroke-dasharray": "8,4"},
        "soft-limit": {"stroke": "#cc6600", "fill": "none", "stroke-width": "1.5", "stroke-dasharray": "6,3"},
        "t-track": {"stroke": "none", "fill": "#339955", "fill-opacity": "0.2", "stroke-width": "0"},
        "margin-zone": {"fill": "#666666", "fill-opacity": "0.15"},
        "legend": {"fill": "#000000", "font-family": "monospace", "font-size": "10px"},
        "title": {"fill": "#000000", "font-family": "monospace", "font-size": "14px", "font-weight": "bold"},
        "section-label": {"fill": "#333333", "font-family": "monospace", "font-size": "9px", "font-weight": "bold"},
        "callout-box": {"stroke": "#333333", "fill": "none", "stroke-width": "1"},
        "callout-detail": {"stroke": "#000000", "fill": "none", "stroke-width": "1.5"},
        "beam-assembly": {"stroke": "#000000", "fill": "none", "stroke-width": "1"},
        "beam-layer": {"stroke": "#333333", "fill": "#e0e0e0", "fill-opacity": "0.3", "stroke-width": "1"},
        "beam-splice": {"stroke": "#cc6600", "fill": "none", "stroke-width": "1.5", "stroke-dasharray": "4,2"},
        "title-subtitle": {"fill": "#000000", "font-family": "monospace", "font-size": "9px"},
        "callout-ref-text": {"fill": "#333333", "font-family": "monospace", "font-size": "7px"},
        "callout-dim-text": {"fill": "#333333", "font-family": "monospace", "font-size": "8px"},
        "beam-dim-text": {"fill": "#333333", "font-family": "monospace", "font-size": "8px"},
        "beam-segment-text": {"fill": "#333333", "font-family": "monospace", "font-size": "7px"},
        "heightfield-border": {"stroke": "#cc6600", "fill": "none", "stroke-width": "1", "stroke-dasharray": "4,2"},
    },
)

DIAGRAM_THEMES = {
    "dark": DARK_DIAGRAM_THEME,
    "print": PRINT_DIAGRAM_THEME,
}

_CHROME_TOP = 40.0
_CHROME_RIGHT = 140.0
_CHROME_RIGHT_HEIGHT_THRESHOLD = 160.0

_DIMENSION_TEXT_OFFSET = 5.0
_ARROWHEAD_SIZE = 3.0

_TITLE_X_OFFSET = 10.0
_TITLE_Y_OFFSET = 14.0
_TITLE_UNITS_Y_OFFSET = 14.0

_LEGEND_OFFSET = 132.0
_LEGEND_LINE_HEIGHT = 16.0
_LEGEND_SWATCH_WIDTH = 15.0

_NOTES_X = 20.0
_NOTES_INDENT = 10.0
_NOTES_LINE_HEIGHT = 12.0
_NOTES_Y_OFFSET = 10.0
_NOTES_PADDING = 20.0
_NOTES_MIN_HEIGHT = 60.0

_CALLOUT_BOX_WIDTH = 100.0
_CALLOUT_BOX_HEIGHT = 70.0
_CALLOUT_BOX_SPACING = 15.0
_CALLOUT_SCALE = 3.0
_CALLOUT_START_Y_OFFSET = 180.0
_CALLOUT_MARGIN = 20.0
_CALLOUT_MARKER_RADIUS = 7.0

_BEAM_X = 20.0
_BEAM_Y_OFFSET = 10.0
_BEAM_DIAGRAM_WIDTH = 350.0
_BEAM_LAYER_HEIGHT = 14.0
_BEAM_HEADER_HEIGHT = 20.0
_BEAM_SPACING = 15.0


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

    def _transform_y_flip(y: float) -> float:
        return bounds.y_max - (y - bounds.y_min)

    def _transform_y_identity(y: float) -> float:
        return y

    transform_y = _transform_y_flip if viewport.y_flip else _transform_y_identity

    chrome_top = _CHROME_TOP
    chrome_bottom = _estimate_notes_height(diagram.metadata)
    beam_assembly_h = _estimate_beam_assembly_height(diagram.metadata)
    chrome_bottom += beam_assembly_h
    callout_h = _estimate_callout_height(diagram.metadata)
    chrome_right = _CHROME_RIGHT
    chrome_right_height = max(0.0, callout_h - _CHROME_RIGHT_HEIGHT_THRESHOLD)

    viewbox_x = bounds.x_min - padding
    viewbox_y = bounds.y_min - padding - chrome_top
    viewbox_width = (bounds.x_max - bounds.x_min) + padding + chrome_right
    viewbox_height = (bounds.y_max - bounds.y_min) + 2 * padding + chrome_top + chrome_bottom + chrome_right_height

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

    drawing_bottom = bounds.y_max + padding
    layer_names = {layer.name for layer in diagram.layers}
    _render_title_block(svg, viewbox_x, viewbox_y, theme, diagram.metadata.get("view_face", "front"))
    _render_legend(svg, viewbox_x, viewbox_y, viewbox_width, layer_names, theme)
    edge_profiles = diagram.metadata.get("edge_profiles", [])
    if edge_profiles:
        sheet_thickness = float(diagram.metadata.get("sheet_thickness", "19"))
        _render_edge_callouts(
            svg,
            viewbox_x,
            viewbox_y,
            viewbox_width,
            edge_profiles,
            sheet_thickness,
            theme,
            diagram.layers,
        )
    notes_top = drawing_bottom + chrome_right_height
    _render_notes_block(svg, notes_top, diagram.metadata, theme)
    beam_structures = diagram.metadata.get("beam_structures", [])
    if beam_structures:
        notes_h = _estimate_notes_height(diagram.metadata)
        beam_top = notes_top + notes_h
        _render_beam_assemblies(svg, beam_top, beam_structures, theme)

    ET.indent(svg, space="  ")
    return ET.tostring(svg, encoding="unicode")


def _estimate_notes_height(metadata: dict) -> float:
    lines = 2
    if metadata.get("feature_counts"):
        lines += 1
    depth_info = metadata.get("depth_info", [])
    if depth_info:
        lines += 1 + len(depth_info)
    hole_diameters = metadata.get("hole_diameters", [])
    if hole_diameters:
        lines += 1 + len(hole_diameters)
    part_inventory = metadata.get("part_inventory", [])
    if part_inventory:
        lines += 1 + len(part_inventory)
    edge_allowances = metadata.get("edge_allowances", [])
    if edge_allowances:
        lines += 1 + len(edge_allowances)
    return max(lines * _NOTES_LINE_HEIGHT + _NOTES_PADDING, _NOTES_MIN_HEIGHT)


def _compute_padding(bounds, viewport: ViewportSpec) -> float:
    if viewport.padding_percent is not None:
        width = bounds.x_max - bounds.x_min
        height = bounds.y_max - bounds.y_min
        return float(max(width, height)) * viewport.padding_percent / 100.0
    return viewport.padding_mm


def _generate_stylesheet(theme: DiagramTheme) -> str:
    lines = []
    if theme.style_map:
        for token, styles in theme.style_map.items():
            class_name = token
            props = "; ".join(f"{k}: {v}" for k, v in styles.items())
            lines.append(f".{class_name} {{ {props}; }}")
    return "\n".join(lines)


def _layer_name_to_class(name: str) -> str:
    return name.lower().replace("_", "-")


def _render_shape(parent: ET.Element, shape: Shape, theme: DiagramTheme, transform_y, y_flip: bool) -> None:  # noqa: C901 — shape-type dispatcher
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

    elif isinstance(shape, Image):
        y = transform_y(shape.y + shape.height) if y_flip else shape.y
        attrs = {
            "x": f"{shape.x:.3f}",
            "y": f"{y:.3f}",
            "width": f"{shape.width:.3f}",
            "height": f"{shape.height:.3f}",
            "href": shape.href,
            "opacity": f"{shape.opacity:.3f}",
            "preserveAspectRatio": "none",
        }
        if shape.id:
            attrs["id"] = shape.id
        ET.SubElement(parent, "image", attrs)


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
            "y": str(y_dim - _DIMENSION_TEXT_OFFSET),
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
            "x": str(x_dim + _DIMENSION_TEXT_OFFSET),
            "y": str(mid_y),
            "text-anchor": "middle",
            "dominant-baseline": "middle",
            "transform": f"rotate(-90 {x_dim + _DIMENSION_TEXT_OFFSET} {mid_y})",
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
    size = _ARROWHEAD_SIZE
    if direction == "left":
        points = f"{x},{y} {x + size},{y - size} {x + size},{y + size}"
    elif direction == "right":
        points = f"{x},{y} {x - size},{y - size} {x - size},{y + size}"
    elif direction == "up":
        points = f"{x},{y} {x - size},{y + size} {x + size},{y + size}"
    elif direction == "down":
        points = f"{x},{y} {x - size},{y - size} {x + size},{y - size}"
    else:
        return
    ET.SubElement(parent, "polygon", {"points": points, "fill": color})


_LEGEND_ENTRIES = [
    ("SHEET_OUTLINE", "Sheet Outline", "sheet-outline", "line"),
    ("PROFILE_CUTS", "Profile Cuts", "profile", "line"),
    ("POCKET_REGIONS", "Pocket Regions", "pocket", "rect"),
    ("HOLES", "Holes", "hole", "line"),
    ("ENGRAVE_PATHS", "Engrave Paths", "engrave", "line"),
    ("WASTE_CUTS", "Waste Cuts", "waste", "line"),
    ("PROFILE_TOOLPATHS", "Toolpath Centerline", "toolpath", "line"),
    ("ENVELOPE", "Machine Envelope", "envelope", "line"),
    ("SPOILBOARD", "Spoilboard", "spoilboard", "rect"),
    ("EFFECTIVE_ENVELOPE", "Effective Envelope", "effective-envelope", "line"),
    ("SOFT_LIMITS", "Soft Limits", "soft-limit", "line"),
    ("T_TRACK", "T-Track", "t-track", "rect"),
    ("WORK_SURFACE", "Work Surface", "work-surface", "rect"),
    ("CENTERLINES", "Centerlines", "centerline", "line"),
]


def _render_title_block(
    svg: ET.Element,
    viewbox_x: float,
    viewbox_y: float,
    theme: DiagramTheme,
    view_face: str = "front",
) -> None:
    group = ET.SubElement(svg, "g", {"id": "TITLE_BLOCK", "class": "title-block"})
    x = viewbox_x + _TITLE_X_OFFSET
    y = viewbox_y + _TITLE_Y_OFFSET

    title_style = theme.get_style("title")
    title_attrs = {
        "x": str(x),
        "y": str(y),
        **{k: v for k, v in title_style.items()},
    }
    title = ET.SubElement(group, "text", title_attrs)
    title.text = "BLUEPRINT PROOF DRAWING"

    subtitle_style = theme.get_style("title-subtitle")
    units_attrs = {
        "x": str(x),
        "y": str(y + _TITLE_UNITS_Y_OFFSET),
        **{k: v for k, v in subtitle_style.items()},
    }
    units = ET.SubElement(group, "text", units_attrs)
    units.text = "Units: millimeters (mm)"

    if view_face == "back":
        banner_attrs = {
            "x": str(x),
            "y": str(y + 2 * _TITLE_UNITS_Y_OFFSET),
            **{k: v for k, v in subtitle_style.items()},
            "font-weight": "bold",
        }
        banner = ET.SubElement(group, "text", banner_attrs)
        banner.text = "BACK FACE — SETUP 1 (flipped about X)"


def _render_legend(
    svg: ET.Element,
    viewbox_x: float,
    viewbox_y: float,
    viewbox_width: float,
    layer_names: set[str],
    theme: DiagramTheme,
) -> None:
    x = viewbox_x + viewbox_width - _LEGEND_OFFSET
    y = viewbox_y + _TITLE_Y_OFFSET
    line_height = _LEGEND_LINE_HEIGHT
    swatch_width = _LEGEND_SWATCH_WIDTH

    group = ET.SubElement(svg, "g", {"id": "LEGEND", "class": "legend"})

    legend_style = theme.get_style("legend")
    header_attrs = {
        "x": str(x),
        "y": str(y),
        **{k: v for k, v in legend_style.items()},
        "font-weight": "bold",
    }
    header = ET.SubElement(group, "text", header_attrs)
    header.text = "LEGEND"

    visible = [entry for entry in _LEGEND_ENTRIES if entry[0] in layer_names]
    visible.append(("DIMENSIONS", "Dimensions", "dimension", "line"))

    for i, (_, label, token, swatch_type) in enumerate(visible):
        y_pos = y + (i + 1) * line_height + 5
        style = theme.get_style(token)

        if swatch_type == "rect":
            rect_attrs = {
                "x": str(x),
                "y": str(y_pos - 6),
                "width": str(swatch_width),
                "height": "8",
            }
            for k in ("stroke", "stroke-width", "fill", "fill-opacity", "stroke-dasharray"):
                if k in style:
                    rect_attrs[k] = style[k]
            ET.SubElement(group, "rect", rect_attrs)
        else:
            line_attrs = {
                "x1": str(x),
                "y1": str(y_pos - 3),
                "x2": str(x + swatch_width),
                "y2": str(y_pos - 3),
            }
            for k in ("stroke", "stroke-width", "stroke-dasharray"):
                if k in style:
                    line_attrs[k] = style[k]
            ET.SubElement(group, "line", line_attrs)

        label_attrs = {
            "x": str(x + swatch_width + 5),
            "y": str(y_pos),
            **{k: v for k, v in legend_style.items()},
        }
        label_elem = ET.SubElement(group, "text", label_attrs)
        label_elem.text = label


def _render_notes_block(
    svg: ET.Element,
    drawing_bottom: float,
    metadata: dict,
    theme: DiagramTheme,
) -> None:
    x = _NOTES_X
    y = drawing_bottom + _NOTES_Y_OFFSET
    line_height = _NOTES_LINE_HEIGHT
    indent = _NOTES_INDENT

    group = ET.SubElement(svg, "g", {"id": "NOTES", "class": "notes"})
    notes_style = theme.get_style("notes")

    def _text(x_pos: float, y_pos: float, content: str, bold: bool = False) -> None:
        attrs = {
            "x": str(x_pos),
            "y": str(y_pos),
            **{k: v for k, v in notes_style.items()},
        }
        if bold:
            attrs["font-weight"] = "bold"
        elem = ET.SubElement(group, "text", attrs)
        elem.text = content

    _text(x, y, "NOTES", bold=True)
    line_num = 1

    sheet_w = metadata.get("sheet_width", "")
    sheet_h = metadata.get("sheet_height", "")
    sheet_t = metadata.get("sheet_thickness", "")
    if sheet_w:
        _text(
            x,
            y + line_num * line_height,
            f"Sheet: {float(sheet_w):.1f} \u00d7 {float(sheet_h):.1f} \u00d7 {float(sheet_t):.1f}mm",
        )
        line_num += 1

    feature_counts = metadata.get("feature_counts", "")
    if feature_counts:
        _text(x, y + line_num * line_height, f"Features: {feature_counts}")
        line_num += 1

    depth_info = metadata.get("depth_info", [])
    if depth_info:
        _text(x, y + line_num * line_height, "Depths:")
        line_num += 1
        for depth_line in depth_info:
            _text(x + indent, y + line_num * line_height, f"\u2022 {depth_line}")
            line_num += 1

    hole_diameters = metadata.get("hole_diameters", [])
    if hole_diameters:
        _text(x, y + line_num * line_height, "Hole Diameters:")
        line_num += 1
        for d in hole_diameters:
            _text(x + indent, y + line_num * line_height, f"\u2022 \u2300{d}mm")
            line_num += 1

    part_inventory = metadata.get("part_inventory", [])
    if part_inventory:
        _text(x, y + line_num * line_height, f"Parts ({len(part_inventory)}):")
        line_num += 1
        for part_id in part_inventory:
            _text(x + indent, y + line_num * line_height, f"\u2022 {part_id}")
            line_num += 1

    edge_allowances = metadata.get("edge_allowances", [])
    if edge_allowances:
        _text(x, y + line_num * line_height, "Edge Allowances:")
        line_num += 1
        for allow in edge_allowances:
            rough = allow["rough_allowance_mm"]
            finish = allow["finish_allowance_mm"]
            _text(x + indent, y + line_num * line_height, f"\u2022 Rough: {rough:.2f}mm, Finish: {finish:.2f}mm")
            line_num += 1


def _estimate_callout_height(metadata: dict) -> float:
    edge_profiles = metadata.get("edge_profiles", [])
    if not edge_profiles:
        return 0.0
    return len(edge_profiles) * (_CALLOUT_BOX_HEIGHT + _CALLOUT_BOX_SPACING) + _CALLOUT_MARGIN


def _find_shape_bounds(shape_id: str, layers: tuple[LayerIR, ...]) -> tuple[float, float, float, float] | None:
    for layer in layers:
        for shape in layer.items:
            if not hasattr(shape, "id") or shape.id != shape_id:
                continue
            if isinstance(shape, Rect):
                return (shape.x, shape.y, shape.width, shape.height)
            if isinstance(shape, Circle):
                return (shape.cx - shape.radius, shape.cy - shape.radius, shape.radius * 2, shape.radius * 2)
    return None


def _render_edge_callouts(
    svg: ET.Element,
    viewbox_x: float,
    viewbox_y: float,
    viewbox_width: float,
    edge_profiles: list[dict],
    sheet_thickness: float,
    theme: DiagramTheme,
    layers: tuple[LayerIR, ...] = (),
) -> None:
    if not edge_profiles:
        return

    group = ET.SubElement(svg, "g", {"id": "EDGE_CALLOUTS", "class": "edge-callouts"})

    box_width = _CALLOUT_BOX_WIDTH
    box_height = _CALLOUT_BOX_HEIGHT
    box_spacing = _CALLOUT_BOX_SPACING
    scale = _CALLOUT_SCALE

    start_x = viewbox_x + viewbox_width - box_width - _CALLOUT_MARGIN
    start_y = viewbox_y + _CALLOUT_START_Y_OFFSET

    section_labels = "ABCDEFGH"

    callout_style = theme.get_style("callout-box")
    detail_style = theme.get_style("callout-detail")
    label_style = theme.get_style("section-label")
    dim_style = theme.get_style("callout-dim-text")

    for i, profile in enumerate(edge_profiles):
        if i >= len(section_labels):
            break

        label = section_labels[i]
        box_x = start_x
        box_y = start_y + i * (box_height + box_spacing)

        ET.SubElement(
            group,
            "rect",
            {
                "x": str(box_x),
                "y": str(box_y),
                "width": str(box_width),
                "height": str(box_height),
                **{k: v for k, v in callout_style.items()},
                "id": f"callout_{label}_box",
            },
        )

        title_attrs = {
            "x": str(box_x + 8),
            "y": str(box_y + 12),
            "text-anchor": "start",
            **{k: v for k, v in label_style.items()},
        }
        title_elem = ET.SubElement(group, "text", title_attrs)
        title_elem.text = f"SECTION {label}"

        profile_type = profile.get("type")
        items = profile.get("items", [])

        if items:
            items_text = ", ".join(items[:3])
            if len(items) > 3:
                items_text += f" (+{len(items) - 3})"
            ref_style = theme.get_style("callout-ref-text")
            ref_attrs = {
                "x": str(box_x + 8),
                "y": str(box_y + box_height - 6),
                "text-anchor": "start",
                **{k: v for k, v in ref_style.items()},
            }
            ref_elem = ET.SubElement(group, "text", ref_attrs)
            ref_elem.text = items_text

        detail_x = box_x + 10
        detail_y = box_y + 20
        detail_w = box_width - 20
        detail_h = box_height - 36

        if profile_type == "chamfer":
            _render_chamfer_section(
                group,
                detail_x,
                detail_y,
                detail_w,
                detail_h,
                sheet_thickness,
                profile.get("distance_mm", 0),
                scale,
                detail_style,
                dim_style,
            )
        elif profile_type == "fillet":
            _render_fillet_section(
                group,
                detail_x,
                detail_y,
                detail_w,
                detail_h,
                sheet_thickness,
                profile.get("radius_mm", 0),
                scale,
                detail_style,
                dim_style,
            )

        for item_id in items:
            bounds = _find_shape_bounds(item_id, layers)
            if bounds is None:
                continue
            sx, sy, sw, _sh = bounds
            marker_r = _CALLOUT_MARKER_RADIUS
            mx = sx + sw - marker_r - 2
            my = sy + marker_r + 2
            ET.SubElement(
                group,
                "circle",
                {
                    "cx": str(mx),
                    "cy": str(my),
                    **{k: v for k, v in callout_style.items()},
                    "r": str(marker_r),
                },
            )
            marker_text = ET.SubElement(
                group,
                "text",
                {
                    "x": str(mx),
                    "y": str(my),
                    "text-anchor": "middle",
                    "dominant-baseline": "central",
                    **{k: v for k, v in label_style.items()},
                },
            )
            marker_text.text = label


def _render_chamfer_section(
    parent: ET.Element,
    area_x: float,
    area_y: float,
    area_w: float,
    area_h: float,
    thickness: float,
    distance: float,
    scale: float,
    detail_style: dict[str, str],
    dim_style: dict[str, str],
) -> None:
    t_s = min(thickness * scale, area_h)
    d_s = min(distance * scale, t_s)
    cx = area_x + area_w / 2
    cy = area_y + area_h / 2
    x0 = cx - t_s / 2
    y0 = cy - t_s / 2

    path_d = (
        f"M {x0:.2f} {y0 + d_s:.2f} "
        f"L {x0 + d_s:.2f} {y0:.2f} "
        f"L {x0 + t_s:.2f} {y0:.2f} "
        f"L {x0 + t_s:.2f} {y0 + t_s:.2f} "
        f"L {x0:.2f} {y0 + t_s:.2f} "
        f"Z"
    )

    ET.SubElement(
        parent,
        "path",
        {
            "d": path_d,
            **{k: v for k, v in detail_style.items()},
        },
    )

    dim_x = x0 + d_s / 2
    dim_y = y0 - 3
    dim_attrs = {
        "x": str(dim_x),
        "y": str(dim_y),
        "text-anchor": "middle",
        **{k: v for k, v in dim_style.items()},
    }
    dim_elem = ET.SubElement(parent, "text", dim_attrs)
    dim_elem.text = f"{distance:.1f}"

    t_attrs = {
        "x": str(x0 + t_s + 4),
        "y": str(cy),
        "text-anchor": "start",
        "dominant-baseline": "middle",
        **{k: v for k, v in dim_style.items()},
    }
    t_elem = ET.SubElement(parent, "text", t_attrs)
    t_elem.text = f"{thickness:.0f}"


def _render_fillet_section(
    parent: ET.Element,
    area_x: float,
    area_y: float,
    area_w: float,
    area_h: float,
    thickness: float,
    radius: float,
    scale: float,
    detail_style: dict[str, str],
    dim_style: dict[str, str],
) -> None:
    t_s = min(thickness * scale, area_h)
    r_s = min(radius * scale, t_s)
    cx = area_x + area_w / 2
    cy = area_y + area_h / 2
    x0 = cx - t_s / 2
    y0 = cy - t_s / 2

    path_d = (
        f"M {x0:.2f} {y0 + r_s:.2f} "
        f"A {r_s:.2f} {r_s:.2f} 0 0 1 {x0 + r_s:.2f} {y0:.2f} "
        f"L {x0 + t_s:.2f} {y0:.2f} "
        f"L {x0 + t_s:.2f} {y0 + t_s:.2f} "
        f"L {x0:.2f} {y0 + t_s:.2f} "
        f"Z"
    )

    ET.SubElement(
        parent,
        "path",
        {
            "d": path_d,
            **{k: v for k, v in detail_style.items()},
        },
    )

    dim_x = x0 + r_s / 2 - 2
    dim_y = y0 - 3
    dim_attrs = {
        "x": str(dim_x),
        "y": str(dim_y),
        "text-anchor": "middle",
        **{k: v for k, v in dim_style.items()},
    }
    dim_elem = ET.SubElement(parent, "text", dim_attrs)
    dim_elem.text = f"R{radius:.1f}"

    t_attrs = {
        "x": str(x0 + t_s + 4),
        "y": str(cy),
        "text-anchor": "start",
        "dominant-baseline": "middle",
        **{k: v for k, v in dim_style.items()},
    }
    t_elem = ET.SubElement(parent, "text", t_attrs)
    t_elem.text = f"{thickness:.0f}"


def _estimate_beam_assembly_height(metadata: dict) -> float:
    beam_structures = metadata.get("beam_structures", [])
    if not beam_structures:
        return 0.0
    total = 0.0
    for beam in beam_structures:
        layer_count = beam.get("layer_count", 1)
        total += _BEAM_HEADER_HEIGHT + layer_count * _BEAM_LAYER_HEIGHT + _BEAM_SPACING
    return total + 10.0


def _render_beam_assemblies(
    svg: ET.Element,
    top_y: float,
    beam_structures: list[dict],
    theme: DiagramTheme,
) -> None:
    group = ET.SubElement(svg, "g", {"id": "BEAM_ASSEMBLIES", "class": "beam-assemblies"})
    x = _BEAM_X
    y = top_y + _BEAM_Y_OFFSET
    layer_height = _BEAM_LAYER_HEIGHT
    header_height = _BEAM_HEADER_HEIGHT
    beam_spacing = _BEAM_SPACING
    diagram_width = _BEAM_DIAGRAM_WIDTH

    notes_style = theme.get_style("notes")
    beam_seg_style = theme.get_style("beam-segment-text")
    layer_style = theme.get_style("beam-layer")
    splice_style = theme.get_style("beam-splice")
    beam_dim_style = theme.get_style("beam-dim-text")

    for beam in beam_structures:
        name = beam.get("name", "beam")
        length_mm = beam.get("length_mm", 0)
        width_mm = beam.get("width_mm", 0)
        total_thickness = beam.get("total_thickness_mm", 0)
        role = beam.get("role", "")
        layers = beam.get("layers", [])
        layer_count = beam.get("layer_count", len(layers))

        role_str = f" ({role})" if role else ""
        header_text = f"ASSEMBLY: {name}{role_str}"
        header_attrs = {
            "x": str(x),
            "y": str(y),
            **{k: v for k, v in notes_style.items()},
            "font-weight": "bold",
        }
        header_elem = ET.SubElement(group, "text", header_attrs)
        header_elem.text = header_text

        dims_text = f"{length_mm:.0f} \u00d7 {width_mm:.0f} \u00d7 {total_thickness:.0f}mm"
        dims_attrs = {
            "x": str(x),
            "y": str(y + 12),
            **{k: v for k, v in beam_dim_style.items()},
        }
        dims_elem = ET.SubElement(group, "text", dims_attrs)
        dims_elem.text = dims_text

        diagram_y = y + header_height
        scale = diagram_width / length_mm if length_mm > 0 else 1.0

        for layer_data in layers:
            layer_idx = layer_data.get("layer_index", 0)
            segments = layer_data.get("segments", [])
            ly = diagram_y + layer_idx * layer_height

            label_attrs = {
                "x": str(x - 2),
                "y": str(ly + layer_height / 2 + 1),
                "text-anchor": "end",
                "dominant-baseline": "middle",
                **{k: v for k, v in beam_seg_style.items()},
            }
            label_elem = ET.SubElement(group, "text", label_attrs)
            label_elem.text = f"L{layer_idx}"

            for seg in segments:
                seg_start = seg.get("start_mm", 0)
                seg_end = seg.get("end_mm", 0)
                seg_length = seg.get("length_mm", seg_end - seg_start)
                seg_idx = seg.get("index", 0)

                sx = x + seg_start * scale
                sw = (seg_end - seg_start) * scale

                ET.SubElement(
                    group,
                    "rect",
                    {
                        "x": f"{sx:.2f}",
                        "y": f"{ly:.2f}",
                        "width": f"{sw:.2f}",
                        "height": f"{layer_height - 2:.2f}",
                        **{k: v for k, v in layer_style.items()},
                    },
                )

                seg_label = f"S{seg_idx} ({seg_length:.0f})"
                seg_label_attrs = {
                    "x": f"{sx + sw / 2:.2f}",
                    "y": f"{ly + layer_height / 2:.2f}",
                    "text-anchor": "middle",
                    "dominant-baseline": "middle",
                    **{k: v for k, v in beam_seg_style.items()},
                }
                seg_label_elem = ET.SubElement(group, "text", seg_label_attrs)
                seg_label_elem.text = seg_label

            if len(segments) > 1:
                for seg in segments[:-1]:
                    splice_x = x + seg["end_mm"] * scale
                    splice_y1 = ly
                    splice_y2 = ly + layer_height - 2
                    ET.SubElement(
                        group,
                        "line",
                        {
                            "x1": f"{splice_x:.2f}",
                            "y1": f"{splice_y1:.2f}",
                            "x2": f"{splice_x:.2f}",
                            "y2": f"{splice_y2:.2f}",
                            **{k: v for k, v in splice_style.items()},
                        },
                    )

        if layer_count > 1 and any(len(ld.get("segments", [])) > 1 for ld in layers):
            stagger_y = diagram_y + layer_count * layer_height + 4
            stagger_attrs = {
                "x": str(x + diagram_width / 2),
                "y": str(stagger_y),
                "text-anchor": "middle",
                **{k: v for k, v in beam_seg_style.items()},
            }
            stagger_elem = ET.SubElement(group, "text", stagger_attrs)
            stagger_elem.text = "butt joints staggered (BM-9)"

        y = diagram_y + layer_count * layer_height + beam_spacing


__all__ = [
    "DARK_DIAGRAM_THEME",
    "DIAGRAM_THEMES",
    "PRINT_DIAGRAM_THEME",
    "DiagramTheme",
    "StyleSpec",
    "render_diagram_svg",
]
