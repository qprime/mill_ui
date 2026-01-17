
from __future__ import annotations

from typing import Any

from ir.removal_intent import (
    RemovalIntent,
    Bounds2D,
    Allowance,
    Constraints,
    TabConstraint,
    Island,
    EdgeTreatment,
)
from layout_ast.layout import Item
from core.constants import (
    HintKeys,
    GeometryKeys,
    TabKeys,
    MetadataKeys,
    FeatureType,
    ShapeType,
    Side,
)
from core.geometry import compute_shape_bounds


def profile_hint_to_removal_intent(
    hint: dict[str, Any],
    sheet_thickness_mm: float,
    region_id_prefix: str = "profile",
) -> RemovalIntent:

    hint_id = hint.get(HintKeys.ID, "")
    region_id = f"{region_id_prefix}_{hint_id}" if hint_id else region_id_prefix


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


    return RemovalIntent(
        region_id=region_id,
        bounds=bounds,
        z_top=0.0,
        z_bottom=-depth_mm,
        allowance=allowance,
        constraints=constraints,
        metadata={
            MetadataKeys.HINT_TYPE: FeatureType.PROFILE,
            HintKeys.SHAPE: hint.get(HintKeys.SHAPE),
            HintKeys.SIDE: side,
            MetadataKeys.ORIGINAL_ID: hint_id,
        },
    )


def pocket_hint_to_removal_intent(
    hint: dict[str, Any],
    region_id_prefix: str = "pocket",
) -> RemovalIntent:

    hint_id = hint.get(HintKeys.ID, "")
    region_id = f"{region_id_prefix}_{hint_id}" if hint_id else region_id_prefix


    depth_mm = float(hint.get(HintKeys.DEPTH_MM, 0.0))
    start_depth_mm = float(hint.get(HintKeys.START_DEPTH_MM, 0.0))


    bounds = _geometry_to_bounds(
        hint.get(HintKeys.SHAPE, ""),
        hint.get(HintKeys.GEOMETRY, {}),
        hint.get(HintKeys.CENTER_XY_MM),
    )


    allowance = Allowance()


    metadata = {
        MetadataKeys.HINT_TYPE: FeatureType.POCKET,
        HintKeys.SHAPE: hint.get(HintKeys.SHAPE),
        MetadataKeys.ORIGINAL_ID: hint_id,
    }


    if HintKeys.CORNER_CLEANUP_TOOL_DIAMETER_MM in hint:
        metadata[HintKeys.CORNER_CLEANUP_TOOL_DIAMETER_MM] = float(hint[HintKeys.CORNER_CLEANUP_TOOL_DIAMETER_MM])


    return RemovalIntent(
        region_id=region_id,
        bounds=bounds,
        z_top=-start_depth_mm,
        z_bottom=-(start_depth_mm + depth_mm),
        allowance=allowance,
        constraints=Constraints(),
        metadata=metadata,
    )


def hole_hint_to_removal_intent(
    hint: dict[str, Any],
    region_id_prefix: str = "hole",
) -> RemovalIntent:

    hint_id = hint.get(HintKeys.ID, "")
    region_id = f"{region_id_prefix}_{hint_id}" if hint_id else region_id_prefix


    depth_mm = float(hint.get(HintKeys.DEPTH_MM, 0.0))


    bounds = _geometry_to_bounds(
        hint.get(HintKeys.SHAPE, ""),
        hint.get(HintKeys.GEOMETRY, {}),
        hint.get(HintKeys.CENTER_XY_MM),
    )


    allowance = Allowance()


    return RemovalIntent(
        region_id=region_id,
        bounds=bounds,
        z_top=0.0,
        z_bottom=-depth_mm,
        allowance=allowance,
        constraints=Constraints(),
        metadata={
            MetadataKeys.HINT_TYPE: FeatureType.HOLE,
            HintKeys.SHAPE: hint.get(HintKeys.SHAPE),
            MetadataKeys.ORIGINAL_ID: hint_id,
        },
    )


def engrave_hint_to_removal_intent(
    hint: dict[str, Any],
    region_id_prefix: str = "engrave",
) -> RemovalIntent:

    hint_id = hint.get(HintKeys.ID, "")
    region_id = f"{region_id_prefix}_{hint_id}" if hint_id else region_id_prefix


    depth_mm = float(hint.get(HintKeys.DEPTH_MM, 0.0))


    bounds = _geometry_to_bounds(
        hint.get(HintKeys.SHAPE, ""),
        hint.get(HintKeys.GEOMETRY, {}),
        hint.get(HintKeys.CENTER_XY_MM),
    )


    allowance = Allowance()


    return RemovalIntent(
        region_id=region_id,
        bounds=bounds,
        z_top=0.0,
        z_bottom=-depth_mm,
        allowance=allowance,
        constraints=Constraints(),
        metadata={
            MetadataKeys.HINT_TYPE: FeatureType.ENGRAVE,
            HintKeys.SHAPE: hint.get(HintKeys.SHAPE),
            MetadataKeys.ORIGINAL_ID: hint_id,
        },
    )


def _geometry_to_bounds(shape: str, geometry: dict[str, Any], center_xy: tuple[float, float] | list[float] | None) -> Bounds2D:
    """Convert v1 hint geometry to bounds. Delegates to unified compute_shape_bounds()."""
    return compute_shape_bounds(shape, geometry, center_xy)


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
    height_mm = float(tabs_data.get(TabKeys.HEIGHT, tabs_data.get(TabKeys.HEIGHT_MM, 3.0)))


    width_value = tabs_data.get(TabKeys.WIDTH_MM, tabs_data.get(TabKeys.WIDTH))
    width_mm = float(width_value) if width_value is not None else None

    tab = TabConstraint(count=count, height_mm=height_mm, width_mm=width_mm)
    return Constraints(tabs=tab)


def item_to_removal_intent(
    item: Item,
    region_id_prefix: str = "item",
) -> RemovalIntent:
    if not item.geometry:
        raise ValueError(f"Item {item.shape_id} has no geometry")
    if not item.placement:
        raise ValueError(f"Item {item.shape_id} has no placement")
    if not item.feature:
        raise ValueError(f"Item {item.shape_id} has no feature")


    region_id = f"{region_id_prefix}_{item.shape_id}" if item.shape_id else region_id_prefix


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


    return RemovalIntent(
        region_id=region_id,
        bounds=bounds,
        z_top=0.0,
        z_bottom=-depth_mm,
        allowance=allowance,
        constraints=constraints,
        metadata={
            MetadataKeys.ITEM_TYPE: item.type,
            MetadataKeys.FEATURE_TYPE: item.feature.type,
            MetadataKeys.SHAPE_ID: item.shape_id,
        },
    )


def _item_geometry_to_bounds(item_type: str, geometry_data: dict[str, Any], cx: float, cy: float) -> Bounds2D:
    """Convert Item geometry to bounds. Delegates to unified compute_shape_bounds()."""
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
