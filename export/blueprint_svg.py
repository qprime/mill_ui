
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence
from xml.etree import ElementTree as ET

from core.constants import DepthMode
from layout_ast.layout import LayoutAST, Item, Sheet
from ir.removal_intent import RemovalIntent, Bounds2D
from export.dimensions import place_dimensions_on_rails, render_placed_dimension, render_gap_dimension


@dataclass(frozen=True)
class Theme:
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
    engrave_width: str
    construction_stroke: str
    construction_dash: str
    dimension_stroke: str
    dimension_text: str
    gap_stroke: str
    gap_text: str
    notes_text: str
    legend_text: str
    label_text: str
    waste_stroke: str
    waste_dash: str


DARK_THEME = Theme(
    background="#1a1a1a",
    foreground="#e8e8e8",
    profile_stroke="#e8e8e8",
    profile_width="2",
    pocket_stroke="#6496c8",
    pocket_fill="#6496c8",
    pocket_width="1.5",
    hole_stroke="#e8e8e8",
    hole_fill="none",
    engrave_stroke="#888888",
    engrave_width="0.25",
    construction_stroke="#6b8e7f",
    construction_dash="2,2",
    dimension_stroke="#5ab9ea",
    dimension_text="#5ab9ea",
    gap_stroke="#ff9500",
    gap_text="#ff9500",
    notes_text="#cccccc",
    legend_text="#cccccc",
    label_text="#ffcc00",
    waste_stroke="#ff9500",
    waste_dash="8,4",
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
    engrave_width="0.25",
    construction_stroke="#666666",
    construction_dash="2,2",
    dimension_stroke="#333333",
    dimension_text="#333333",
    gap_stroke="#cc6600",
    gap_text="#cc6600",
    notes_text="#000000",
    legend_text="#000000",
    label_text="#333333",
    waste_stroke="#cc6600",
    waste_dash="8,4",
)

THEMES = {
    "dark": DARK_THEME,
    "print": PRINT_THEME,
}


