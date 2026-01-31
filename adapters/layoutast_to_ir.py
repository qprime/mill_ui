from __future__ import annotations

from typing import Sequence

from layout_ast.layout import LayoutAST, Item, Sheet
from ir.removal_intent import Bounds2D
from export.dimensions import DimensionRequest, collect_dimension_requests
from diagram_ir import DiagramIR, LayerIR, Rect, Line, Polyline, Circle, Text, Path, Point2D


def layoutast_to_diagram_ir(
    ast: LayoutAST,
    y_origin: str = "back",
    show_dimensions: bool = True,
    show_toolpaths: bool = True,
    kerf_width_mm: float = 0.0,
) -> DiagramIR:
    sheet = ast.sheet
    margin = sheet.margin_mm

    bounds = Bounds2D(
        x_min=-margin,
        x_max=sheet.width_mm + margin,
        y_min=-margin,
        y_max=sheet.height_mm + margin,
    )

    def flip_y(y: float) -> float:
        if y_origin == "back":
            return sheet.working_height_mm - y
        return y

    layers: list[LayerIR] = []

    sheet_shapes = _build_sheet_layer(sheet, margin)
    layers.append(LayerIR(name="SHEET_OUTLINE", items=tuple(sheet_shapes)))

    profile_shapes: list = []
    waste_shapes: list = []
    pocket_shapes: list = []
    hole_shapes: list = []
    engrave_shapes: list = []
    label_shapes: list = []
    toolpath_shapes: list = []

    tool_radius = kerf_width_mm / 2.0

    for item in ast.items:
        if item.kind != "shape" or item.feature is None:
            continue

        is_waste = item.shape_id and "waste" in item.shape_id
        feature_type = item.feature.type

        if feature_type == "profile":
            shapes = _item_to_shapes(item, "profile" if not is_waste else "waste", flip_y)
            if is_waste:
                waste_shapes.extend(shapes)
            else:
                profile_shapes.extend(shapes)
                if show_toolpaths and tool_radius > 0:
                    tp_shapes = _build_toolpath_shapes(item, tool_radius, flip_y)
                    toolpath_shapes.extend(tp_shapes)

        elif feature_type == "pocket":
            shapes = _item_to_shapes(item, "pocket", flip_y)
            pocket_shapes.extend(shapes)

        elif feature_type == "hole":
            shapes = _item_to_shapes(item, "hole", flip_y)
            hole_shapes.extend(shapes)
            shapes.extend(_build_hole_crosshairs(item, flip_y))
            hole_shapes.extend(shapes)

        elif feature_type == "engrave":
            shapes = _item_to_shapes(item, "engrave", flip_y)
            engrave_shapes.extend(shapes)

        elif feature_type == "notch":
            shapes = _build_notch_shapes(item, flip_y)
            profile_shapes.extend(shapes)

        if item.label and item.placement:
            label_shapes.extend(_build_label(item, flip_y))

    if profile_shapes:
        layers.append(LayerIR(name="PROFILE_CUTS", items=tuple(profile_shapes)))
    if toolpath_shapes:
        layers.append(LayerIR(name="PROFILE_TOOLPATHS", items=tuple(toolpath_shapes)))
    if waste_shapes:
        layers.append(LayerIR(name="WASTE_CUTS", items=tuple(waste_shapes)))
    if pocket_shapes:
        layers.append(LayerIR(name="POCKET_REGIONS", items=tuple(pocket_shapes)))
    if hole_shapes:
        layers.append(LayerIR(name="HOLES", items=tuple(hole_shapes)))
    if engrave_shapes:
        layers.append(LayerIR(name="ENGRAVE_PATHS", items=tuple(engrave_shapes)))
    if label_shapes:
        layers.append(LayerIR(name="LABELS", items=tuple(label_shapes)))

    dims: tuple[DimensionRequest, ...] = ()
    if show_dimensions and getattr(sheet, 'show_dimensions', True):
        dim_requests = collect_dimension_requests(
            ast, 0, 0, include_features={"profile", "pocket"}, y_flip=flip_y
        )
        dims = tuple(dim_requests)

    notes = _build_notes(ast, sheet)

    metadata = {
        "sheet_width": str(sheet.width_mm),
        "sheet_height": str(sheet.height_mm),
        "sheet_thickness": str(sheet.thickness_mm),
        "y_origin": y_origin,
    }

    return DiagramIR(
        bounds=bounds,
        layers=tuple(layers),
        dims=dims,
        notes=tuple(notes),
        metadata=metadata,
    )


