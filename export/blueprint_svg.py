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
from export.dimensions import place_dimensions_on_rails, render_placed_dimension, render_gap_dimension


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
    gap_stroke: str  # Color for gap/spacing dimensions (braces)
    gap_text: str
    notes_text: str
    legend_text: str


DARK_THEME = Theme(
    background="#1a1a1a",
    foreground="#e8e8e8",
    profile_stroke="#e8e8e8",
    profile_width="2",
    pocket_stroke="#6496c8",
    pocket_fill="#6496c8",  # Use fill-opacity instead of rgba for PDF compatibility
    pocket_width="1.5",
    hole_stroke="#e8e8e8",
    hole_fill="none",
    engrave_stroke="#888888",
    engrave_dash="4,4",
    construction_stroke="#6b8e7f",  # Greenish-gray for better visibility
    construction_dash="2,2",
    dimension_stroke="#5ab9ea",
    dimension_text="#5ab9ea",
    gap_stroke="#ff9500",  # Amber/orange for spacing/gap dimensions
    gap_text="#ff9500",
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
    gap_stroke="#cc6600",  # Darker orange for print theme
    gap_text="#cc6600",
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
    margin = 140  # mm margin for dimension rails, title, legend, and notes
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

    # Render dimensions on rails (Part B)
    _render_dimensions(dimension_group, layout_ast, offset_x, offset_y, margin, theme_obj)

    # Render title block, legend, and notes (Part C)
    _render_title_block(title_group, viewbox_width, viewbox_height, theme_obj)
    _render_legend(legend_group, viewbox_width, theme_obj)
    _render_notes(notes_group, layout_ast, removal_intents, viewbox_height, theme_obj)

    # Convert to string
    ET.indent(svg, space="  ")
    return ET.tostring(svg, encoding="unicode")


def _generate_stylesheet(theme: Theme) -> str:
    """Generate CSS stylesheet for SVG."""
    return f"""
        .sheet-outline {{ stroke: {theme.construction_stroke}; stroke-width: 1; fill: none; stroke-dasharray: {theme.construction_dash}; }}
        .profile-cuts {{ stroke: {theme.profile_stroke}; stroke-width: {theme.profile_width}; fill: none; }}
        .pocket-regions {{ stroke: {theme.pocket_stroke}; stroke-width: {theme.pocket_width}; fill: {theme.pocket_fill}; fill-opacity: 0.2; }}
        .holes {{ stroke: {theme.hole_stroke}; stroke-width: 1.5; fill: {theme.hole_fill}; }}
        .engrave-paths {{ stroke: {theme.engrave_stroke}; stroke-width: 1; fill: none; stroke-dasharray: {theme.engrave_dash}; }}
        .construction {{ stroke: {theme.construction_stroke}; stroke-width: 0.5; fill: none; stroke-dasharray: {theme.construction_dash}; }}
        .dimensions {{ stroke: {theme.dimension_stroke}; stroke-width: 1; fill: none; }}
        .dimension-text {{ fill: #888888; font-family: monospace; font-size: 6px; }}
        .gap-dimensions {{ stroke: {theme.gap_stroke}; stroke-width: 1; fill: none; }}
        .gap-text {{ fill: #888888; font-family: monospace; font-size: 6px; }}
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


def _render_dimensions(
    group: ET.Element,
    ast: LayoutAST,
    offset_x: float,
    offset_y: float,
    margin: float,
    theme: Theme,
) -> None:
    """Render dimension lines and labels on rails."""
    # Standard feature dimensions (blue lines, gray text via CSS)
    dims = place_dimensions_on_rails(ast, offset_x, offset_y, margin=margin, include_features={"profile", "pocket"})
    for dim in dims:
        render_placed_dimension(group, dim, theme.dimension_stroke)

    # Gap dimensions (amber/orange braces)
    _render_gap_dimensions(group, ast, offset_x, offset_y, theme)


def _render_gap_dimensions(
    group: ET.Element,
    ast: LayoutAST,
    offset_x: float,
    offset_y: float,
    theme: Theme,
) -> None:
    """Render gap/spacing dimensions with double-headed arrows.

    Detects and shows:
    1. Border/inset: gap between profile edge and first pocket
    2. Mullion spacing: horizontal gaps between adjacent pockets
    3. Rail spacing: vertical gaps between adjacent pockets
    """
    # Find profile bounds
    profile_items = [
        item for item in ast.items
        if item.kind == "shape"
        and item.feature is not None
        and item.feature.type == "profile"
        and item.geometry is not None
        and item.placement is not None
    ]

    if not profile_items:
        return

    # Get main profile (largest area, typically the outer boundary)
    main_profile = None
    max_area = 0.0
    for item in profile_items:
        if item.type in ("Rect", "RoundedRect"):
            w = float(item.geometry.data.get("w_mm", 0))
            h = float(item.geometry.data.get("h_mm", 0))
            area = w * h
            if area > max_area:
                max_area = area
                main_profile = item

    if main_profile is None:
        return

    # Get main profile bounds
    cx, cy = main_profile.placement.center_xy_mm
    w = float(main_profile.geometry.data.get("w_mm", 0))
    h = float(main_profile.geometry.data.get("h_mm", 0))

    profile_x_min = cx - w / 2.0
    profile_x_max = cx + w / 2.0
    profile_y_min = cy - h / 2.0
    profile_y_max = cy + h / 2.0

    # Get pockets to detect internal gaps
    pocket_items = [
        item for item in ast.items
        if item.kind == "shape"
        and item.feature is not None
        and item.feature.type == "pocket"
        and item.geometry is not None
        and item.placement is not None
        and item.type in ("Rect", "RoundedRect")
    ]

    if not pocket_items:
        return

    # Build pocket bounds list
    pocket_bounds = []
    for pocket in pocket_items:
        pcx, pcy = pocket.placement.center_xy_mm
        pw = float(pocket.geometry.data.get("w_mm", 0))
        ph = float(pocket.geometry.data.get("h_mm", 0))
        pocket_bounds.append({
            "cx": pcx,
            "cy": pcy,
            "x_min": pcx - pw / 2.0,
            "x_max": pcx + pw / 2.0,
            "y_min": pcy - ph / 2.0,
            "y_max": pcy + ph / 2.0,
            "w": pw,
            "h": ph,
        })

    # 1. Border/inset dimensions
    min_left_gap = min(pb["x_min"] - profile_x_min for pb in pocket_bounds)
    min_top_gap = min(pb["y_min"] - profile_y_min for pb in pocket_bounds)

    if min_left_gap > 5.0:
        # Horizontal arrow in left border showing inset
        y_center = (profile_y_min + profile_y_max) / 2.0
        render_gap_dimension(
            group,
            offset_x + profile_x_min,
            offset_x + profile_x_min + min_left_gap,
            "horizontal",
            offset_y + y_center,
            f"{min_left_gap:.0f}mm",
            theme.gap_stroke,
        )

    if min_top_gap > 5.0:
        # Vertical arrow in top border showing inset
        x_center = (profile_x_min + profile_x_max) / 2.0
        render_gap_dimension(
            group,
            offset_y + profile_y_min,
            offset_y + profile_y_min + min_top_gap,
            "vertical",
            offset_x + x_center,
            f"{min_top_gap:.0f}mm",
            theme.gap_stroke,
        )

    # 2. Detect horizontal gaps (mullions) - sort pockets by x position
    sorted_by_x = sorted(pocket_bounds, key=lambda p: p["x_min"])
    horizontal_gaps = []
    for i in range(len(sorted_by_x) - 1):
        curr = sorted_by_x[i]
        next_pocket = sorted_by_x[i + 1]
        gap = next_pocket["x_min"] - curr["x_max"]
        if gap > 5.0:  # Significant gap
            # Check if pockets are vertically aligned (same row)
            y_overlap = not (curr["y_max"] < next_pocket["y_min"] or curr["y_min"] > next_pocket["y_max"])
            if y_overlap:
                horizontal_gaps.append({
                    "start": curr["x_max"],
                    "end": next_pocket["x_min"],
                    "y": (max(curr["y_min"], next_pocket["y_min"]) + min(curr["y_max"], next_pocket["y_max"])) / 2.0,
                    "gap": gap,
                })

    # 3. Detect vertical gaps (rails) - sort pockets by y position
    sorted_by_y = sorted(pocket_bounds, key=lambda p: p["y_min"])
    vertical_gaps = []
    for i in range(len(sorted_by_y) - 1):
        curr = sorted_by_y[i]
        next_pocket = sorted_by_y[i + 1]
        gap = next_pocket["y_min"] - curr["y_max"]
        if gap > 5.0:  # Significant gap
            # Check if pockets are horizontally aligned (same column)
            x_overlap = not (curr["x_max"] < next_pocket["x_min"] or curr["x_min"] > next_pocket["x_max"])
            if x_overlap:
                vertical_gaps.append({
                    "start": curr["y_max"],
                    "end": next_pocket["y_min"],
                    "x": (max(curr["x_min"], next_pocket["x_min"]) + min(curr["x_max"], next_pocket["x_max"])) / 2.0,
                    "gap": gap,
                })

    # Render unique horizontal gaps (mullions)
    seen_h_gaps = set()
    for hgap in horizontal_gaps:
        key = (round(hgap["start"], 1), round(hgap["end"], 1), round(hgap["gap"], 1))
        if key not in seen_h_gaps:
            seen_h_gaps.add(key)
            render_gap_dimension(
                group,
                offset_x + hgap["start"],
                offset_x + hgap["end"],
                "vertical",  # Mullion is vertical, but we're measuring horizontal gap
                offset_x + (hgap["start"] + hgap["end"]) / 2.0,
                f"{hgap['gap']:.0f}mm",
                theme.gap_stroke,
            )

    # Render unique vertical gaps (rails)
    seen_v_gaps = set()
    for vgap in vertical_gaps:
        key = (round(vgap["start"], 1), round(vgap["end"], 1), round(vgap["gap"], 1))
        if key not in seen_v_gaps:
            seen_v_gaps.add(key)
            render_gap_dimension(
                group,
                offset_y + vgap["start"],
                offset_y + vgap["end"],
                "horizontal",  # Rail is horizontal, but we're measuring vertical gap
                offset_y + (vgap["start"] + vgap["end"]) / 2.0,
                f"{vgap['gap']:.0f}mm",
                theme.gap_stroke,
            )

def _render_title_block(group: ET.Element, viewbox_width: float, viewbox_height: float, theme: Theme) -> None:
    """Render title block with metadata."""
    x = 20
    y = 20
    line_height = 14

    # Title
    title = ET.SubElement(
        group,
        "text",
        {
            "x": str(x),
            "y": str(y),
            "class": "notes",
            "font-weight": "bold",
            "font-size": "14px",
        },
    )
    title.text = "BLUEPRINT PROOF DRAWING"

    # Units (no timestamp for determinism)
    units = ET.SubElement(
        group,
        "text",
        {
            "x": str(x),
            "y": str(y + line_height),
            "class": "notes",
            "font-size": "9px",
        },
    )
    units.text = "Units: millimeters (mm)"


def _render_legend(group: ET.Element, viewbox_width: float, theme: Theme) -> None:
    """Render legend showing layer meanings."""
    x = viewbox_width - 132  # Positioned near right edge with margin space
    y = 20
    line_height = 16
    swatch_size = 10

    legend_title = ET.SubElement(
        group,
        "text",
        {
            "x": str(x),
            "y": str(y),
            "class": "legend",
            "font-weight": "bold",
        },
    )
    legend_title.text = "LEGEND"

    # Layer specifications: (label, stroke_color, stroke_width, dash_pattern, fill_color)
    # Note: dash_pattern=None means no dashing, fill_color=None means no fill
    layers = [
        ("Sheet Outline", theme.construction_stroke, "1", theme.construction_dash, None),
        ("Profile Cuts", theme.profile_stroke, "2", None, None),
        ("Pocket Regions", theme.pocket_stroke, "1.5", None, theme.pocket_fill),
        ("Holes", theme.hole_stroke, "1.5", None, None),
        ("Dimensions", theme.dimension_stroke, "1", None, None),
    ]

    for i, (label, stroke, width, dash, fill) in enumerate(layers):
        y_pos = y + (i + 1) * line_height + 5

        # Color swatch (line or rect depending on fill)
        if fill:
            # Pocket regions: show filled rectangle with opacity
            rect_attrs = {
                "x": str(x),
                "y": str(y_pos - 6),
                "width": str(swatch_size * 1.5),
                "height": "8",
                "stroke": stroke,
                "stroke-width": width,
                "fill": fill,
                "fill-opacity": "0.2",
            }
            ET.SubElement(group, "rect", rect_attrs)
        else:
            # Other layers: line sample
            swatch_attrs = {
                "x1": str(x),
                "y1": str(y_pos - 3),
                "x2": str(x + swatch_size * 1.5),
                "y2": str(y_pos - 3),
                "stroke": stroke,
                "stroke-width": width,
            }
            if dash is not None:
                swatch_attrs["stroke-dasharray"] = dash
            ET.SubElement(group, "line", swatch_attrs)

        # Label
        label_elem = ET.SubElement(
            group,
            "text",
            {
                "x": str(x + swatch_size * 2),
                "y": str(y_pos),
                "class": "legend",
            },
        )
        label_elem.text = label


def _render_notes(
    group: ET.Element,
    ast: LayoutAST,
    removal_intents: Sequence[RemovalIntent] | None,
    viewbox_height: float,
    theme: Theme,
) -> None:
    """Render notes block with depth info and feature counts."""
    x = 20
    y = viewbox_height - 120  # Add padding to avoid collision with sheet edge
    line_height = 12

    # Title
    notes_title = ET.SubElement(
        group,
        "text",
        {
            "x": str(x),
            "y": str(y),
            "class": "notes",
            "font-weight": "bold",
        },
    )
    notes_title.text = "NOTES"

    # Collect depth information
    depths_info = _collect_depth_info(ast, removal_intents)

    # Collect hole diameter information
    hole_diameters = _collect_hole_diameters(ast)

    # Feature counts
    feature_counts = _count_features(ast)

    line_num = 1

    # Sheet info
    sheet_info = ET.SubElement(
        group,
        "text",
        {
            "x": str(x),
            "y": str(y + line_num * line_height),
            "class": "notes",
        },
    )
    sheet_info.text = f"Sheet: {ast.sheet.width_mm:.1f} × {ast.sheet.height_mm:.1f} × {ast.sheet.thickness_mm:.1f}mm"
    line_num += 1

    # Feature counts
    if feature_counts:
        counts_text = ", ".join(f"{count} {ftype}{'s' if count > 1 else ''}" for ftype, count in feature_counts.items())
        features_info = ET.SubElement(
            group,
            "text",
            {
                "x": str(x),
                "y": str(y + line_num * line_height),
                "class": "notes",
            },
        )
        features_info.text = f"Features: {counts_text}"
        line_num += 1

    # Depth information
    if depths_info:
        depths_title = ET.SubElement(
            group,
            "text",
            {
                "x": str(x),
                "y": str(y + line_num * line_height),
                "class": "notes",
            },
        )
        depths_title.text = "Depths:"
        line_num += 1

        for depth_line in depths_info:
            depth_elem = ET.SubElement(
                group,
                "text",
                {
                    "x": str(x + 10),
                    "y": str(y + line_num * line_height),
                    "class": "notes",
                },
            )
            depth_elem.text = f"• {depth_line}"
            line_num += 1

    # Hole diameter information
    if hole_diameters:
        hole_title = ET.SubElement(
            group,
            "text",
            {
                "x": str(x),
                "y": str(y + line_num * line_height),
                "class": "notes",
            },
        )
        hole_title.text = "Hole Diameters:"
        line_num += 1

        for diameter_line in hole_diameters:
            diameter_elem = ET.SubElement(
                group,
                "text",
                {
                    "x": str(x + 10),
                    "y": str(y + line_num * line_height),
                    "class": "notes",
                },
            )
            diameter_elem.text = f"• {diameter_line}"
            line_num += 1


def _collect_depth_info(ast: LayoutAST, removal_intents: Sequence[RemovalIntent] | None) -> list[str]:
    """Collect depth information from features (non-through depths only)."""
    depth_lines = []

    # Collect from AST items (exclude "through" profiles, include non-through pockets/holes/engraves)
    depths_by_type: dict[str, set[str]] = {}
    for item in ast.items:
        if item.feature is None:
            continue

        ftype = item.feature.type
        depth = item.feature.depth

        # Skip "through" profiles (they're obvious from the drawing)
        if depth == "through" and ftype == "profile":
            continue

        if depth == "through":
            depth_str = "through"
        elif isinstance(depth, (int, float)):
            depth_str = f"{float(depth):.1f}mm"
        else:
            depth_str = str(depth)

        if ftype not in depths_by_type:
            depths_by_type[ftype] = set()
        depths_by_type[ftype].add(depth_str)

    # Format output
    for ftype in sorted(depths_by_type.keys()):
        depths = sorted(depths_by_type[ftype])
        if len(depths) == 1:
            depth_lines.append(f"{ftype}: {depths[0]}")
        else:
            depth_lines.append(f"{ftype}: {', '.join(depths)}")

    return depth_lines


def _count_features(ast: LayoutAST) -> dict[str, int]:
    """Count features by type."""
    counts: dict[str, int] = {}
    for item in ast.items:
        if item.feature is None:
            continue
        ftype = item.feature.type
        counts[ftype] = counts.get(ftype, 0) + 1
    return counts


def _collect_hole_diameters(ast: LayoutAST) -> list[str]:
    """Collect hole diameter specifications from circle shapes with hole features.

    Returns:
        List of formatted diameter strings (e.g., "10.0mm", "⌀8.0mm")
    """
    diameters: set[float] = set()

    for item in ast.items:
        # Only process circles with hole features
        if item.kind != "shape" or item.type != "Circle":
            continue
        if item.feature is None or item.feature.type != "hole":
            continue
        if item.geometry is None:
            continue

        # Extract diameter (prefer diameter_mm, fall back to radius_mm * 2)
        data = item.geometry.data
        diameter = data.get("diameter_mm")
        if diameter is not None:
            diameters.add(float(diameter))
        else:
            radius = data.get("radius_mm")
            if radius is not None:
                diameters.add(float(radius) * 2.0)

    # Format output (sorted for consistency)
    if not diameters:
        return []

    sorted_diameters = sorted(diameters)
    if len(sorted_diameters) == 1:
        return [f"⌀{sorted_diameters[0]:.1f}mm"]
    else:
        # Multiple diameters: show each unique size
        return [f"⌀{d:.1f}mm" for d in sorted_diameters]
