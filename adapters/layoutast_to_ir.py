from __future__ import annotations

from collections.abc import Callable

from core.constants import DepthMode
from diagram_ir import Circle, DiagramIR, LayerIR, Line, Path, Point2D, Polyline, Rect, Text
from diagram_ir.dimensions import DimensionRequest, collect_dimension_requests
from diagram_ir.geometry import rounded_rect_path
from diagram_ir.shapes import Shape
from ir.removal_intent import Bounds2D
from layout_ast.layout import Item, LayoutAST, Sheet

FEATURE_HANDLERS: dict[str, Callable[[Item, str, Callable, float], list[Shape]]] = {}


def register_feature(feature_type: str):
    def decorator(fn: Callable[[Item, str, Callable, float], list[Shape]]):
        FEATURE_HANDLERS[feature_type] = fn
        return fn

    return decorator


def layoutast_to_diagram_ir(
    ast: LayoutAST,
    y_origin: str = "back",
    show_dimensions: bool = True,
    show_toolpaths: bool = True,
    kerf_width_mm: float = 0.0,
) -> DiagramIR:
    sheet = ast.sheet
    margin = sheet.margin_mm

    toolpath_margin = kerf_width_mm / 2.0 if show_toolpaths and kerf_width_mm > 0 else 0.0
    bounds = Bounds2D(
        x_min=-margin - toolpath_margin,
        x_max=sheet.width_mm + margin + toolpath_margin,
        y_min=-margin - toolpath_margin,
        y_max=sheet.height_mm + margin + toolpath_margin,
    )

    def flip_y(y: float) -> float:
        if y_origin == "back":
            return margin + sheet.working_height_mm - y
        return margin + y

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

        handler = FEATURE_HANDLERS.get(feature_type)
        if handler:
            style_token = _get_style_token(feature_type, bool(is_waste))
            shapes = handler(item, style_token, flip_y, margin)
            _dispatch_shapes(
                shapes,
                feature_type,
                bool(is_waste),
                profile_shapes,
                waste_shapes,
                pocket_shapes,
                hole_shapes,
                engrave_shapes,
            )

            if feature_type == "profile" and not is_waste and show_toolpaths and tool_radius > 0:
                tp_shapes = _build_toolpath_shapes(item, tool_radius, flip_y, margin)
                toolpath_shapes.extend(tp_shapes)

            if feature_type == "hole":
                hole_shapes.extend(_build_hole_crosshairs(item, flip_y, margin))

        if item.label and item.placement:
            label_shapes.extend(_build_label(item, flip_y, margin))

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
    if show_dimensions and getattr(sheet, "show_dimensions", True):
        dim_requests = collect_dimension_requests(ast, margin, 0, include_features={"profile", "pocket"}, y_flip=flip_y)
        dims = tuple(dim_requests)

    metadata = {
        "sheet_width": str(sheet.width_mm),
        "sheet_height": str(sheet.height_mm),
        "sheet_thickness": str(sheet.thickness_mm),
        "y_origin": y_origin,
        "feature_counts": _count_features(ast),
        "depth_info": _collect_depth_info(ast),
        "hole_diameters": _collect_hole_diameters(ast),
        "part_inventory": _collect_part_inventory(ast),
        "edge_profiles": _collect_edge_profiles(ast),
        "edge_allowances": _collect_edge_allowances(ast),
        "beam_structures": ast.config.get("beam_structures", []) if ast.config else [],
    }

    return DiagramIR(
        bounds=bounds,
        layers=tuple(layers),
        dims=dims,
        metadata=metadata,
    )


def _get_style_token(feature_type: str, is_waste: bool) -> str:
    if feature_type == "profile":
        return "waste" if is_waste else "profile"
    return feature_type


def _dispatch_shapes(
    shapes: list[Shape],
    feature_type: str,
    is_waste: bool,
    profile_shapes: list,
    waste_shapes: list,
    pocket_shapes: list,
    hole_shapes: list,
    engrave_shapes: list,
) -> None:
    if feature_type == "profile" or feature_type == "notch":
        if is_waste:
            waste_shapes.extend(shapes)
        else:
            profile_shapes.extend(shapes)
    elif feature_type == "pocket":
        pocket_shapes.extend(shapes)
    elif feature_type == "hole":
        hole_shapes.extend(shapes)
    elif feature_type == "engrave":
        engrave_shapes.extend(shapes)


