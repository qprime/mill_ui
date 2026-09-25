from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from typing import Any

from core.constants import (
    FeatureType,
    GeometryKeys,
    HintKeys,
    Side,
    TabKeys,
)
from core.geometry import compute_shape_bounds
from ir.removal_intent import (
    Allowance,
    Bounds2D,
    Constraints,
    DepthProfile,
    EdgeTreatment,
    HeightfieldToolAssignment,
    Island,
    RemovalIntent,
    ShapeGeometry,
    TabConstraint,
)


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

    geometry = hint.get(HintKeys.GEOMETRY, {})
    shape = hint.get(HintKeys.SHAPE, "")
    shape_geometry = _geometry_dict_to_shape_geometry(geometry, hint.get(HintKeys.CENTER_XY_MM), bounds)

    tabs_data = hint.get(HintKeys.TABS)
    onion_skin_mm = hint.get(HintKeys.ONION_SKIN_MM)
    edge_treatment = _extract_edge_treatment_from_geometry(geometry)
    constraints = _tabs_to_constraints(tabs_data) if tabs_data else Constraints()
    if onion_skin_mm is not None:
        constraints = replace(constraints, onion_skin_mm=float(onion_skin_mm))
    if edge_treatment is not None:
        constraints = replace(constraints, edge_treatment=edge_treatment)

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

    shape_geometry = _geometry_dict_to_shape_geometry(geometry, hint.get(HintKeys.CENTER_XY_MM), bounds)

    extra_kwargs: dict[str, Any] = {}
    if extra_fn:
        extra_kwargs = extra_fn(hint)

    edge_treatment = _extract_edge_treatment_from_geometry(geometry)

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
        constraints=Constraints(edge_treatment=edge_treatment),
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
    intent = _simple_hint_to_removal_intent(hint, FeatureType.POCKET, region_id_prefix, _pocket_extra_kwargs)
    islands = _extract_islands_from_geometry(hint.get(HintKeys.GEOMETRY, {}))
    if not islands:
        return intent
    return replace(intent, constraints=replace(intent.constraints, islands=tuple(islands)))


def hole_hint_to_removal_intent(
    hint: dict[str, Any],
    region_id_prefix: str = "hole",
) -> RemovalIntent:
    return _simple_hint_to_removal_intent(hint, FeatureType.HOLE, region_id_prefix, _hole_extra_kwargs)


def engrave_hint_to_removal_intent(
    hint: dict[str, Any],
    region_id_prefix: str = "engrave",
) -> RemovalIntent:
    return _simple_hint_to_removal_intent(hint, FeatureType.ENGRAVE, region_id_prefix, _engrave_extra_kwargs)


def heightfield_hint_to_removal_intent(
    hint: dict[str, Any],
    region_id_prefix: str = "heightfield",
) -> RemovalIntent:
    hint_id = hint.get(HintKeys.ID, "")
    region_id = _make_region_id(region_id_prefix, hint_id)
    shape = hint.get(HintKeys.SHAPE, "")
    geometry = hint.get(HintKeys.GEOMETRY, {})

    if "image_path" not in geometry:
        raise ValueError(f"Heightfield hint {hint_id!r}: geometry.data missing required 'image_path'")
    if "white_is_high" not in geometry:
        raise ValueError(f"Heightfield hint {hint_id!r}: geometry.data missing required 'white_is_high'")

    image_path = str(geometry["image_path"])
    white_is_high = bool(geometry["white_is_high"])
    depth_mm = float(hint.get(HintKeys.DEPTH_MM, 0.0))

    tools_raw = geometry.get("tools") or ()
    if not tools_raw:
        raise ValueError(f"Heightfield hint {hint_id!r}: requires at least one tool entry")
    heightfield_tools = tuple(
        HeightfieldToolAssignment(
            tool_name=str(t["tool"]),
            role=str(t["role"]),
            stepover_frac=float(t["stepover_frac"]),
            stepdown_mm=float(t["stepdown_mm"]) if t.get("stepdown_mm") is not None else None,
            angle_deg=float(t["angle_deg"]) if t.get("angle_deg") is not None else None,
        )
        for t in tools_raw
    )

    bounds = _geometry_to_bounds(shape, geometry, hint.get(HintKeys.CENTER_XY_MM))

    return RemovalIntent(
        region_id=region_id,
        bounds=bounds,
        depth_profile=DepthProfile.heightfield(
            z_top=0.0,
            z_bottom=-depth_mm,
            image_path=image_path,
            white_is_high=white_is_high,
        ),
        hint_type=FeatureType.HEIGHTFIELD,
        shape=shape,
        original_id=hint_id,
        allowance=Allowance(),
        constraints=Constraints(),
        heightfield_tools=heightfield_tools,
    )


def _geometry_to_bounds(
    shape: str, geometry: dict[str, Any], center_xy: tuple[float, float] | list[float] | None
) -> Bounds2D:
    return compute_shape_bounds(shape, geometry, center_xy)


_CENTER_TOLERANCE_MM = 1e-9


def _center_offset(center: float, bounds_center: float) -> float:
    offset = center - bounds_center
    return offset if abs(offset) > _CENTER_TOLERANCE_MM else 0.0


def _rebased_point(point: Any, dx: float, dy: float) -> tuple[float, float]:
    return (float(point[0]) + dx, float(point[1]) + dy)


def _geometry_dict_to_shape_geometry(
    geometry: dict[str, Any],
    center_xy: tuple[float, float] | list[float] | None,
    bounds: Bounds2D,
) -> ShapeGeometry:
    cx, cy = (0.0, 0.0) if center_xy is None else (float(center_xy[0]), float(center_xy[1]))
    bounds_cx, bounds_cy = bounds.center
    dx, dy = _center_offset(cx, bounds_cx), _center_offset(cy, bounds_cy)
    points_raw = geometry.get(GeometryKeys.POINTS)
    points: tuple[tuple[float, float], ...] | None = None
    if points_raw is not None:
        points = tuple(_rebased_point(p, dx, dy) for p in points_raw)
    holes_raw = geometry.get(GeometryKeys.HOLES)
    holes: tuple[tuple[tuple[float, float], ...], ...] | None = None
    if holes_raw:
        holes = tuple(tuple(_rebased_point(p, dx, dy) for p in hole) for hole in holes_raw)
    start_raw = geometry.get("start")
    start = _rebased_point(start_raw, dx, dy) if start_raw is not None else None
    end_raw = geometry.get("end")
    end = _rebased_point(end_raw, dx, dy) if end_raw is not None else None
    return ShapeGeometry(
        w_mm=float(geometry[GeometryKeys.W_MM]) if GeometryKeys.W_MM in geometry else None,
        h_mm=float(geometry[GeometryKeys.H_MM]) if GeometryKeys.H_MM in geometry else None,
        diameter_mm=float(geometry[GeometryKeys.DIAMETER_MM]) if GeometryKeys.DIAMETER_MM in geometry else None,
        points=points,
        holes=holes,
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

    edge_type = edge_data.get(GeometryKeys.TYPE)
    if edge_type is None:
        raise ValueError(f"EdgeTreatment: type is required, got {edge_data!r}")

    return EdgeTreatment(
        type=edge_type,
        radius_mm=edge_data.get(GeometryKeys.RADIUS_MM),
        distance_mm=edge_data.get(GeometryKeys.DISTANCE_MM),
        rough_allowance_mm=edge_data.get(GeometryKeys.ROUGH_ALLOWANCE_MM),
        finish_allowance_mm=edge_data.get(GeometryKeys.FINISH_ALLOWANCE_MM),
    )