def render_blueprint_svg(
    layout_ast: LayoutAST,
    removal_intents: Sequence[RemovalIntent] | None = None,
    theme: str = "dark",
    y_origin: str = "back",
) -> str:
    theme_obj = THEMES.get(theme, DARK_THEME)
    sheet = layout_ast.sheet

    sheet_margin = sheet.margin_mm

    svg_margin = 140
    viewbox_width = sheet.width_mm + 2 * svg_margin
    viewbox_height = sheet.height_mm + 2 * svg_margin

    svg = ET.Element(
        "svg",
        {
            "xmlns": "http://www.w3.org/2000/svg",
            "viewBox": f"0 0 {viewbox_width} {viewbox_height}",
            "width": f"{viewbox_width}mm",
            "height": f"{viewbox_height}mm",
        },
    )


    style = ET.SubElement(svg, "style")
    style.text = _generate_stylesheet(theme_obj)


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


    offset_x = svg_margin + sheet_margin
    offset_y = svg_margin + sheet_margin

    def flip_y(y: float) -> float:
        if y_origin == "back":
            return sheet.working_height_mm - y
        return y

    sheet_group = ET.SubElement(svg, "g", {"id": "SHEET_OUTLINE", "class": "sheet-outline"})
    profile_group = ET.SubElement(svg, "g", {"id": "PROFILE_CUTS", "class": "profile-cuts"})
    toolpath_group = ET.SubElement(svg, "g", {"id": "PROFILE_TOOLPATHS", "class": "profile-toolpaths"})
    waste_group = ET.SubElement(svg, "g", {"id": "WASTE_CUTS", "class": "waste-cuts"})
    pocket_group = ET.SubElement(svg, "g", {"id": "POCKET_REGIONS", "class": "pocket-regions"})
    engrave_group = ET.SubElement(svg, "g", {"id": "ENGRAVE_PATHS", "class": "engrave-paths"})
    hole_group = ET.SubElement(svg, "g", {"id": "HOLES", "class": "holes"})
    label_group = ET.SubElement(svg, "g", {"id": "LABELS", "class": "labels"})
    edge_color_group = ET.SubElement(svg, "g", {"id": "EDGE_COLORS", "class": "edge-colors"})
    construction_group = ET.SubElement(svg, "g", {"id": "CONSTRUCTION", "class": "construction"})
    dimension_group = ET.SubElement(svg, "g", {"id": "DIMENSIONS", "class": "dimensions"})
    notes_group = ET.SubElement(svg, "g", {"id": "NOTES", "class": "notes"})
    title_group = ET.SubElement(svg, "g", {"id": "TITLE_BLOCK", "class": "title-block"})
    legend_group = ET.SubElement(svg, "g", {"id": "LEGEND", "class": "legend"})


    _render_sheet_boundary(sheet_group, sheet, svg_margin, svg_margin, theme_obj)


    has_waste_cuts = False
    try:
        tool_radius_mm = float(layout_ast.kerf_width_mm or 0.0) / 2.0
    except (TypeError, ValueError):
        tool_radius_mm = 0.0

    for item in layout_ast.items:
        if item.kind != "shape" or item.feature is None:
            continue

        is_waste = item.shape_id and "waste" in item.shape_id
        if is_waste:
            has_waste_cuts = True

        feature_type = item.feature.type
        if feature_type == "profile":
            target_group = waste_group if is_waste else profile_group
            _render_profile(target_group, item, offset_x, offset_y, theme_obj, y_flip=flip_y)
            if tool_radius_mm > 0.0 and not is_waste:
                _render_profile_toolpath(toolpath_group, item, offset_x, offset_y, tool_radius_mm, y_flip=flip_y)
        elif feature_type == "notch":
            # Notches are edge cutouts; render them in the PROFILE_CUTS layer so
            # the blueprint reflects the final cut geometry users expect.
            _render_notch(profile_group, item, offset_x, offset_y, y_flip=flip_y)
        elif feature_type == "pocket":
            _render_pocket(pocket_group, item, offset_x, offset_y, theme_obj, y_flip=flip_y)
        elif feature_type == "hole":
            _render_hole(hole_group, item, offset_x, offset_y, theme_obj, y_flip=flip_y)
        elif feature_type == "engrave":
            _render_engrave(engrave_group, item, offset_x, offset_y, theme_obj, y_flip=flip_y)

        if item.label and item.placement:
            _render_label(label_group, item, offset_x, offset_y, y_flip=flip_y)

        if item.params and "edge_lines" in item.params:
            _render_edge_colors(edge_color_group, item, offset_x, offset_y, y_flip=flip_y)


    if getattr(sheet, 'show_dimensions', True):
        _render_dimensions(dimension_group, layout_ast, offset_x, offset_y, svg_margin, theme_obj, y_flip=flip_y)


    _render_title_block(title_group, viewbox_width, viewbox_height, theme_obj)
    _render_legend(legend_group, viewbox_width, theme_obj, has_waste_cuts=has_waste_cuts)
    _render_notes(notes_group, layout_ast, removal_intents, viewbox_height, theme_obj)


    ET.indent(svg, space="  ")
    return ET.tostring(svg, encoding="unicode")


def _generate_stylesheet(theme: Theme) -> str:
    return f"""
        .sheet-outline {{ stroke: {theme.construction_stroke}; stroke-width: 1; fill: none; stroke-dasharray: {theme.construction_dash}; }}
        .profile-cuts {{ stroke: {theme.profile_stroke}; stroke-width: {theme.profile_width}; fill: none; }}
        .profile-toolpaths {{ stroke: {theme.dimension_stroke}; stroke-width: 1; fill: none; stroke-dasharray: 4,2; }}
        .waste-cuts {{ stroke: {theme.waste_stroke}; stroke-width: {theme.profile_width}; fill: none; stroke-dasharray: {theme.waste_dash}; }}
        .pocket-regions {{ stroke: {theme.pocket_stroke}; stroke-width: {theme.pocket_width}; fill: {theme.pocket_fill}; fill-opacity: 0.2; }}
        .holes {{ stroke: {theme.hole_stroke}; stroke-width: 1.5; fill: {theme.hole_fill}; }}
        .engrave-paths {{ stroke: {theme.engrave_stroke}; stroke-width: {theme.engrave_width}; fill: none; }}
        .construction {{ stroke: {theme.construction_stroke}; stroke-width: 0.5; fill: none; stroke-dasharray: {theme.construction_dash}; }}
        .dimensions {{ stroke: {theme.dimension_stroke}; stroke-width: 1; fill: none; }}
        .dimension-text {{ fill: {theme.dimension_text}; font-family: monospace; font-size: 10px; }}
        .gap-dimensions {{ stroke: {theme.gap_stroke}; stroke-width: 1; fill: none; }}
        .gap-text {{ fill: {theme.gap_text}; font-family: monospace; font-size: 10px; }}
        .notes {{ fill: {theme.notes_text}; font-family: monospace; font-size: 10px; }}
        .legend {{ fill: {theme.legend_text}; font-family: monospace; font-size: 10px; }}
        .part-label {{ fill: {theme.label_text}; font-family: monospace; font-size: 8px; font-weight: bold; }}
        .edge-label {{ fill: {theme.label_text}; font-family: monospace; font-size: 7px; }}
    """


