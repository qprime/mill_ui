"""SVG rendering with RemovalIntent visualization overlays.

Renders LayoutAST shapes with RemovalIntent region overlays for visual debugging.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from skills.mill_ui.layout_ast.layout import LayoutAST
from skills.mill_ui.ir.removal_intent import RemovalIntent


def render_svg_with_removal_intent(
    ast: LayoutAST,
    removal_intents: list[RemovalIntent],
    output_path: str | Path,
) -> None:
    """Render SVG with RemovalIntent overlay for visual inspection.

    Args:
        ast: LayoutAST containing original shapes
        removal_intents: List of RemovalIntent regions to overlay
        output_path: Path to write SVG file

    SVG Layers:
        - Original shapes (black, stroke-width=1)
        - RemovalIntent bounds (red, stroke-width=2)
        - Kerf offsets (blue dashed, stroke-width=1)
    """
    # Calculate SVG viewBox from sheet dimensions
    sheet = ast.sheet
    width_mm = sheet.width_mm
    height_mm = sheet.height_mm

    # Add 10mm margin on all sides
    margin = 10.0
    viewbox_width = width_mm + 2 * margin
    viewbox_height = height_mm + 2 * margin

    # Create SVG root element
    svg = ET.Element(
        "svg",
        xmlns="http://www.w3.org/2000/svg",
        viewBox=f"0 0 {viewbox_width} {viewbox_height}",
        width=f"{viewbox_width}mm",
        height=f"{viewbox_height}mm",
    )

    # Add white background
    ET.SubElement(
        svg,
        "rect",
        x="0",
        y="0",
        width=f"{viewbox_width}",
        height=f"{viewbox_height}",
        fill="white",
    )

    # Add sheet boundary (light gray)
    ET.SubElement(
        svg,
        "rect",
        x=f"{margin}",
        y=f"{margin}",
        width=f"{width_mm}",
        height=f"{height_mm}",
        fill="none",
        stroke="#cccccc",
        attrib={"stroke-width": "0.5"},
    )

    # Render original shapes (black)
    shapes_group = ET.SubElement(svg, "g", id="original_shapes")
    for item in ast.items:
        if item.kind == "shape" and item.geometry and item.placement:
            _render_shape(shapes_group, item, margin, "black", "1")

    # Render RemovalIntent bounds (red)
    removal_group = ET.SubElement(svg, "g", id="removal_intent_bounds")
    for intent in removal_intents:
        _render_removal_intent_bounds(removal_group, intent, margin)

    # Render kerf offsets (blue dashed)
    kerf_group = ET.SubElement(svg, "g", id="kerf_offsets")
    for intent in removal_intents:
        _render_kerf_offset(kerf_group, intent, margin)

    # Write SVG to file
    tree = ET.ElementTree(svg)
    ET.indent(tree, space="  ")
    tree.write(output_path, encoding="utf-8", xml_declaration=True)


def _render_shape(
    parent: ET.Element,
    item: Any,
    margin: float,
    stroke_color: str,
    stroke_width: str,
) -> None:
    """Render a single shape to SVG."""
    shape_type = item.type
    geometry = item.geometry.data
    center_x, center_y = item.placement.center_xy_mm

    # Translate to SVG coordinates (add margin, flip Y)
    cx = center_x + margin
    cy = center_y + margin

    if shape_type == "Rect":
        w = geometry["w_mm"]
        h = geometry["h_mm"]
        x = cx - w / 2
        y = cy - h / 2

        ET.SubElement(
            parent,
            "rect",
            x=f"{x}",
            y=f"{y}",
            width=f"{w}",
            height=f"{h}",
            fill="none",
            stroke=stroke_color,
            attrib={"stroke-width": stroke_width},
        )

    elif shape_type == "Circle":
        r = geometry["diameter_mm"] / 2

        ET.SubElement(
            parent,
            "circle",
            cx=f"{cx}",
            cy=f"{cy}",
            r=f"{r}",
            fill="none",
            stroke=stroke_color,
            attrib={"stroke-width": stroke_width},
        )

    elif shape_type == "RoundedRect":
        w = geometry["w_mm"]
        h = geometry["h_mm"]
        corner_r = geometry.get("corner_radius_mm", 0.0)
        x = cx - w / 2
        y = cy - h / 2

        ET.SubElement(
            parent,
            "rect",
            x=f"{x}",
            y=f"{y}",
            width=f"{w}",
            height=f"{h}",
            rx=f"{corner_r}",
            ry=f"{corner_r}",
            fill="none",
            stroke=stroke_color,
            attrib={"stroke-width": stroke_width},
        )


def _render_removal_intent_bounds(
    parent: ET.Element,
    intent: RemovalIntent,
    margin: float,
) -> None:
    """Render RemovalIntent bounding box (red)."""
    bounds = intent.bounds
    x = bounds.x_min + margin
    y = bounds.y_min + margin
    w = bounds.x_max - bounds.x_min
    h = bounds.y_max - bounds.y_min

    # Add label
    label_x = x + w / 2
    label_y = y - 2

    ET.SubElement(
        parent,
        "text",
        x=f"{label_x}",
        y=f"{label_y}",
        fill="red",
        attrib={
            "font-size": "3",
            "text-anchor": "middle",
            "font-family": "monospace",
        },
    ).text = intent.region_id

    # Draw bounds rectangle
    ET.SubElement(
        parent,
        "rect",
        x=f"{x}",
        y=f"{y}",
        width=f"{w}",
        height=f"{h}",
        fill="none",
        stroke="red",
        attrib={"stroke-width": "2", "opacity": "0.7"},
    )


def _render_kerf_offset(
    parent: ET.Element,
    intent: RemovalIntent,
    margin: float,
) -> None:
    """Render kerf compensation offset (blue dashed)."""
    allowance = intent.allowance

    # Only render if there's actual kerf compensation
    if allowance.kerf_compensation == 0.0:
        return

    bounds = intent.bounds
    kerf = allowance.kerf_compensation

    # Offset bounds by kerf compensation
    x = bounds.x_min + margin - kerf
    y = bounds.y_min + margin - kerf
    w = (bounds.x_max - bounds.x_min) + 2 * kerf
    h = (bounds.y_max - bounds.y_min) + 2 * kerf

    ET.SubElement(
        parent,
        "rect",
        x=f"{x}",
        y=f"{y}",
        width=f"{w}",
        height=f"{h}",
        fill="none",
        stroke="blue",
        attrib={
            "stroke-width": "1",
            "stroke-dasharray": "2,2",
            "opacity": "0.5",
        },
    )