def _build_sheet_layer(sheet: Sheet, margin: float) -> list:
    shapes = [
        Rect(
            x=0,
            y=0,
            width=sheet.width_mm,
            height=sheet.height_mm,
            style_token="sheet-outline",
            id="sheet_boundary",
        )
    ]

    if margin > 0:
        shapes.append(
            Rect(x=0, y=0, width=sheet.width_mm, height=margin,
                 style_token="margin-zone", id="margin_bottom")
        )
        shapes.append(
            Rect(x=0, y=sheet.height_mm - margin, width=sheet.width_mm, height=margin,
                 style_token="margin-zone", id="margin_top")
        )
        shapes.append(
            Rect(x=0, y=margin, width=margin, height=sheet.height_mm - 2 * margin,
                 style_token="margin-zone", id="margin_left")
        )
        shapes.append(
            Rect(x=sheet.width_mm - margin, y=margin, width=margin, height=sheet.height_mm - 2 * margin,
                 style_token="margin-zone", id="margin_right")
        )

    return shapes


def _item_to_shapes(item: Item, style_token: str, flip_y) -> list:
    if item.geometry is None or item.placement is None:
        return []

    cx, cy = item.placement.center_xy_mm
    cy_flipped = flip_y(cy)
    shape_type = item.type
    data = item.geometry.data
    shape_id = item.shape_id or "unnamed"

    if shape_type in ("Rect", "Rectangle"):
        w = float(data.get("w_mm") or data.get("width", 0))
        h = float(data.get("h_mm") or data.get("height", 0))
        return [
            Rect(
                x=cx - w / 2,
                y=flip_y(cy + h / 2),
                width=w,
                height=h,
                style_token=style_token,
                id=shape_id,
            )
        ]

    elif shape_type == "Circle":
        r = float(data.get("radius_mm") or data.get("diameter_mm", 0) / 2)
        return [
            Circle(
                cx=cx,
                cy=cy_flipped,
                radius=r,
                style_token=style_token,
                id=shape_id,
            )
        ]

    elif shape_type == "Polygon":
        points = data.get("points", [])
        if not points:
            return []
        transformed = [Point2D(cx + p[0], flip_y(cy + p[1])) for p in points]
        return [
            Polyline(
                points=tuple(transformed),
                closed=True,
                style_token=style_token,
                id=shape_id,
            )
        ]

    elif shape_type == "RoundedRect":
        w = float(data.get("w_mm", 0))
        h = float(data.get("h_mm", 0))
        radius = float(data.get("radius_mm", 0))
        radius_tl = float(data.get("radius_tl_mm", radius))
        radius_tr = float(data.get("radius_tr_mm", radius))
        radius_br = float(data.get("radius_br_mm", radius))
        radius_bl = float(data.get("radius_bl_mm", radius))

        x = cx - w / 2
        y = flip_y(cy + h / 2)
        path_d = _rounded_rect_path(x, y, w, h, radius_tl, radius_tr, radius_br, radius_bl)
        return [
            Path(d=path_d, style_token=style_token, id=shape_id)
        ]

    elif shape_type == "Line":
        start = data.get("start", [0, 0])
        end = data.get("end", [0, 0])
        return [
            Line(
                x1=cx + start[0],
                y1=flip_y(cy + start[1]),
                x2=cx + end[0],
                y2=flip_y(cy + end[1]),
                style_token=style_token,
                id=shape_id,
            )
        ]

    elif shape_type == "Polyline":
        points = data.get("points", [])
        if not points:
            return []
        transformed = [Point2D(cx + p[0], flip_y(cy + p[1])) for p in points]
        return [
            Polyline(
                points=tuple(transformed),
                closed=False,
                style_token=style_token,
                id=shape_id,
            )
        ]

    return []


def _build_hole_crosshairs(item: Item, flip_y) -> list:
    if item.placement is None:
        return []
    cx, cy = item.placement.center_xy_mm
    cy_flipped = flip_y(cy)
    mark_size = 3
    return [
        Line(x1=cx - mark_size, y1=cy_flipped, x2=cx + mark_size, y2=cy_flipped,
             style_token="hole", id=f"{item.shape_id or 'hole'}_cross_h"),
        Line(x1=cx, y1=cy_flipped - mark_size, x2=cx, y2=cy_flipped + mark_size,
             style_token="hole", id=f"{item.shape_id or 'hole'}_cross_v"),
    ]