def _render_sheet_boundary(group: ET.Element, sheet: Sheet, offset_x: float, offset_y: float, theme: Theme) -> None:
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

    margin = sheet.margin_mm
    if margin > 0.0:
        margin_group = ET.SubElement(group, "g", {"class": "margin-zone"})

        ET.SubElement(
            margin_group,
            "rect",
            {
                "x": str(offset_x),
                "y": str(offset_y),
                "width": str(sheet.width_mm),
                "height": str(margin),
                "fill": theme.construction_stroke,
                "fill-opacity": "0.15",
            },
        )

        ET.SubElement(
            margin_group,
            "rect",
            {
                "x": str(offset_x),
                "y": str(offset_y + sheet.height_mm - margin),
                "width": str(sheet.width_mm),
                "height": str(margin),
                "fill": theme.construction_stroke,
                "fill-opacity": "0.15",
            },
        )

        ET.SubElement(
            margin_group,
            "rect",
            {
                "x": str(offset_x),
                "y": str(offset_y + margin),
                "width": str(margin),
                "height": str(sheet.height_mm - 2 * margin),
                "fill": theme.construction_stroke,
                "fill-opacity": "0.15",
            },
        )

        ET.SubElement(
            margin_group,
            "rect",
            {
                "x": str(offset_x + sheet.width_mm - margin),
                "y": str(offset_y + margin),
                "width": str(margin),
                "height": str(sheet.height_mm - 2 * margin),
                "fill": theme.construction_stroke,
                "fill-opacity": "0.15",
            },
        )


def _rounded_rect_path(
    x: float,
    y: float,
    w: float,
    h: float,
    radius_tl: float,
    radius_tr: float,
    radius_br: float,
    radius_bl: float,
) -> str:
    rtl = min(radius_tl, w / 2, h / 2)
    rtr = min(radius_tr, w / 2, h / 2)
    rbr = min(radius_br, w / 2, h / 2)
    rbl = min(radius_bl, w / 2, h / 2)

    parts = [f"M {x + rtl:.3f} {y:.3f}"]
    parts.append(f"L {x + w - rtr:.3f} {y:.3f}")
    if rtr > 0:
        parts.append(f"A {rtr:.3f} {rtr:.3f} 0 0 1 {x + w:.3f} {y + rtr:.3f}")
    parts.append(f"L {x + w:.3f} {y + h - rbr:.3f}")
    if rbr > 0:
        parts.append(f"A {rbr:.3f} {rbr:.3f} 0 0 1 {x + w - rbr:.3f} {y + h:.3f}")
    parts.append(f"L {x + rbl:.3f} {y + h:.3f}")
    if rbl > 0:
        parts.append(f"A {rbl:.3f} {rbl:.3f} 0 0 1 {x:.3f} {y + h - rbl:.3f}")
    parts.append(f"L {x:.3f} {y + rtl:.3f}")
    if rtl > 0:
        parts.append(f"A {rtl:.3f} {rtl:.3f} 0 0 1 {x + rtl:.3f} {y:.3f}")
    parts.append("Z")
    return " ".join(parts)


def _polygon_to_path(
    points: list,
    holes: list,
    offset_x: float,
    offset_y: float,
    center_x: float = 0.0,
    center_y: float = 0.0,
    y_flip=None,
) -> str:
    if not points:
        return ""

    yf = y_flip if y_flip is not None else (lambda y: y)

    def ring_to_path(ring: list) -> str:
        if not ring:
            return ""
        parts = [f"M {ring[0][0] + center_x + offset_x:.3f} {yf(ring[0][1] + center_y) + offset_y:.3f}"]
        for x, y in ring[1:]:
            parts.append(f"L {x + center_x + offset_x:.3f} {yf(y + center_y) + offset_y:.3f}")
        parts.append("Z")
        return " ".join(parts)

    segments = [ring_to_path(points)]
    for hole in holes or []:
        if hole:
            segments.append(ring_to_path(hole))
    return " ".join(segments)


