from __future__ import annotations

import logging
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

from shapely.geometry import Point
from shapely.geometry.base import BaseGeometry

from adapters.hints_to_removal import _geometry_dict_to_shape_geometry
from core.constants import DepthMode, ShapeType
from core.geometry import compute_shape_bounds, pocket_region
from diagram_ir import Circle, DiagramIR, Image, LayerIR, Line, Path, Point2D, Polyline, Rect, Text
from diagram_ir.dimensions import DimensionRequest, collect_dimension_requests
from diagram_ir.geometry import rounded_rect_path
from diagram_ir.shapes import Shape
from ir.removal_intent import Bounds2D, RemovalIntent
from layout_ast.layout import Item, LayoutAST, Sheet

_logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from cam.planner.passes.edge import EdgeCutPlan
    from cam.planner.passes.tools import ToolSelection


_EDGE_TYPES = frozenset({"bevel", "chamfer", "roundover", "raised_panel"})


@dataclass(frozen=True)
class _DrawingContext:
    flip_y: Callable[[float], float]
    margin_mm: float
    shape_id: str
    edge_plan: EdgeCutPlan | None = None
    edge_error: str | None = None
    requested_depth_mm: float = 0.0


FeatureHandler = Callable[[Item, str, _DrawingContext], list[Shape]]
FEATURE_HANDLERS: dict[str, FeatureHandler] = {}

FEATURE_LAYER: dict[str, str] = {
    "profile": "PROFILE_CUTS",
    "notch": "PROFILE_CUTS",
    "pocket": "POCKET_REGIONS",
    "hole": "HOLES",
    "engrave": "ENGRAVE_PATHS",
    "heightfield": "HEIGHTFIELD_OVERLAYS",
    "bevel": "BEVEL_CUTS",
    "raised_panel": "BEVEL_CUTS",
    "chamfer": "CHAMFER_CUTS",
    "roundover": "ROUNDOVER_CUTS",
}

WASTE_LAYER = "WASTE_CUTS"

_LAYER_ORDER = (
    "PROFILE_CUTS",
    "PROFILE_TOOLPATHS",
    "WASTE_CUTS",
    "POCKET_REGIONS",
    "HOLES",
    "ENGRAVE_PATHS",
    "KEEPOUT_ZONES",
    "BEVEL_CUTS",
    "CHAMFER_CUTS",
    "ROUNDOVER_CUTS",
    "UNPLANNED_EDGES",
    "HEIGHTFIELD_OVERLAYS",
    "LABELS",
)


def register_feature(*feature_types: str, layer: str | None = None) -> Callable[[FeatureHandler], FeatureHandler]:
    def decorator(fn: FeatureHandler) -> FeatureHandler:
        for feature_type in feature_types:
            FEATURE_HANDLERS[feature_type] = fn
            if layer is not None:
                FEATURE_LAYER[feature_type] = layer
        return fn

    return decorator


def _include_keepout_bounds(bounds: Bounds2D, item: Item, flip_y: Callable, margin: float) -> Bounds2D:
    if item.geometry is None or item.placement is None:
        return bounds
    zone = compute_shape_bounds(item.type, item.geometry.data, item.placement.center_xy_mm)
    ys = (flip_y(zone.y_min), flip_y(zone.y_max))
    return Bounds2D(
        min(bounds.x_min, margin + zone.x_min),
        max(bounds.x_max, margin + zone.x_max),
        min(bounds.y_min, *ys),
        max(bounds.y_max, *ys),
    )