@register_feature("profile")  # type: ignore[untyped-decorator]
def _handle_profile(item: Item, style_token: str, flip_y: Callable, margin: float) -> list[Shape]:
    return _item_to_shapes(item, style_token, flip_y, margin)


@register_feature("pocket")  # type: ignore[untyped-decorator]
def _handle_pocket(item: Item, style_token: str, flip_y: Callable, margin: float) -> list[Shape]:
    return _item_to_shapes(item, style_token, flip_y, margin)


@register_feature("hole")  # type: ignore[untyped-decorator]
def _handle_hole(item: Item, style_token: str, flip_y: Callable, margin: float) -> list[Shape]:
    return _item_to_shapes(item, style_token, flip_y, margin)


@register_feature("engrave")  # type: ignore[untyped-decorator]
def _handle_engrave(item: Item, style_token: str, flip_y: Callable, margin: float) -> list[Shape]:
    return _item_to_shapes(item, style_token, flip_y, margin)


@register_feature("surface")  # type: ignore[untyped-decorator]
def _handle_surface(item: Item, style_token: str, flip_y: Callable, margin: float) -> list[Shape]:
    return []


@register_feature("notch")  # type: ignore[untyped-decorator]
def _handle_notch(item: Item, style_token: str, flip_y: Callable, margin: float) -> list[Shape]:
    return _build_notch_shapes(item, flip_y, margin)


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
            Rect(x=0, y=0, width=sheet.width_mm, height=margin, style_token="margin-zone", id="margin_bottom")
        )
        shapes.append(
            Rect(
                x=0,
                y=sheet.height_mm - margin,
                width=sheet.width_mm,
                height=margin,
                style_token="margin-zone",
                id="margin_top",
            )
        )
        shapes.append(
            Rect(
                x=0,
                y=margin,
                width=margin,
                height=sheet.height_mm - 2 * margin,
                style_token="margin-zone",
                id="margin_left",
            )
        )
        shapes.append(
            Rect(
                x=sheet.width_mm - margin,
                y=margin,
                width=margin,
                height=sheet.height_mm - 2 * margin,
                style_token="margin-zone",
                id="margin_right",
            )
        )

    return shapes


def _item_to_shapes(item: Item, style_token: str, flip_y, margin: float) -> list:
    if item.geometry is None or item.placement is None:
        return []

    cx, cy = item.placement.center_xy_mm
    sx = margin + cx
    cy_flipped = flip_y(cy)
    shape_type = item.type
    data = item.geometry.data
    shape_id = item.shape_id or "unnamed"

    if shape_type in ("Rect", "Rectangle"):
        w = float(data.get("w_mm") or data.get("width", 0))
        h = float(data.get("h_mm") or data.get("height", 0))
        return [
            Rect(
                x=sx - w / 2,
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
                cx=sx,
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
        transformed = [Point2D(sx + p[0], flip_y(cy + p[1])) for p in points]
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

        x = sx - w / 2
        y = flip_y(cy + h / 2)
        path_d = rounded_rect_path(x, y, w, h, radius_tl, radius_tr, radius_br, radius_bl)
        return [Path(d=path_d, style_token=style_token, id=shape_id)]

    elif shape_type == "Line":
        start = data.get("start", [0, 0])
        end = data.get("end", [0, 0])
        return [
            Line(
                x1=sx + start[0],
                y1=flip_y(cy + start[1]),
                x2=sx + end[0],
                y2=flip_y(cy + end[1]),
                style_token=style_token,
                id=shape_id,
            )
        ]

    elif shape_type == "Polyline":
        points = data.get("points", [])
        if not points:
            return []
        transformed = [Point2D(sx + p[0], flip_y(cy + p[1])) for p in points]
        return [
            Polyline(
                points=tuple(transformed),
                closed=False,
                style_token=style_token,
                id=shape_id,
            )
        ]

    return []


def _build_hole_crosshairs(item: Item, flip_y, margin: float) -> list:
    if item.placement is None:
        return []
    cx, cy = item.placement.center_xy_mm
    sx = margin + cx
    cy_flipped = flip_y(cy)
    mark_size = 3
    return [
        Line(
            x1=sx - mark_size,
            y1=cy_flipped,
            x2=sx + mark_size,
            y2=cy_flipped,
            style_token="hole",
            id=f"{item.shape_id or 'hole'}_cross_h",
        ),
        Line(
            x1=sx,
            y1=cy_flipped - mark_size,
            x2=sx,
            y2=cy_flipped + mark_size,
            style_token="hole",
            id=f"{item.shape_id or 'hole'}_cross_v",
        ),
    ]


def _build_notch_shapes(item: Item, flip_y, margin: float) -> list:
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
            x=margin + x_min,
            y=y_draw,
            width=w,
            height=h_draw,
            style_token="profile",
            id=item.shape_id or "notch",
        )
    ]