def _render_profile(group: ET.Element, item: Item, offset_x: float, offset_y: float, theme: Theme, y_flip=None) -> None:
    if item.geometry is None:
        return

    shape_type = item.type

    yf = y_flip if y_flip is not None else (lambda y: y)

    if item.placement is None:
        return

    cx, orig_cy = item.placement.center_xy_mm
    cy = yf(orig_cy)

    if shape_type == "Line":
        start = item.geometry.data.get("start", [0, 0])
        end = item.geometry.data.get("end", [0, 0])
        ET.SubElement(
            group,
            "line",
            {
                "x1": str(offset_x + cx + start[0]),
                "y1": str(offset_y + yf(orig_cy + start[1])),
                "x2": str(offset_x + cx + end[0]),
                "y2": str(offset_y + yf(orig_cy + end[1])),
            },
        )
        return

    if shape_type in ("Rect", "Rectangle"):
        w = item.geometry.data.get("w_mm") or item.geometry.data.get("width", 0)
        h = item.geometry.data.get("h_mm") or item.geometry.data.get("height", 0)
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
    elif shape_type == "Polygon":
        points = item.geometry.data.get("points", [])
        holes = item.geometry.data.get("holes", [])
        orig_cx, orig_cy = item.placement.center_xy_mm
        path_d = _polygon_to_path(points, holes, offset_x, offset_y, center_x=orig_cx, center_y=orig_cy, y_flip=yf)
        if path_d:
            ET.SubElement(group, "path", {"d": path_d, "fill-rule": "evenodd"})
    elif shape_type == "Polyline":
        points = item.geometry.data.get("points", [])
        if points:
            points_str = " ".join(f"{x + cx + offset_x},{yf(orig_cy + y) + offset_y}" for x, y in points)
            ET.SubElement(group, "polyline", {"points": points_str})
    elif shape_type == "RoundedRect":
        w = item.geometry.data.get("w_mm", 0)
        h = item.geometry.data.get("h_mm", 0)
        radius_tl = item.geometry.data.get("radius_tl_mm", item.geometry.data.get("radius_mm", 0))
        radius_tr = item.geometry.data.get("radius_tr_mm", item.geometry.data.get("radius_mm", 0))
        radius_br = item.geometry.data.get("radius_br_mm", item.geometry.data.get("radius_mm", 0))
        radius_bl = item.geometry.data.get("radius_bl_mm", item.geometry.data.get("radius_mm", 0))
        x = offset_x + cx - w / 2
        y = offset_y + cy - h / 2
        path_d = _rounded_rect_path(x, y, w, h, radius_tl, radius_tr, radius_br, radius_bl)
        ET.SubElement(group, "path", {"d": path_d})


def _render_profile_toolpath(group: ET.Element, item: Item, offset_x: float, offset_y: float, tool_radius_mm: float, y_flip=None) -> None:
    if item.geometry is None or item.feature is None or item.placement is None:
        return
    if tool_radius_mm <= 0.0:
        return

    side = (item.feature.side or "on").lower()
    offset = 0.0
    if side == "outside":
        offset = tool_radius_mm
    elif side == "inside":
        offset = -tool_radius_mm
    else:
        offset = 0.0

    yf = y_flip if y_flip is not None else (lambda y: y)

    shape_type = item.type
    cx, cy = item.placement.center_xy_mm

    if shape_type in ("Rect", "Rectangle"):
        w = float(item.geometry.data.get("w_mm") or item.geometry.data.get("width", 0.0))
        h = float(item.geometry.data.get("h_mm") or item.geometry.data.get("height", 0.0))
        if w <= 0.0 or h <= 0.0:
            return
        x_min = cx - w / 2.0
        x_max = cx + w / 2.0
        y_min = cy - h / 2.0
        y_max = cy + h / 2.0

        from shapely.geometry import box as shapely_box
        from shapely.ops import orient
        from shapely import BufferJoinStyle

        poly = shapely_box(x_min, y_min, x_max, y_max)
        if offset != 0.0:
            poly = poly.buffer(offset, join_style=BufferJoinStyle.mitre, mitre_limit=2.0)
        poly = orient(poly, sign=1.0)
        if poly.is_empty or not hasattr(poly, "exterior"):
            return
        points = list(poly.exterior.coords[:-1])
        path_d = _polygon_to_path(points, [], offset_x, offset_y, center_x=0.0, center_y=0.0, y_flip=yf)
        if path_d:
            ET.SubElement(group, "path", {"d": path_d, "fill-rule": "evenodd"})
        return

    if shape_type == "Polygon":
        points = item.geometry.data.get("points", [])
        holes = item.geometry.data.get("holes", [])
        if not points:
            return

        abs_points = [(float(x) + cx, float(y) + cy) for x, y in points]
        abs_holes: list[list[tuple[float, float]]] = []
        for hole in holes or []:
            abs_holes.append([(float(x) + cx, float(y) + cy) for x, y in hole])

        from shapely.geometry import Polygon as ShapelyPolygon, MultiPolygon
        from shapely.ops import orient
        from shapely import BufferJoinStyle

        poly = ShapelyPolygon(abs_points, abs_holes if abs_holes else None)
        if offset != 0.0:
            poly = poly.buffer(offset, join_style=BufferJoinStyle.mitre, mitre_limit=2.0)

        if poly.is_empty:
            return

        polys = []
        if isinstance(poly, MultiPolygon):
            polys = list(poly.geoms)
        else:
            polys = [poly]

        for p in polys:
            p = orient(p, sign=1.0)
            if p.is_empty or not hasattr(p, "exterior"):
                continue
            exterior = list(p.exterior.coords[:-1])
            interior_rings = [list(r.coords[:-1]) for r in getattr(p, "interiors", [])]
            path_d = _polygon_to_path(exterior, interior_rings, offset_x, offset_y, center_x=0.0, center_y=0.0, y_flip=yf)
            if path_d:
                ET.SubElement(group, "path", {"d": path_d, "fill-rule": "evenodd"})
        return


