
from __future__ import annotations

from typing import Any, Callable

from ir.removal_intent import (
    RemovalIntent,
    Bounds2D,
    Allowance,
    Constraints,
    TabConstraint,
    Island,
    EdgeTreatment,
    DepthProfile,
    ShapeGeometry,
)
from layout_ast.layout import Item
from core.constants import (
    HintKeys,
    GeometryKeys,
    TabKeys,
    FeatureType,
    ShapeType,
    Side,
)
from core.geometry import compute_shape_bounds


def _make_region_id(prefix: str, hint_id: str | None) -> str:
    return f"{prefix}_{hint_id}" if hint_id else prefix


def profile_hint_to_removal_intent(
    hint: dict[str, Any],
    sheet_thickness_mm: float,
    region_id_prefix: str = "profile",
) -> RemovalIntent:

    hint_id = hint.get(HintKeys.ID, "")
    region_id = _make_region_id(region_id_prefix, hint_id)


    depth_mm = float(hint.get(HintKeys.DEPTH_MM, sheet_thickness_mm))


    bounds = _geometry_to_bounds(
        hint.get(HintKeys.SHAPE, ""),
        hint.get(HintKeys.GEOMETRY, {}),
        hint.get(HintKeys.CENTER_XY_MM),
    )


    side = hint.get(HintKeys.SIDE, Side.OUTSIDE).lower()
    allowance = _side_to_allowance(side)


    tabs_data = hint.get(HintKeys.TABS)
    constraints = _tabs_to_constraints(tabs_data) if tabs_data else Constraints()

    geometry = hint.get(HintKeys.GEOMETRY, {})
    shape = hint.get(HintKeys.SHAPE, "")
    shape_geometry = _geometry_dict_to_shape_geometry(shape, geometry)

    return RemovalIntent(
        region_id=region_id,
        bounds=bounds,
        depth_profile=DepthProfile.constant(z_top=0.0, z_bottom=-depth_mm),
        hint_type=FeatureType.PROFILE,
        shape=shape,
        side=side,
        original_id=hint_id,
        shape_geometry=shape_geometry,
        allowance=allowance,
        constraints=constraints,
    )


def _simple_hint_to_removal_intent(
    hint: dict[str, Any],
    feature_type: str,
    region_id_prefix: str,
    extra_fn: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
) -> RemovalIntent:
    hint_id = hint.get(HintKeys.ID, "")
    region_id = _make_region_id(region_id_prefix, hint_id)
    depth_mm = float(hint.get(HintKeys.DEPTH_MM, 0.0))
    start_depth_mm = float(hint.get(HintKeys.START_DEPTH_MM, 0.0))
    shape = hint.get(HintKeys.SHAPE, "")
    geometry = hint.get(HintKeys.GEOMETRY, {})

    bounds = _geometry_to_bounds(shape, geometry, hint.get(HintKeys.CENTER_XY_MM))

    shape_geometry = _geometry_dict_to_shape_geometry(shape, geometry)

    extra_kwargs: dict[str, Any] = {}
    if extra_fn:
        extra_kwargs = extra_fn(hint)

    return RemovalIntent(
        region_id=region_id,
        bounds=bounds,
        depth_profile=DepthProfile.constant(
            z_top=-start_depth_mm,
            z_bottom=-(start_depth_mm + depth_mm),
        ),
        hint_type=feature_type,
        shape=shape,
        original_id=hint_id,
        shape_geometry=shape_geometry,
        allowance=Allowance(),
        constraints=Constraints(),
        **extra_kwargs,
    )


def _pocket_extra_kwargs(hint: dict[str, Any]) -> dict[str, Any]:
    kwargs: dict[str, Any] = {}
    if HintKeys.CORNER_CLEANUP_TOOL_DIAMETER_MM in hint:
        kwargs["corner_cleanup_tool_diameter_mm"] = float(hint[HintKeys.CORNER_CLEANUP_TOOL_DIAMETER_MM])
    return kwargs


def _hole_extra_kwargs(hint: dict[str, Any]) -> dict[str, Any]:
    return {}


def _engrave_extra_kwargs(hint: dict[str, Any]) -> dict[str, Any]:
    return {}


def pocket_hint_to_removal_intent(
    hint: dict[str, Any],
    region_id_prefix: str = "pocket",
) -> RemovalIntent:
    return _simple_hint_to_removal_intent(
        hint, FeatureType.POCKET, region_id_prefix, _pocket_extra_kwargs
    )


def hole_hint_to_removal_intent(
    hint: dict[str, Any],
    region_id_prefix: str = "hole",
) -> RemovalIntent:
    return _simple_hint_to_removal_intent(
        hint, FeatureType.HOLE, region_id_prefix, _hole_extra_kwargs
    )


def engrave_hint_to_removal_intent(
    hint: dict[str, Any],
    region_id_prefix: str = "engrave",
) -> RemovalIntent:
    return _simple_hint_to_removal_intent(
        hint, FeatureType.ENGRAVE, region_id_prefix, _engrave_extra_kwargs
    )


def _geometry_to_bounds(shape: str, geometry: dict[str, Any], center_xy: tuple[float, float] | list[float] | None) -> Bounds2D:
    return compute_shape_bounds(shape, geometry, center_xy)