def _build_notch_shapes(item: Item, flip_y) -> list:
    if item.geometry is None or item.placement is None:
        return []

    data = item.geometry.data
    try:
        edge_index = int(data.get("edge_index", 0))
        u_start_mm = float(data.get("u_start_mm", 0.0))
        u_len_mm = float(data.get("u_len_mm", 0.0))
        inset_mm = float(data.get("inset_mm", data.get("depth_mm", 0.0)))
        panel_width_mm = float(data.get("panel_width_mm", 0.0))
        panel_height_mm = float(data.get("panel_height_mm", 0.0))
    except (TypeError, ValueError):
        return []

    if u_len_mm <= 0 or inset_mm <= 0:
        return []

    cx, cy = item.placement.center_xy_mm
    half_w = panel_width_mm / 2.0
    half_h = panel_height_mm / 2.0

    if edge_index == 0:
        x_min = cx - half_w + u_start_mm
        y_min = cy - half_h
        w, h = u_len_mm, inset_mm
    elif edge_index == 2:
        x_min = cx - half_w + u_start_mm
        y_min = cy + half_h - inset_mm
        w, h = u_len_mm, inset_mm
    elif edge_index == 1:
        x_min = cx + half_w - inset_mm
        y_min = cy - half_h + u_start_mm
        w, h = inset_mm, u_len_mm
    else:
        x_min = cx - half_w
        y_min = cy - half_h + u_start_mm
        w, h = inset_mm, u_len_mm

    y0 = flip_y(y_min)
    y1 = flip_y(y_min + h)
    y_draw = min(y0, y1)
    h_draw = abs(y1 - y0)

    return [
        Rect(
            x=x_min,
            y=y_draw,
            width=w,
            height=h_draw,
            style_token="profile",
            id=item.shape_id or "notch",
        )
    ]


def _build_toolpath_shapes(item: Item, tool_radius: float, flip_y) -> list:
    if item.geometry is None or item.feature is None or item.placement is None:
        return []
    if tool_radius <= 0:
        return []

    side = (item.feature.side or "on").lower()
    offset = 0.0
    if side == "outside":
        offset = tool_radius
    elif side == "inside":
        offset = -tool_radius

    if offset == 0:
        return []

    shape_type = item.type
    cx, cy = item.placement.center_xy_mm
    data = item.geometry.data

    if shape_type in ("Rect", "Rectangle"):
        w = float(data.get("w_mm") or data.get("width", 0))
        h = float(data.get("h_mm") or data.get("height", 0))
        if w <= 0 or h <= 0:
            return []

        new_w = w + 2 * offset
        new_h = h + 2 * offset
        if new_w <= 0 or new_h <= 0:
            return []

        return [
            Rect(
                x=cx - new_w / 2,
                y=flip_y(cy + new_h / 2),
                width=new_w,
                height=new_h,
                style_token="toolpath",
                id=f"{item.shape_id or 'item'}_toolpath",
            )
        ]

    return []


def _build_label(item: Item, flip_y) -> list:
    if not item.label or item.placement is None:
        return []
    cx, cy = item.placement.center_xy_mm
    return [
        Text(
            x=cx,
            y=flip_y(cy),
            content=item.label,
            style_token="label",
            anchor="middle",
            baseline="middle",
            id=f"{item.shape_id or 'item'}_label",
        )
    ]


def _build_notes(ast: LayoutAST, sheet: Sheet) -> list[Text]:
    notes = []

    notes.append(
        Text(
            x=5,
            y=sheet.height_mm - 5,
            content=f"Sheet: {sheet.width_mm:.0f} × {sheet.height_mm:.0f} × {sheet.thickness_mm:.0f}mm",
            style_token="notes",
            anchor="start",
            baseline="text-top",
        )
    )

    return notes


def _rounded_rect_path(
    x: float, y: float, w: float, h: float,
    radius_tl: float, radius_tr: float, radius_br: float, radius_bl: float
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


__all__ = ["layoutast_to_diagram_ir"]