def _render_notch(group: ET.Element, item: Item, offset_x: float, offset_y: float, y_flip=None) -> None:
    if item.geometry is None or item.placement is None:
        return

    data = item.geometry.data
    try:
        edge_index = int(data.get("edge_index", 0))
        u_start_mm = float(data.get("u_start_mm", 0.0))
        u_len_mm = float(data.get("u_len_mm", 0.0))
        inset_mm = float(data.get("inset_mm", data.get("depth_mm", 0.0)))
        panel_width_mm = float(data.get("panel_width_mm", 0.0))
        panel_height_mm = float(data.get("panel_height_mm", 0.0))
    except (TypeError, ValueError):
        return

    if u_len_mm <= 0.0 or inset_mm <= 0.0 or panel_width_mm <= 0.0 or panel_height_mm <= 0.0:
        return

    cx, cy = item.placement.center_xy_mm
    half_w = panel_width_mm / 2.0
    half_h = panel_height_mm / 2.0

    if edge_index == 0:
        x_min = cx - half_w + u_start_mm
        y_min = cy - half_h
        w = u_len_mm
        h = inset_mm
    elif edge_index == 2:
        x_min = cx - half_w + u_start_mm
        y_min = cy + half_h - inset_mm
        w = u_len_mm
        h = inset_mm
    elif edge_index == 1:
        x_min = cx + half_w - inset_mm
        y_min = cy - half_h + u_start_mm
        w = inset_mm
        h = u_len_mm
    else:
        x_min = cx - half_w
        y_min = cy - half_h + u_start_mm
        w = inset_mm
        h = u_len_mm

    yf = y_flip if y_flip is not None else (lambda y: y)
    y0 = yf(y_min)
    y1 = yf(y_min + h)
    y = min(y0, y1)
    h_draw = abs(y1 - y0)

    ET.SubElement(
        group,
        "rect",
        {
            "x": str(offset_x + x_min),
            "y": str(offset_y + y),
            "width": str(w),
            "height": str(h_draw),
        },
    )


def _render_pocket(group: ET.Element, item: Item, offset_x: float, offset_y: float, theme: Theme, y_flip=None) -> None:
    if item.geometry is None or item.placement is None:
        return

    yf = y_flip if y_flip is not None else (lambda y: y)
    shape_type = item.type
    cx, cy = item.placement.center_xy_mm
    cy = yf(cy)

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
    elif shape_type == "Polygon":
        points = item.geometry.data.get("points", [])
        holes = item.geometry.data.get("holes", [])
        orig_cx, orig_cy = item.placement.center_xy_mm
        path_d = _polygon_to_path(points, holes, offset_x, offset_y, center_x=orig_cx, center_y=orig_cy, y_flip=yf)
        if path_d:
            ET.SubElement(group, "path", {"d": path_d, "fill-rule": "evenodd"})
    elif shape_type == "RoundedRect":
        w = item.geometry.data.get("w_mm", 0)
        h = item.geometry.data.get("h_mm", 0)
        radius_tl = item.geometry.data.get("radius_tl_mm", item.geometry.data.get("radius_mm", 0))
        radius_tr = item.geometry.data.get("radius_tr_mm", item.geometry.data.get("radius_mm", 0))
        radius_br = item.geometry.data.get("radius_br_mm", item.geometry.data.get("radius_mm", 0))
        radius_bl = item.geometry.data.get("radius_bl_mm", item.geometry.data.get("radius_mm", 0))
        x = offset_x + cx - w / 2
        y = offset_y + cy - h / 2
        path_d = _rounded_rect_path(x, y, w, h, radius_tl, radius_tr, radius_br, radius_bl)
        ET.SubElement(group, "path", {"d": path_d})


