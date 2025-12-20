"""Blueprint-style SVG proof drawing export.

Generates deterministic, intent-derived inspection drawings from LayoutAST/RemovalIntent.
Focuses on validation before machining, not toolpath visualization.

All dimensions in millimeters.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence
from xml.etree import ElementTree as ET

from layout_ast.layout import LayoutAST, Item, Sheet
from ir.removal_intent import RemovalIntent, Bounds2D


# Theme definitions
@dataclass(frozen=True)
class Theme:
    """Visual theme for blueprint rendering."""
    background: str
    foreground: str
    profile_stroke: str
    profile_width: str
    pocket_stroke: str
    pocket_fill: str
    pocket_width: str
    hole_stroke: str
    hole_fill: str
    engrave_stroke: str
    engrave_dash: str
    construction_stroke: str
    construction_dash: str
    dimension_stroke: str
    dimension_text: str
    notes_text: str
    legend_text: str


DARK_THEME = Theme(
    background="#1a1a1a",
    foreground="#e8e8e8",
    profile_stroke="#e8e8e8",
    profile_width="2",
    pocket_stroke="#6496c8",
    pocket_fill="rgba(100,150,200,0.2)",
    pocket_width="1.5",
    hole_stroke="#e8e8e8",
    hole_fill="none",
    engrave_stroke="#888888",
    engrave_dash="4,4",
    construction_stroke="#333333",
    construction_dash="2,2",
    dimension_stroke="#5ab9ea",
    dimension_text="#5ab9ea",
    notes_text="#cccccc",
    legend_text="#cccccc",
)

PRINT_THEME = Theme(
    background="#ffffff",
    foreground="#000000",
    profile_stroke="#000000",
    profile_width="2",
    pocket_stroke="#000000",
    pocket_fill="#f0f0f0",
    pocket_width="1.5",
    hole_stroke="#000000",
    hole_fill="none",
    engrave_stroke="#000000",
    engrave_dash="4,4",
    construction_stroke="#666666",
    construction_dash="2,2",
    dimension_stroke="#333333",
    dimension_text="#333333",
    notes_text="#000000",
    legend_text="#000000",
)

THEMES = {
    "dark": DARK_THEME,
    "print": PRINT_THEME,
}


def render_blueprint_svg(
    layout_ast: LayoutAST,
    removal_intents: Sequence[RemovalIntent] | None = None,
    theme: str = "dark",
) -> str:
    """Render blueprint-style SVG from LayoutAST and RemovalIntent.

    Args:
        layout_ast: Layout AST with sheet and items
        removal_intents: Optional RemovalIntent list (for depth info, bounds validation)
        theme: "dark" (default) or "print"

    Returns:
        SVG string with semantic layer groups
    """
    theme_obj = THEMES.get(theme, DARK_THEME)
    sheet = layout_ast.sheet

    # Create SVG root with viewBox matching sheet dimensions + margin for dimensions
    margin = 100  # mm margin for dimension rails
    viewbox_width = sheet.width_mm + 2 * margin
    viewbox_height = sheet.height_mm + 2 * margin

    svg = ET.Element(
        "svg",
        {
            "xmlns": "http://www.w3.org/2000/svg",
            "viewBox": f"0 0 {viewbox_width} {viewbox_height}",
            "width": f"{viewbox_width}mm",
            "height": f"{viewbox_height}mm",
        },
    )

    # Add style definitions
    style = ET.SubElement(svg, "style")
    style.text = _generate_stylesheet(theme_obj)

    # Background rectangle
    ET.SubElement(
        svg,
        "rect",
        {
            "x": "0",
            "y": "0",
            "width": str(viewbox_width),
            "height": str(viewbox_height),
            "fill": theme_obj.background,
        },
    )

    # Offset for margin
    offset_x = margin
    offset_y = margin

    # Create semantic layer groups
    sheet_group = ET.SubElement(svg, "g", {"id": "SHEET_OUTLINE", "class": "sheet-outline"})
    profile_group = ET.SubElement(svg, "g", {"id": "PROFILE_CUTS", "class": "profile-cuts"})
    pocket_group = ET.SubElement(svg, "g", {"id": "POCKET_REGIONS", "class": "pocket-regions"})
    engrave_group = ET.SubElement(svg, "g", {"id": "ENGRAVE_PATHS", "class": "engrave-paths"})
    hole_group = ET.SubElement(svg, "g", {"id": "HOLES", "class": "holes"})
    construction_group = ET.SubElement(svg, "g", {"id": "CONSTRUCTION", "class": "construction"})
    dimension_group = ET.SubElement(svg, "g", {"id": "DIMENSIONS", "class": "dimensions"})
    notes_group = ET.SubElement(svg, "g", {"id": "NOTES", "class": "notes"})
    title_group = ET.SubElement(svg, "g", {"id": "TITLE_BLOCK", "class": "title-block"})
    legend_group = ET.SubElement(svg, "g", {"id": "LEGEND", "class": "legend"})

    # Render sheet boundary
    _render_sheet_boundary(sheet_group, sheet, offset_x, offset_y, theme_obj)

    # Render items by feature type
    for item in layout_ast.items:
        if item.kind != "shape" or item.feature is None:
            continue  # Skip templates or items without features

        feature_type = item.feature.type
        if feature_type == "profile":
            _render_profile(profile_group, item, offset_x, offset_y, theme_obj)
        elif feature_type == "pocket":
            _render_pocket(pocket_group, item, offset_x, offset_y, theme_obj)
        elif feature_type == "hole":
            _render_hole(hole_group, item, offset_x, offset_y, theme_obj)
        elif feature_type == "engrave":
            _render_engrave(engrave_group, item, offset_x, offset_y, theme_obj)

    # Add minimal notes for now (Part A doesn't have full dimension engine yet)
    _render_notes_placeholder(notes_group, viewbox_width, viewbox_height, theme_obj)

    # Convert to string
    ET.indent(svg, space="  ")
    return ET.tostring(svg, encoding="unicode")


def _generate_stylesheet(theme: Theme) -> str:
    """Generate CSS stylesheet for SVG."""
    return f"""
        .sheet-outline {{ stroke: {theme.construction_stroke}; stroke-width: 1; fill: none; stroke-dasharray: {theme.construction_dash}; }}
        .profile-cuts {{ stroke: {theme.profile_stroke}; stroke-width: {theme.profile_width}; fill: none; }}
        .pocket-regions {{ stroke: {theme.pocket_stroke}; stroke-width: {theme.pocket_width}; fill: {theme.pocket_fill}; }}
        .holes {{ stroke: {theme.hole_stroke}; stroke-width: 1.5; fill: {theme.hole_fill}; }}
        .engrave-paths {{ stroke: {theme.engrave_stroke}; stroke-width: 1; fill: none; stroke-dasharray: {theme.engrave_dash}; }}
        .construction {{ stroke: {theme.construction_stroke}; stroke-width: 0.5; fill: none; stroke-dasharray: {theme.construction_dash}; }}
        .dimensions {{ stroke: {theme.dimension_stroke}; stroke-width: 1; fill: none; }}
        .dimension-text {{ fill: {theme.dimension_text}; font-family: monospace; font-size: 12px; }}
        .notes {{ fill: {theme.notes_text}; font-family: monospace; font-size: 10px; }}
        .legend {{ fill: {theme.legend_text}; font-family: monospace; font-size: 10px; }}
    """


def _render_sheet_boundary(group: ET.Element, sheet: Sheet, offset_x: float, offset_y: float, theme: Theme) -> None:
    """Render sheet outline."""
    ET.SubElement(
        group,
        "rect",
        {
            "x": str(offset_x),
            "y": str(offset_y),
            "width": str(sheet.width_mm),
            "height": str(sheet.height_mm),
        },
    )


def _render_profile(group: ET.Element, item: Item, offset_x: float, offset_y: float, theme: Theme) -> None:
    """Render profile cut shape."""
    if item.geometry is None or item.placement is None:
        return

    shape_type = item.type
    cx, cy = item.placement.center_xy_mm

    if shape_type == "Rect":
        w = item.geometry.data.get("w_mm", 0)
        h = item.geometry.data.get("h_mm", 0)
        x = offset_x + cx - w / 2
        y = offset_y + cy - h / 2
        ET.SubElement(
            group,
            "rect",
            {
                "x": str(x),
                "y": str(y),
                "width": str(w),
                "height": str(h),
            },
        )
    elif shape_type == "Circle":
        r = item.geometry.data.get("radius_mm") or item.geometry.data.get("diameter_mm", 0) / 2
        ET.SubElement(
            group,
            "circle",
            {
                "cx": str(offset_x + cx),
                "cy": str(offset_y + cy),
                "r": str(r),
            },
        )


def _render_pocket(group: ET.Element, item: Item, offset_x: float, offset_y: float, theme: Theme) -> None:
    """Render pocket region."""
    if item.geometry is None or item.placement is None:
        return

    shape_type = item.type
    cx, cy = item.placement.center_xy_mm

    if shape_type == "Rect":
        w = item.geometry.data.get("w_mm", 0)
        h = item.geometry.data.get("h_mm", 0)
        x = offset_x + cx - w / 2
        y = offset_y + cy - h / 2
        ET.SubElement(
            group,
            "rect",
            {
                "x": str(x),
                "y": str(y),
                "width": str(w),
                "height": str(h),
            },
        )
    elif shape_type == "Circle":
        r = item.geometry.data.get("radius_mm") or item.geometry.data.get("diameter_mm", 0) / 2
        ET.SubElement(
            group,
            "circle",
            {
                "cx": str(offset_x + cx),
                "cy": str(offset_y + cy),
                "r": str(r),
            },
        )


def _render_hole(group: ET.Element, item: Item, offset_x: float, offset_y: float, theme: Theme) -> None:
    """Render hole with center mark."""
    if item.geometry is None or item.placement is None:
        return

    cx, cy = item.placement.center_xy_mm
    abs_cx = offset_x + cx
    abs_cy = offset_y + cy

    # Get diameter
    d = item.geometry.data.get("diameter_mm", item.geometry.data.get("radius_mm", 5) * 2)
    r = d / 2

    # Circle outline
    ET.SubElement(
        group,
        "circle",
        {
            "cx": str(abs_cx),
            "cy": str(abs_cy),
            "r": str(r),
        },
    )

    # Center mark (cross)
    mark_size = 3
    ET.SubElement(
        group,
        "line",
        {
            "x1": str(abs_cx - mark_size),
            "y1": str(abs_cy),
            "x2": str(abs_cx + mark_size),
            "y2": str(abs_cy),
        },
    )
    ET.SubElement(
        group,
        "line",
        {
            "x1": str(abs_cx),
            "y1": str(abs_cy - mark_size),
            "x2": str(abs_cx),
            "y2": str(abs_cy + mark_size),
        },
    )


def _render_engrave(group: ET.Element, item: Item, offset_x: float, offset_y: float, theme: Theme) -> None:
    """Render engrave path (simplified for Part A)."""
    # For now, render engraves similar to profiles but with dashed style
    # TODO: Handle polylines, splines in later parts
    _render_profile(group, item, offset_x, offset_y, theme)


def _render_notes_placeholder(group: ET.Element, viewbox_width: float, viewbox_height: float, theme: Theme) -> None:
    """Render placeholder notes area (full implementation in Part C)."""
    notes_x = 20
    notes_y = viewbox_height - 60

    text = ET.SubElement(
        group,
        "text",
        {
            "x": str(notes_x),
            "y": str(notes_y),
            "class": "notes",
        },
    )
    text.text = "NOTES: (Dimensions and depth info to be added in Part B/C)"