def _build_toolpath_shapes(item: Item, tool_radius: float, flip_y, margin: float) -> list:
    if item.geometry is None or item.feature is None or item.placement is None:
        return []
    if tool_radius <= 0:
        return []

    offset = tool_radius

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
                x=margin + cx - new_w / 2,
                y=flip_y(cy + new_h / 2),
                width=new_w,
                height=new_h,
                style_token="toolpath",
                id=f"{item.shape_id or 'item'}_toolpath",
            )
        ]

    elif shape_type == "Circle":
        r = float(data.get("radius_mm") or data.get("diameter_mm", 0) / 2)
        if r <= 0:
            return []
        new_r = r + offset
        if new_r <= 0:
            return []
        return [
            Circle(
                cx=margin + cx,
                cy=flip_y(cy),
                radius=new_r,
                style_token="toolpath",
                id=f"{item.shape_id or 'item'}_toolpath",
            )
        ]

    elif shape_type == "Polygon":
        points = data.get("points", [])
        holes = data.get("holes", [])
        if not points:
            return []
        return _build_polygon_toolpath(
            points,
            holes,
            cx,
            cy,
            offset,
            margin,
            flip_y,
            item.shape_id or "item",
        )

    elif shape_type == "RoundedRect":
        w = float(data.get("w_mm", 0))
        h = float(data.get("h_mm", 0))
        if w <= 0 or h <= 0:
            return []
        new_w = w + 2 * offset
        new_h = h + 2 * offset
        if new_w <= 0 or new_h <= 0:
            return []
        radius = float(data.get("radius_mm", 0))
        r_tl = max(0.0, float(data.get("radius_tl_mm", radius)) + offset)
        r_tr = max(0.0, float(data.get("radius_tr_mm", radius)) + offset)
        r_br = max(0.0, float(data.get("radius_br_mm", radius)) + offset)
        r_bl = max(0.0, float(data.get("radius_bl_mm", radius)) + offset)
        sx = margin + cx
        x = sx - new_w / 2
        y = flip_y(cy + new_h / 2)
        path_d = rounded_rect_path(x, y, new_w, new_h, r_tl, r_tr, r_br, r_bl)
        return [Path(d=path_d, style_token="toolpath", id=f"{item.shape_id or 'item'}_toolpath")]

    return []


def _build_polygon_toolpath(
    points: list,
    holes: list | None,
    cx: float,
    cy: float,
    offset: float,
    margin: float,
    flip_y,
    shape_id: str,
) -> list:
    from shapely import BufferJoinStyle
    from shapely.geometry import MultiPolygon
    from shapely.geometry import Polygon as ShapelyPolygon
    from shapely.ops import orient

    abs_points = [(float(x) + cx, float(y) + cy) for x, y in points]
    abs_holes: list[list[tuple[float, float]]] = []
    for hole in holes or []:
        abs_holes.append([(float(x) + cx, float(y) + cy) for x, y in hole])

    poly = ShapelyPolygon(abs_points, abs_holes if abs_holes else None)
    if offset != 0.0:
        poly = poly.buffer(offset, join_style=BufferJoinStyle.mitre, mitre_limit=2.0)

    if poly.is_empty:
        return []

    polys = list(poly.geoms) if isinstance(poly, MultiPolygon) else [poly]
    results: list = []
    for i, p in enumerate(polys):
        p = orient(p, sign=1.0)
        if p.is_empty or not hasattr(p, "exterior"):
            continue
        coords = list(p.exterior.coords[:-1])
        transformed = [Point2D(margin + x, flip_y(y)) for x, y in coords]
        suffix = f"_toolpath_{i}" if len(polys) > 1 else "_toolpath"
        results.append(
            Polyline(
                points=tuple(transformed),
                closed=True,
                style_token="toolpath",
                id=f"{shape_id}{suffix}",
            )
        )
    return results