def _render_hole(group: ET.Element, item: Item, offset_x: float, offset_y: float, theme: Theme, y_flip=None) -> None:
    if item.geometry is None or item.placement is None:
        return

    yf = y_flip if y_flip is not None else (lambda y: y)
    cx, cy = item.placement.center_xy_mm
    abs_cx = offset_x + cx
    abs_cy = offset_y + yf(cy)


    d = item.geometry.data.get("diameter_mm", item.geometry.data.get("radius_mm", 5) * 2)
    r = d / 2


    ET.SubElement(
        group,
        "circle",
        {
            "cx": str(abs_cx),
            "cy": str(abs_cy),
            "r": str(r),
        },
    )


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


def _render_engrave(group: ET.Element, item: Item, offset_x: float, offset_y: float, theme: Theme, y_flip=None) -> None:
    _render_profile(group, item, offset_x, offset_y, theme, y_flip=y_flip)


def _render_label(group: ET.Element, item: Item, offset_x: float, offset_y: float, y_flip=None) -> None:
    if not item.label or item.placement is None:
        return

    yf = y_flip if y_flip is not None else (lambda y: y)
    cx, cy = item.placement.center_xy_mm
    label_elem = ET.SubElement(
        group,
        "text",
        {
            "x": str(offset_x + cx),
            "y": str(offset_y + yf(cy)),
            "class": "part-label",
            "text-anchor": "middle",
            "dominant-baseline": "middle",
        },
    )
    label_elem.text = item.label


def _render_edge_colors(group: ET.Element, item: Item, offset_x: float, offset_y: float, y_flip=None) -> None:
    if item.params is None or "edge_lines" not in item.params:
        return

    yf = y_flip if y_flip is not None else (lambda y: y)
    edge_lines = item.params["edge_lines"]

    for line in edge_lines:
        ET.SubElement(
            group,
            "line",
            {
                "x1": str(offset_x + line["x1"]),
                "y1": str(offset_y + yf(line["y1"])),
                "x2": str(offset_x + line["x2"]),
                "y2": str(offset_y + yf(line["y2"])),
                "stroke": line["color"],
                "stroke-width": "3",
                "stroke-linecap": "round",
            },
        )

    edge_labels = item.params.get("edge_labels", [])
    for label in edge_labels:
        label_elem = ET.SubElement(
            group,
            "text",
            {
                "x": str(offset_x + label["x"]),
                "y": str(offset_y + yf(label["y"])),
                "class": "edge-label",
                "text-anchor": label.get("anchor", "middle"),
                "dominant-baseline": "middle",
                "fill": label.get("color", "#ffffff"),
            },
        )
        label_elem.text = label["text"]


def _render_dimensions(
    group: ET.Element,
    ast: LayoutAST,
    offset_x: float,
    offset_y: float,
    margin: float,
    theme: Theme,
    y_flip=None,
) -> None:
    yf = y_flip if y_flip is not None else (lambda y: y)
    dims = place_dimensions_on_rails(ast, offset_x, offset_y, margin=margin, include_features={"profile", "pocket"}, y_flip=yf)
    for dim in dims:
        render_placed_dimension(group, dim, theme.dimension_stroke)

    _render_gap_dimensions(group, ast, offset_x, offset_y, theme, y_flip=yf)