def layoutast_to_diagram_ir(
    ast: LayoutAST,
    y_origin: str = "back",
    show_dimensions: bool = True,
    show_toolpaths: bool = True,
    kerf_width_mm: float = 0.0,
    view_face: str = "front",
    edge_tools: Sequence[ToolSelection] | None = None,
    removal_intents: Sequence[RemovalIntent] | None = None,
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

    layer_shapes: dict[str, list[Shape]] = {}

    tool_radius = kerf_width_mm / 2.0

    edge_tools = _edge_tools_for_layout(ast, edge_tools)
    edge_depths: dict[str, set[str]] = {}
    edge_intents = _edge_intent_map(removal_intents)

    for index, item in enumerate(ast.items):
        if item.kind == "keepout":
            bounds = _include_keepout_bounds(bounds, item, flip_y, margin)
            layer_shapes.setdefault("KEEPOUT_ZONES", []).extend(_item_to_shapes(item, "keepout", flip_y, margin))
            layer_shapes.setdefault("LABELS", []).extend(_build_label(item, flip_y, margin))
            continue
        if item.kind != "shape" or item.feature is None:
            continue

        is_waste = item.shape_id and "waste" in item.shape_id
        feature_type = item.feature.type

        handler = FEATURE_HANDLERS.get(feature_type)
        if handler:
            style_token = _get_style_token(feature_type, bool(is_waste))
            context = _drawing_context(item, index, sheet, flip_y, margin, edge_tools, edge_intents)
            shapes = handler(item, style_token, context)
            _record_edge_depth(edge_depths, feature_type, context)
            bounds = _include_edge_plan_bounds(bounds, context)

            target_layer = "UNPLANNED_EDGES" if context.edge_error else FEATURE_LAYER.get(feature_type)
            if target_layer:
                if is_waste and target_layer == "PROFILE_CUTS":
                    target_layer = WASTE_LAYER
                _route_feature_shapes(layer_shapes, shapes, target_layer)

            if feature_type == "profile" and not is_waste and show_toolpaths and tool_radius > 0:
                tp_shapes = _build_toolpath_shapes(item, tool_radius, flip_y, margin)
                layer_shapes.setdefault("PROFILE_TOOLPATHS", []).extend(tp_shapes)

            if feature_type == "hole":
                layer_shapes.setdefault("HOLES", []).extend(_build_hole_crosshairs(item, flip_y, margin))

        if item.label and item.placement:
            layer_shapes.setdefault("LABELS", []).extend(_build_label(item, flip_y, margin))

    for layer_name in _LAYER_ORDER:
        if layer_shapes.get(layer_name):
            layers.append(LayerIR(name=layer_name, items=tuple(layer_shapes[layer_name])))

    dims: tuple[DimensionRequest, ...] = ()
    if show_dimensions and getattr(sheet, "show_dimensions", True):
        dim_requests = collect_dimension_requests(ast, margin, 0, include_features={"profile", "pocket"}, y_flip=flip_y)
        dims = tuple(dim_requests)

    metadata = {
        "sheet_width": str(sheet.width_mm),
        "sheet_height": str(sheet.height_mm),
        "sheet_thickness": str(sheet.thickness_mm),
        "sheet_margin": sheet.margin_mm,
        "y_origin": y_origin,
        "view_face": view_face,
        "feature_counts": _count_features(ast),
        "depth_info": _collect_depth_info(ast, edge_depths),
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


def _route_feature_shapes(layer_shapes: dict[str, list[Shape]], shapes: Sequence[Shape], target_layer: str) -> None:
    for shape in shapes:
        shape_layer = FEATURE_LAYER.get(shape.style_token, target_layer)
        layer_shapes.setdefault(shape_layer, []).append(shape)


def _edge_intent_map(intents: Sequence[RemovalIntent] | None) -> Mapping[tuple[str, str], RemovalIntent] | None:
    if intents is None:
        return None
    result: dict[tuple[str, str], RemovalIntent] = {}
    for intent in intents:
        if intent.hint_type not in _EDGE_TYPES:
            continue
        key = intent.face, intent.region_id
        if key in result:
            raise ValueError(
                f"Edge drawing: removal intent IDs must be unique within a face, got '{intent.region_id}' twice on '{intent.face}'"
            )
        result[key] = intent
    return result


def _edge_tools_for_layout(ast: LayoutAST, tools: Sequence[ToolSelection] | None) -> Sequence[ToolSelection]:
    if tools is not None:
        return tools
    if not any(item.feature and item.feature.type in _EDGE_TYPES for item in ast.items):
        return ()
    from cam.planner.passes.tools import normalize_tool_entries
    from config.machine_loader import load_machine_tool_db

    return normalize_tool_entries(load_machine_tool_db(ast.sheet.material))


def _record_edge_depth(depths: dict[str, set[str]], feature_type: str, context: _DrawingContext) -> None:
    if feature_type not in _EDGE_TYPES:
        return
    depth = context.edge_plan.depth_mm if context.edge_plan else context.requested_depth_mm
    suffix = " (unplanned)" if context.edge_error else ""
    depths.setdefault(feature_type, set()).add(f"{depth:.3f}mm{suffix}")


def _include_edge_plan_bounds(bounds: Bounds2D, context: _DrawingContext) -> Bounds2D:
    if context.edge_plan is None:
        return bounds
    xs = [context.margin_mm + point.x for point in context.edge_plan.shape.points]
    ys = [context.flip_y(point.y) for point in context.edge_plan.shape.points]
    return Bounds2D(min(bounds.x_min, *xs), max(bounds.x_max, *xs), min(bounds.y_min, *ys), max(bounds.y_max, *ys))


def _drawing_context(
    item: Item,
    index: int,
    sheet: Sheet,
    flip_y: Callable[[float], float],
    margin: float,
    tools: Sequence[ToolSelection],
    edge_intents: Mapping[tuple[str, str], RemovalIntent] | None,
) -> _DrawingContext:
    shape_id = item.shape_id or item.id or f"edge_{index}"
    if item.feature is None or item.feature.type not in _EDGE_TYPES:
        return _DrawingContext(flip_y, margin, shape_id)
    from adapters.ast_to_removal import item_to_removal_intent
    from adapters.removal_to_planner import removal_intents_to_planner_input
    from cam.planner.passes.edge import build_edge_cut_plan

    depth = item.feature.depth_mm
    try:
        intent = item_to_removal_intent(item, sheet.thickness_mm)
        if edge_intents is not None:
            key = intent.face, intent.region_id
            if key not in edge_intents:
                raise ValueError(f"Edge feature '{shape_id}': no corresponding removal intent available")
            intent = edge_intents[key]
        depth = intent.depth_mm()
        entry = removal_intents_to_planner_input([intent]).edge_features[0]
        plan = build_edge_cut_plan(entry, tools)
    except ValueError as exc:
        return _DrawingContext(flip_y, margin, shape_id, edge_error=str(exc), requested_depth_mm=depth)
    return _DrawingContext(flip_y, margin, shape_id, edge_plan=plan, requested_depth_mm=depth)


@register_feature("bevel", "chamfer", "roundover", "raised_panel")
def _handle_edge(item: Item, style_token: str, context: _DrawingContext) -> list[Shape]:
    if item.placement is None or item.geometry is None or item.feature is None:
        return []
    plan = context.edge_plan
    if plan is None:
        shapes = _item_to_shapes(item, "edge-unplanned", context.flip_y, context.margin_mm)
        x, y = item.placement.center_xy_mm
        label = f"{item.feature.type.replace('_', ' ').capitalize()} unplanned"
    else:
        points = tuple(Point2D(context.margin_mm + p.x, context.flip_y(p.y)) for p in plan.shape.points)
        shapes = [Polyline(points=points, closed=True, style_token=style_token, id=f"{context.shape_id}_edge_cut")]
        for index, pocket in enumerate(plan.pockets):
            shapes.extend(
                _region_path(
                    pocket.region, "pocket", f"{context.shape_id}_pocket_{index}", context.flip_y, context.margin_mm
                )
            )
        xs, ys = [p.x for p in plan.shape.points], [p.y for p in plan.shape.points]
        x, y = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
        label = f"{item.feature.type.replace('_', ' ').capitalize()} {plan.depth_mm:.3f}mm"
        spec = item.feature.raised_panel
        if spec is not None:
            label = f"V {spec.v_angle_deg:g}° / {plan.depth_mm:g}mm"
            field_label = f"Field {spec.field_depth_mm:g}mm" if spec.field_depth_mm > 0 else "Field unchanged"
            y += 8
            shapes.append(
                Text(x=context.margin_mm + x, y=context.flip_y(y - 16), content=field_label, style_token="edge-label")
            )
    shapes.append(
        Text(
            x=context.margin_mm + x,
            y=context.flip_y(y),
            content=label,
            style_token="edge-label",
            id=f"{context.shape_id}_edge_depth",
        )
    )
    return shapes


def _get_style_token(feature_type: str, is_waste: bool) -> str:
    if feature_type == "raised_panel":
        return "bevel"
    if feature_type == "profile":
        return "waste" if is_waste else "profile"
    return feature_type


@register_feature("profile")
def _handle_profile(item: Item, style_token: str, context: _DrawingContext) -> list[Shape]:
    return _item_to_shapes(item, style_token, context.flip_y, context.margin_mm)


@register_feature("pocket")
def _handle_pocket(item: Item, style_token: str, context: _DrawingContext) -> list[Shape]:
    flip_y, margin = context.flip_y, context.margin_mm
    if item.geometry is None or item.placement is None:
        return []
    data = item.geometry.data
    if not data.get("holes") and not data.get("islands"):
        return _item_to_shapes(item, style_token, context.flip_y, context.margin_mm)
    region = _pocket_region_with_exclusions(item)
    return _region_path(region, style_token, item.shape_id or "unnamed", flip_y, margin)


def _pocket_region_with_exclusions(item: Item) -> BaseGeometry:
    if item.geometry is None or item.placement is None:
        raise ValueError(f"Pocket '{item.shape_id}': geometry and placement are required")
    data = item.geometry.data
    bounds = compute_shape_bounds(item.type, data, item.placement.center_xy_mm)
    geometry = _geometry_dict_to_shape_geometry(data, item.placement.center_xy_mm, bounds)
    islands = tuple(
        Bounds2D(float(i["x_min"]), float(i["x_max"]), float(i["y_min"]), float(i["y_max"]))
        for i in data.get("islands", [])
    )
    region = pocket_region(item.type, geometry, bounds.center, islands)
    if region is None:
        raise ValueError(f"Pocket '{item.shape_id}': cannot draw holes/islands for shape '{item.type}'")
    return region


def _region_path(region, style_token: str, shape_id: str, flip_y: Callable, margin: float) -> list[Shape]:
    from shapely import get_parts
    from shapely.geometry import Polygon

    commands: list[str] = []
    for polygon in get_parts(region):
        if not isinstance(polygon, Polygon) or polygon.is_empty:
            continue
        for ring in (polygon.exterior, *polygon.interiors):
            points = [(margin + x, flip_y(y)) for x, y in ring.coords[:-1]]
            commands.append("M " + " L ".join(f"{x:.3f} {y:.3f}" for x, y in points) + " Z")
    return [Path(d=" ".join(commands), fill_rule="evenodd", style_token=style_token, id=shape_id)] if commands else []


@register_feature("hole")
def _handle_hole(item: Item, style_token: str, context: _DrawingContext) -> list[Shape]:
    return _item_to_shapes(item, style_token, context.flip_y, context.margin_mm)


@register_feature("engrave")
def _handle_engrave(item: Item, style_token: str, context: _DrawingContext) -> list[Shape]:
    return _item_to_shapes(item, style_token, context.flip_y, context.margin_mm)


@register_feature("surface")
def _handle_surface(item: Item, style_token: str, context: _DrawingContext) -> list[Shape]:
    return []


@register_feature("notch")
def _handle_notch(item: Item, style_token: str, context: _DrawingContext) -> list[Shape]:
    return _build_notch_shapes(item, context.flip_y, context.margin_mm)


@register_feature("heightfield", layer="HEIGHTFIELD_OVERLAYS")
def _handle_heightfield(item: Item, style_token: str, context: _DrawingContext) -> list[Shape]:
    return _build_heightfield_shapes(item, context.flip_y, context.margin_mm)


def _build_heightfield_shapes(item: Item, flip_y: Callable, margin: float) -> list[Shape]:
    if item.geometry is None or item.placement is None:
        return []

    data = item.geometry.data
    image_path = data.get("image_path")
    if not image_path:
        _logger.warning(
            "Heightfield '%s': missing image_path in geometry.data — skipped in diagram",
            item.shape_id or "unknown",
        )
        return []

    try:
        w = float(data["w_mm"])
        h = float(data["h_mm"])
    except (KeyError, TypeError, ValueError) as exc:
        _logger.warning(
            "Heightfield '%s': invalid geometry dimensions (%s) — skipped in diagram",
            item.shape_id or "unknown",
            exc,
        )
        return []

    href = _heightfield_image_href(image_path)

    cx, cy = item.placement.center_xy_mm
    sx = margin + cx
    x = sx - w / 2
    y_top_source = cy + h / 2
    y = flip_y(y_top_source)
    shape_id = item.shape_id or "heightfield"

    return [
        Image(
            x=x,
            y=y,
            width=w,
            height=h,
            href=href,
            id=shape_id,
        ),
        Rect(
            x=x,
            y=y,
            width=w,
            height=h,
            style_token="heightfield-border",
            id=f"{shape_id}_border",
        ),
    ]


def _heightfield_image_href(image_path: str) -> str:
    import os

    from generators.area.heightfield_loader import load_heightfield_data_url

    if not os.path.isabs(image_path):
        raise ValueError(
            f"Heightfield image_path must be absolute for blueprint rendering, got {image_path!r}. "
            "Resolver should have joined it against source_dir."
        )
    return load_heightfield_data_url(image_path)


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

    if ShapeType.is_rect(shape_type):
        w = float(data.get("w_mm") or data.get("width", 0))
        h = float(data.get("h_mm") or data.get("height", 0))
        return [
            Rect(
                x=sx - w / 2,
                y=min(flip_y(cy + h / 2), flip_y(cy - h / 2)),
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
        y = min(flip_y(cy + h / 2), flip_y(cy - h / 2))
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
    except (TypeError, ValueError) as exc:
        _logger.warning("Notch '%s': invalid geometry data (%s) — skipped in diagram", item.shape_id or "unknown", exc)
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

    if ShapeType.is_rect(shape_type):
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
                y=min(flip_y(cy + new_h / 2), flip_y(cy - new_h / 2)),
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
        y = min(flip_y(cy + new_h / 2), flip_y(cy - new_h / 2))
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
    if item.feature is not None and item.feature.type == "pocket" and item.geometry is not None:
        data = item.geometry.data
        if item.type == "Polygon" or data.get("holes") or data.get("islands"):
            region = _pocket_region_with_exclusions(item)
            if region.is_empty:
                return []
            if not region.contains(Point(cx, cy)):
                point = region.representative_point()
                cx, cy = point.x, point.y
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
    return ", ".join(f"{count} {ftype}{'s' if count > 1 else ''}" for ftype, count in sorted(counts.items()))


def _collect_depth_info(ast: LayoutAST, edge_depths: dict[str, set[str]] | None = None) -> list[str]:
    depths_by_type: dict[str, set[str]] = {}
    for item in ast.items:
        if item.feature is None:
            continue
        ftype = item.feature.type
        if item.feature.is_through and ftype == "profile":
            continue
        if edge_depths and ftype in edge_depths:
            depths_by_type.setdefault(ftype, set()).update(edge_depths[ftype])
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


__all__ = ["FEATURE_HANDLERS", "FEATURE_LAYER", "WASTE_LAYER", "layoutast_to_diagram_ir", "register_feature"]
