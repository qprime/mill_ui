
from __future__ import annotations

from typing import Literal
from xml.etree import ElementTree as ET

from diagram_ir.dimensions import PlacedDimension


def render_placed_dimension(parent: ET.Element, dim: PlacedDimension, stroke_color: str) -> None:
    if dim.orientation == "horizontal":
        _render_horizontal(parent, dim, stroke_color)
    else:
        _render_vertical(parent, dim, stroke_color)


def _render_horizontal(parent: ET.Element, dim: PlacedDimension, stroke_color: str) -> None:
    x1, x2 = dim.a, dim.b
    y_anchor = dim.anchor
    y_dim = dim.rail


    _line(parent, x1, y_anchor, x1, y_dim, stroke_color)
    _line(parent, x2, y_anchor, x2, y_dim, stroke_color)


    _line(parent, x1, y_dim, x2, y_dim, stroke_color)
    _arrow(parent, x1, y_dim, "left", stroke_color)
    _arrow(parent, x2, y_dim, "right", stroke_color)


    ET.SubElement(
        parent,
        "text",
        {
            "x": str((x1 + x2) / 2.0),
            "y": str(y_dim - 5.0),
            "class": "dimension-text",
            "text-anchor": "middle",
            "dominant-baseline": "middle",
        },
    ).text = dim.text


def _render_vertical(parent: ET.Element, dim: PlacedDimension, stroke_color: str) -> None:
    y1, y2 = dim.a, dim.b
    x_anchor = dim.anchor
    x_dim = dim.rail


    _line(parent, x_anchor, y1, x_dim, y1, stroke_color)
    _line(parent, x_anchor, y2, x_dim, y2, stroke_color)


    _line(parent, x_dim, y1, x_dim, y2, stroke_color)
    _arrow(parent, x_dim, y1, "up", stroke_color)
    _arrow(parent, x_dim, y2, "down", stroke_color)


    mid_y = (y1 + y2) / 2.0
    ET.SubElement(
        parent,
        "text",
        {
            "x": str(x_dim + 5.0),
            "y": str(mid_y),
            "class": "dimension-text",
            "text-anchor": "middle",
            "dominant-baseline": "middle",
            "transform": f"rotate(-90 {x_dim + 5.0} {mid_y})",
        },
    ).text = dim.text


def _line(parent: ET.Element, x1: float, y1: float, x2: float, y2: float, stroke_color: str) -> None:
    ET.SubElement(
        parent,
        "line",
        {
            "x1": str(x1),
            "y1": str(y1),
            "x2": str(x2),
            "y2": str(y2),
            "stroke": stroke_color,
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


def render_gap_dimension(
    parent: ET.Element,
    start: float,
    end: float,
    orientation: Literal["horizontal", "vertical"],
    position: float,
    label: str,
    color: str,
) -> None:
    if orientation == "horizontal":
        _render_horizontal_gap_arrow(parent, start, end, position, label, color)
    else:
        _render_vertical_gap_arrow(parent, start, end, position, label, color)


def _render_horizontal_gap_arrow(
    parent: ET.Element, x1: float, x2: float, y: float, label: str, color: str
) -> None:
    mid_x = (x1 + x2) / 2.0
    arrow_size = 3.0


    _line(parent, x1, y, x2, y, color)


    ET.SubElement(
        parent,
        "path",
        {
            "d": f"M {x1},{y} L {x1 + arrow_size},{y - arrow_size} L {x1 + arrow_size},{y + arrow_size} Z",
            "class": "gap-dimensions",
            "stroke": "none",
            "fill": color,
        },
    )


    ET.SubElement(
        parent,
        "path",
        {
            "d": f"M {x2},{y} L {x2 - arrow_size},{y - arrow_size} L {x2 - arrow_size},{y + arrow_size} Z",
            "class": "gap-dimensions",
            "stroke": "none",
            "fill": color,
        },
    )


    ET.SubElement(
        parent,
        "text",
        {
            "x": str(mid_x),
            "y": str(y - 4.0),
            "class": "gap-text",
            "text-anchor": "middle",
        },
    ).text = label


def _render_vertical_gap_arrow(
    parent: ET.Element, y1: float, y2: float, x: float, label: str, color: str
) -> None:
    mid_y = (y1 + y2) / 2.0
    arrow_size = 3.0


    _line(parent, x, y1, x, y2, color)


    ET.SubElement(
        parent,
        "path",
        {
            "d": f"M {x},{y1} L {x - arrow_size},{y1 + arrow_size} L {x + arrow_size},{y1 + arrow_size} Z",
            "class": "gap-dimensions",
            "stroke": "none",
            "fill": color,
        },
    )


    ET.SubElement(
        parent,
        "path",
        {
            "d": f"M {x},{y2} L {x - arrow_size},{y2 - arrow_size} L {x + arrow_size},{y2 - arrow_size} Z",
            "class": "gap-dimensions",
            "stroke": "none",
            "fill": color,
        },
    )


    ET.SubElement(
        parent,
        "text",
        {
            "x": str(x - 6.0),
            "y": str(mid_y),
            "class": "gap-text",
            "text-anchor": "middle",
            "dominant-baseline": "middle",
            "transform": f"rotate(-90 {x - 6.0} {mid_y})",
        },
    ).text = label


__all__ = [
    "render_placed_dimension",
    "render_gap_dimension",
]