def _render_gap_dimensions(
    group: ET.Element,
    ast: LayoutAST,
    offset_x: float,
    offset_y: float,
    theme: Theme,
    y_flip=None,
) -> None:
    yf = y_flip if y_flip is not None else (lambda y: y)

    profile_items = [
        item for item in ast.items
        if item.kind == "shape"
        and item.feature is not None
        and item.feature.type == "profile"
        and item.geometry is not None
        and item.placement is not None
        and item.type in ("Rect", "RoundedRect")
    ]

    if not profile_items:
        return


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


    def get_bounds(item: Item) -> dict:
        cx, cy = item.placement.center_xy_mm
        cy_t = yf(cy)
        w = float(item.geometry.data.get("w_mm", 0))
        h = float(item.geometry.data.get("h_mm", 0))
        return {
            "cx": cx,
            "cy": cy_t,
            "x_min": cx - w / 2.0,
            "x_max": cx + w / 2.0,
            "y_min": cy_t - h / 2.0,
            "y_max": cy_t + h / 2.0,
            "w": w,
            "h": h,
        }

    def contains(profile_bounds: dict, pocket_bounds: dict) -> bool:
        return (
            profile_bounds["x_min"] <= pocket_bounds["x_min"]
            and profile_bounds["x_max"] >= pocket_bounds["x_max"]
            and profile_bounds["y_min"] <= pocket_bounds["y_min"]
            and profile_bounds["y_max"] >= pocket_bounds["y_max"]
        )


    profile_pocket_groups: list[tuple[dict, list[dict]]] = []
    pocket_bounds_list = [get_bounds(p) for p in pocket_items]
    assigned_pockets: set[int] = set()

    for profile in profile_items:
        pb = get_bounds(profile)
        contained_pockets = []
        for i, pocket_b in enumerate(pocket_bounds_list):
            if i not in assigned_pockets and contains(pb, pocket_b):
                contained_pockets.append(pocket_b)
                assigned_pockets.add(i)
        if contained_pockets:
            profile_pocket_groups.append((pb, contained_pockets))

    if not profile_pocket_groups:
        return


    rendered_h_gaps: set[int] = set()
    rendered_v_gaps: set[int] = set()


    for profile_bounds, pockets in profile_pocket_groups:
        if not pockets:
            continue


        left_gap = min(p["x_min"] - profile_bounds["x_min"] for p in pockets)
        top_gap = min(p["y_min"] - profile_bounds["y_min"] for p in pockets)

        left_gap_key = round(left_gap)
        if left_gap > 5.0 and left_gap_key not in rendered_h_gaps:
            rendered_h_gaps.add(left_gap_key)
            y_center = (profile_bounds["y_min"] + profile_bounds["y_max"]) / 2.0
            render_gap_dimension(
                group,
                offset_x + profile_bounds["x_min"],
                offset_x + profile_bounds["x_min"] + left_gap,
                "horizontal",
                offset_y + y_center,
                f"{left_gap:.0f}mm",
                theme.gap_stroke,
            )

        top_gap_key = round(top_gap)
        if top_gap > 5.0 and top_gap_key not in rendered_v_gaps:
            rendered_v_gaps.add(top_gap_key)
            x_center = (profile_bounds["x_min"] + profile_bounds["x_max"]) / 2.0
            render_gap_dimension(
                group,
                offset_y + profile_bounds["y_min"],
                offset_y + profile_bounds["y_min"] + top_gap,
                "vertical",
                offset_x + x_center,
                f"{top_gap:.0f}mm",
                theme.gap_stroke,
            )


        if len(pockets) < 2:
            continue


        sorted_by_x = sorted(pockets, key=lambda p: p["x_min"])
        for i in range(len(sorted_by_x) - 1):
            curr = sorted_by_x[i]
            next_p = sorted_by_x[i + 1]
            gap = next_p["x_min"] - curr["x_max"]
            gap_key = round(gap)
            if gap > 5.0 and gap_key not in rendered_h_gaps:

                y_overlap = not (curr["y_max"] < next_p["y_min"] or curr["y_min"] > next_p["y_max"])
                if y_overlap:
                    rendered_h_gaps.add(gap_key)
                    y_pos = (max(curr["y_min"], next_p["y_min"]) + min(curr["y_max"], next_p["y_max"])) / 2.0
                    render_gap_dimension(
                        group,
                        offset_x + curr["x_max"],
                        offset_x + next_p["x_min"],
                        "horizontal",
                        offset_y + y_pos,
                        f"{gap:.0f}mm",
                        theme.gap_stroke,
                    )


        sorted_by_y = sorted(pockets, key=lambda p: p["y_min"])
        for i in range(len(sorted_by_y) - 1):
            curr = sorted_by_y[i]
            next_p = sorted_by_y[i + 1]
            gap = next_p["y_min"] - curr["y_max"]
            gap_key = round(gap)
            if gap > 5.0 and gap_key not in rendered_v_gaps:

                x_overlap = not (curr["x_max"] < next_p["x_min"] or curr["x_min"] > next_p["x_max"])
                if x_overlap:
                    rendered_v_gaps.add(gap_key)
                    x_pos = (max(curr["x_min"], next_p["x_min"]) + min(curr["x_max"], next_p["x_max"])) / 2.0
                    render_gap_dimension(
                        group,
                        offset_y + curr["y_max"],
                        offset_y + next_p["y_min"],
                        "vertical",
                        offset_x + x_pos,
                        f"{gap:.0f}mm",
                        theme.gap_stroke,
                    )