def _build_label(item: Item, flip_y, margin: float) -> list:
    if not item.label or item.placement is None:
        return []
    cx, cy = item.placement.center_xy_mm
    return [
        Text(
            x=margin + cx,
            y=flip_y(cy),
            content=item.label,
            style_token="label",
            anchor="middle",
            baseline="middle",
            id=f"{item.shape_id or 'item'}_label",
        )
    ]


def _count_features(ast: LayoutAST) -> str:
    counts: dict[str, int] = {}
    for item in ast.items:
        if item.feature is None:
            continue
        ftype = item.feature.type
        counts[ftype] = counts.get(ftype, 0) + 1
    if not counts:
        return ""
    return ", ".join(f"{count} {ftype}{'s' if count > 1 else ''}" for ftype, count in counts.items())


def _collect_depth_info(ast: LayoutAST) -> list[str]:
    depths_by_type: dict[str, set[str]] = {}
    for item in ast.items:
        if item.feature is None:
            continue
        ftype = item.feature.type
        if item.feature.is_through and ftype == "profile":
            continue
        depth_str = DepthMode.THROUGH if item.feature.is_through else f"{float(item.feature.depth_mm):.1f}mm"
        if ftype not in depths_by_type:
            depths_by_type[ftype] = set()
        depths_by_type[ftype].add(depth_str)

    return [
        f"{ftype}: {', '.join(sorted(depths))}"
        for ftype in sorted(depths_by_type.keys())
        for depths in [depths_by_type[ftype]]
    ]


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
    return [f"{d:.1f}" for d in sorted(diameters)]


def _collect_part_inventory(ast: LayoutAST) -> list[str]:
    parts: set[str] = set()
    for item in ast.items:
        if item.kind != "shape" or item.feature is None:
            continue
        if not item.shape_id or item.shape_id.startswith("generated_"):
            continue
        parts.add(item.shape_id)
    return sorted(parts)


def _collect_edge_profiles(ast: LayoutAST) -> list[dict]:
    profiles: dict[str, dict] = {}
    for item in ast.items:
        if item.kind != "shape" or item.feature is None or item.geometry is None:
            continue
        edge = item.geometry.data.get("edge_treatment")
        if not edge:
            continue
        treatment_type = edge.get("type")
        if treatment_type == "allowance":
            continue
        if treatment_type == "fillet":
            radius = edge.get("radius_mm")
            if radius is None or radius <= 0:
                continue
            key = f"fillet_r{radius:.1f}"
            if key not in profiles:
                profiles[key] = {"type": "fillet", "radius_mm": radius, "items": []}
        elif treatment_type == "chamfer":
            distance = edge.get("distance_mm")
            if distance is None or distance <= 0:
                continue
            key = f"chamfer_d{distance:.1f}"
            if key not in profiles:
                profiles[key] = {"type": "chamfer", "distance_mm": distance, "items": []}
        else:
            continue
        if item.shape_id:
            profiles[key]["items"].append(item.shape_id)
    return [profiles[k] for k in sorted(profiles)]


def _collect_edge_allowances(ast: LayoutAST) -> list[dict]:
    seen: set[tuple[float, float]] = set()
    result: list[dict] = []
    for item in ast.items:
        if item.kind != "shape" or item.feature is None or item.geometry is None:
            continue
        edge = item.geometry.data.get("edge_treatment")
        if not edge or edge.get("type") != "allowance":
            continue
        rough = edge.get("rough_allowance_mm")
        finish = edge.get("finish_allowance_mm")
        if rough is None or finish is None:
            continue
        pair = (rough, finish)
        if pair not in seen:
            seen.add(pair)
            result.append({"rough_allowance_mm": rough, "finish_allowance_mm": finish})
    return sorted(result, key=lambda a: (-a["rough_allowance_mm"], -a["finish_allowance_mm"]))


__all__ = ["FEATURE_HANDLERS", "layoutast_to_diagram_ir", "register_feature"]