def _geometry_dict_to_shape_geometry(shape: str, geometry: dict[str, Any]) -> ShapeGeometry:
    points_raw = geometry.get(GeometryKeys.POINTS)
    points: tuple[tuple[float, float], ...] | None = None
    if points_raw is not None:
        points = tuple((float(p[0]), float(p[1])) for p in points_raw)
    start_raw = geometry.get("start")
    start: tuple[float, float] | None = (float(start_raw[0]), float(start_raw[1])) if start_raw is not None else None
    end_raw = geometry.get("end")
    end: tuple[float, float] | None = (float(end_raw[0]), float(end_raw[1])) if end_raw is not None else None
    return ShapeGeometry(
        w_mm=float(geometry[GeometryKeys.W_MM]) if GeometryKeys.W_MM in geometry else None,
        h_mm=float(geometry[GeometryKeys.H_MM]) if GeometryKeys.H_MM in geometry else None,
        diameter_mm=float(geometry[GeometryKeys.DIAMETER_MM]) if GeometryKeys.DIAMETER_MM in geometry else None,
        points=points,
        radius_mm=float(geometry[GeometryKeys.RADIUS_MM]) if GeometryKeys.RADIUS_MM in geometry else None,
        radius_tl_mm=float(geometry[GeometryKeys.RADIUS_TL_MM]) if GeometryKeys.RADIUS_TL_MM in geometry else None,
        radius_tr_mm=float(geometry[GeometryKeys.RADIUS_TR_MM]) if GeometryKeys.RADIUS_TR_MM in geometry else None,
        radius_br_mm=float(geometry[GeometryKeys.RADIUS_BR_MM]) if GeometryKeys.RADIUS_BR_MM in geometry else None,
        radius_bl_mm=float(geometry[GeometryKeys.RADIUS_BL_MM]) if GeometryKeys.RADIUS_BL_MM in geometry else None,
        start=start,
        end=end,
    )


def _side_to_allowance(side: str) -> Allowance:
    side_lower = side.lower()

    if side_lower == Side.OUTSIDE:

        return Allowance(outside=0.0)
    elif side_lower == Side.INSIDE:

        return Allowance(inside=0.0)
    elif side_lower == Side.ON:

        return Allowance(on=0.0)
    else:

        return Allowance(outside=0.0)


def _tabs_to_constraints(tabs_data: dict[str, Any] | None) -> Constraints:
    if not tabs_data:
        return Constraints()

    count = int(tabs_data.get(TabKeys.COUNT, 0))
    height_mm = float(tabs_data.get(TabKeys.HEIGHT_MM, 3.0))
    width_value = tabs_data.get(TabKeys.WIDTH_MM)
    width_mm = float(width_value) if width_value is not None else None

    tab = TabConstraint(count=count, height_mm=height_mm, width_mm=width_mm)
    return Constraints(tabs=tab)


def simple_item_to_removal_intent(
    item: Item,
    region_id_prefix: str = "item",
) -> RemovalIntent:
    if not item.geometry:
        raise ValueError(f"Item {item.shape_id} has no geometry")
    if not item.placement:
        raise ValueError(f"Item {item.shape_id} has no placement")
    if not item.feature:
        raise ValueError(f"Item {item.shape_id} has no feature")


    region_id = _make_region_id(region_id_prefix, item.shape_id)


    depth_mm = float(item.feature.depth_mm) if item.feature.depth_mm is not None else 0.0


    cx, cy = item.placement.center_xy_mm
    bounds = _item_geometry_to_bounds(item.type, item.geometry.data, cx, cy)


    allowance = Allowance()
    if item.feature.type == FeatureType.PROFILE and item.feature.side:
        allowance = _side_to_allowance(item.feature.side)


    islands = _extract_islands_from_geometry(item.geometry.data)
    edge_treatment = _extract_edge_treatment_from_geometry(item.geometry.data)

    constraints = Constraints(
        islands=tuple(islands) if islands else (),
        edge_treatment=edge_treatment
    )


    shape_geometry = _geometry_dict_to_shape_geometry(item.type, item.geometry.data)

    return RemovalIntent(
        region_id=region_id,
        bounds=bounds,
        depth_profile=DepthProfile.constant(z_top=0.0, z_bottom=-depth_mm),
        allowance=allowance,
        constraints=constraints,
        item_type=item.type,
        feature_type=item.feature.type,
        shape_id=item.shape_id,
        shape_geometry=shape_geometry,
    )


def _item_geometry_to_bounds(item_type: str, geometry_data: dict[str, Any], cx: float, cy: float) -> Bounds2D:
    return compute_shape_bounds(item_type, geometry_data, (cx, cy))


def _extract_islands_from_geometry(geometry_data: dict[str, Any]) -> list[Island]:
    islands = []
    island_data = geometry_data.get(GeometryKeys.ISLANDS, [])

    for island_dict in island_data:
        bounds = Bounds2D(
            x_min=float(island_dict[GeometryKeys.X_MIN]),
            x_max=float(island_dict[GeometryKeys.X_MAX]),
            y_min=float(island_dict[GeometryKeys.Y_MIN]),
            y_max=float(island_dict[GeometryKeys.Y_MAX]),
        )
        islands.append(Island(bounds=bounds))

    return islands


def _extract_edge_treatment_from_geometry(geometry_data: dict[str, Any]) -> EdgeTreatment | None:
    edge_data = geometry_data.get(GeometryKeys.EDGE_TREATMENT)
    if not edge_data:
        return None

    return EdgeTreatment(
        type=edge_data[GeometryKeys.TYPE],
        radius_mm=edge_data.get(GeometryKeys.RADIUS_MM),
        distance_mm=edge_data.get(GeometryKeys.DISTANCE_MM),
        rough_allowance_mm=edge_data.get(GeometryKeys.ROUGH_ALLOWANCE_MM),
        finish_allowance_mm=edge_data.get(GeometryKeys.FINISH_ALLOWANCE_MM),
    )