def _render_title_block(group: ET.Element, viewbox_width: float, viewbox_height: float, theme: Theme) -> None:
    x = 20
    y = 20
    line_height = 14


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


def _render_legend(group: ET.Element, viewbox_width: float, theme: Theme, has_waste_cuts: bool = False) -> None:
    x = viewbox_width - 132
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


    layers = [
        ("Sheet Outline", theme.construction_stroke, "1", theme.construction_dash, None),
        ("Profile Cuts", theme.profile_stroke, "2", None, None),
        ("Pocket Regions", theme.pocket_stroke, "1.5", None, theme.pocket_fill),
        ("Holes", theme.hole_stroke, "1.5", None, None),
        ("Dimensions", theme.dimension_stroke, "1", None, None),
    ]

    if has_waste_cuts:
        layers.append(("Waste Cuts", theme.waste_stroke, "2", theme.waste_dash, None))

    for i, (label, stroke, width, dash, fill) in enumerate(layers):
        y_pos = y + (i + 1) * line_height + 5


        if fill:

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
    x = 20
    y = viewbox_height - 120
    line_height = 12


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


    depths_info = _collect_depth_info(ast, removal_intents)
    hole_diameters = _collect_hole_diameters(ast)
    feature_counts = _count_features(ast)
    part_inventory = _collect_part_inventory(ast)

    line_num = 1


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

    if part_inventory:
        parts_title = ET.SubElement(
            group,
            "text",
            {
                "x": str(x),
                "y": str(y + line_num * line_height),
                "class": "notes",
            },
        )
        parts_title.text = f"Parts ({len(part_inventory)}):"
        line_num += 1

        for part_id in part_inventory:
            part_elem = ET.SubElement(
                group,
                "text",
                {
                    "x": str(x + 10),
                    "y": str(y + line_num * line_height),
                    "class": "notes",
                },
            )
            part_elem.text = f"• {part_id}"
            line_num += 1


def _collect_depth_info(ast: LayoutAST, removal_intents: Sequence[RemovalIntent] | None) -> list[str]:
    depth_lines = []


    depths_by_type: dict[str, set[str]] = {}
    for item in ast.items:
        if item.feature is None:
            continue

        ftype = item.feature.type
        depth = item.feature.depth


        if DepthMode.is_through(depth) and ftype == "profile":
            continue

        if DepthMode.is_through(depth):
            depth_str = DepthMode.THROUGH
        elif isinstance(depth, (int, float)):
            depth_str = f"{float(depth):.1f}mm"
        else:
            depth_str = str(depth)

        if ftype not in depths_by_type:
            depths_by_type[ftype] = set()
        depths_by_type[ftype].add(depth_str)


    for ftype in sorted(depths_by_type.keys()):
        depths = sorted(depths_by_type[ftype])
        if len(depths) == 1:
            depth_lines.append(f"{ftype}: {depths[0]}")
        else:
            depth_lines.append(f"{ftype}: {', '.join(depths)}")

    return depth_lines


def _count_features(ast: LayoutAST) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in ast.items:
        if item.feature is None:
            continue
        ftype = item.feature.type
        counts[ftype] = counts.get(ftype, 0) + 1
    return counts


def _collect_hole_diameters(ast: LayoutAST) -> list[str]:
    diameters: set[float] = set()

    for item in ast.items:
        if item.kind != "shape" or item.type != "Circle":
            continue
        if item.feature is None or item.feature.type != "hole":
            continue
        if item.geometry is None:
            continue

        data = item.geometry.data
        diameter = data.get("diameter_mm")
        if diameter is not None:
            diameters.add(float(diameter))
        else:
            radius = data.get("radius_mm")
            if radius is not None:
                diameters.add(float(radius) * 2.0)

    if not diameters:
        return []

    sorted_diameters = sorted(diameters)
    if len(sorted_diameters) == 1:
        return [f"⌀{sorted_diameters[0]:.1f}mm"]
    else:
        return [f"⌀{d:.1f}mm" for d in sorted_diameters]


def _collect_part_inventory(ast: LayoutAST) -> list[str]:
    parts: list[str] = []

    for item in ast.items:
        if item.kind != "shape" or item.feature is None:
            continue
        if not item.shape_id:
            continue
        if item.shape_id.startswith("generated_"):
            continue

        parts.append(item.shape_id)

    return sorted(set(parts))
