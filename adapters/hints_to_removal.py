
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


def profile_hint_to_removal_intent(
    hint: dict[str, Any],
    sheet_thickness_mm: float,
    region_id_prefix: str = "profile",
) -> RemovalIntent:

    hint_id = hint.get("id", "")
    region_id = f"{region_id_prefix}_{hint_id}" if hint_id else region_id_prefix


    depth_mm = float(hint.get("depth_mm", sheet_thickness_mm))


    bounds = _geometry_to_bounds(hint.get("shape", ""), hint.get("geometry", {}), hint.get("center_xy_mm"))


    side = hint.get("side", "outside").lower()
    allowance = _side_to_allowance(side)


    tabs_data = hint.get("tabs")
    constraints = _tabs_to_constraints(tabs_data) if tabs_data else Constraints()


    return RemovalIntent(
        region_id=region_id,
        bounds=bounds,
        z_top=0.0,
        z_bottom=-depth_mm,
        allowance=allowance,
        constraints=constraints,
        metadata={
            "hint_type": "profile",
            "shape": hint.get("shape"),
            "side": side,
            "original_id": hint_id,
        },
    )


def pocket_hint_to_removal_intent(
    hint: dict[str, Any],
    region_id_prefix: str = "pocket",
) -> RemovalIntent:

    hint_id = hint.get("id", "")
    region_id = f"{region_id_prefix}_{hint_id}" if hint_id else region_id_prefix


    depth_mm = float(hint.get("depth_mm", 0.0))
    start_depth_mm = float(hint.get("start_depth_mm", 0.0))


    bounds = _geometry_to_bounds(hint.get("shape", ""), hint.get("geometry", {}), hint.get("center_xy_mm"))


    allowance = Allowance()


    metadata = {
        "hint_type": "pocket",
        "shape": hint.get("shape"),
        "original_id": hint_id,
    }


    if "corner_cleanup_tool_diameter_mm" in hint:
        metadata["corner_cleanup_tool_diameter_mm"] = float(hint["corner_cleanup_tool_diameter_mm"])


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

    hint_id = hint.get("id", "")
    region_id = f"{region_id_prefix}_{hint_id}" if hint_id else region_id_prefix


    depth_mm = float(hint.get("depth_mm", 0.0))


    bounds = _geometry_to_bounds(hint.get("shape", ""), hint.get("geometry", {}), hint.get("center_xy_mm"))


    allowance = Allowance()


    return RemovalIntent(
        region_id=region_id,
        bounds=bounds,
        z_top=0.0,
        z_bottom=-depth_mm,
        allowance=allowance,
        constraints=Constraints(),
        metadata={
            "hint_type": "hole",
            "shape": hint.get("shape"),
            "original_id": hint_id,
        },
    )


def engrave_hint_to_removal_intent(
    hint: dict[str, Any],
    region_id_prefix: str = "engrave",
) -> RemovalIntent:

    hint_id = hint.get("id", "")
    region_id = f"{region_id_prefix}_{hint_id}" if hint_id else region_id_prefix


    depth_mm = float(hint.get("depth_mm", 0.0))


    bounds = _geometry_to_bounds(hint.get("shape", ""), hint.get("geometry", {}), hint.get("center_xy_mm"))


    allowance = Allowance()


    return RemovalIntent(
        region_id=region_id,
        bounds=bounds,
        z_top=0.0,
        z_bottom=-depth_mm,
        allowance=allowance,
        constraints=Constraints(),
        metadata={
            "hint_type": "engrave",
            "shape": hint.get("shape"),
            "original_id": hint_id,
        },
    )


def _geometry_to_bounds(shape: str, geometry: dict[str, Any], center_xy: tuple[float, float] | list[float] | None) -> Bounds2D:
    if center_xy is None:
        center_xy = (0.0, 0.0)
    elif isinstance(center_xy, list):
        center_xy = (float(center_xy[0]), float(center_xy[1]))

    cx, cy = float(center_xy[0]), float(center_xy[1])

    shape_lower = shape.lower()

    if shape_lower in ("rect", "rectangle"):
        w = float(geometry.get("w_mm", 0.0))
        h = float(geometry.get("h_mm", 0.0))
        half_w, half_h = w / 2.0, h / 2.0
        return Bounds2D(
            x_min=cx - half_w,
            x_max=cx + half_w,
            y_min=cy - half_h,
            y_max=cy + half_h,
        )

    elif shape_lower == "circle":
        diameter = float(geometry.get("diameter_mm", 0.0))
        radius = diameter / 2.0
        return Bounds2D(
            x_min=cx - radius,
            x_max=cx + radius,
            y_min=cy - radius,
            y_max=cy + radius,
        )

    else:

        return Bounds2D(
            x_min=cx - 0.5,
            x_max=cx + 0.5,
            y_min=cy - 0.5,
            y_max=cy + 0.5,
        )


def _side_to_allowance(side: str) -> Allowance:
    side_lower = side.lower()

    if side_lower == "outside":

        return Allowance(outside=0.0)
    elif side_lower == "inside":

        return Allowance(inside=0.0)
    elif side_lower == "on":

        return Allowance(on=0.0)
    else:

        return Allowance(outside=0.0)


def _tabs_to_constraints(tabs_data: dict[str, Any] | None) -> Constraints:
    if not tabs_data:
        return Constraints()

    count = int(tabs_data.get("count", 0))
    height_mm = float(tabs_data.get("height", tabs_data.get("height_mm", 3.0)))


    width_value = tabs_data.get("width_mm", tabs_data.get("width"))
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
    if item.feature.type == "profile" and item.feature.side:
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
            "item_type": item.type,
            "feature_type": item.feature.type,
            "shape_id": item.shape_id,
        },
    )


def _item_geometry_to_bounds(item_type: str, geometry_data: dict[str, Any], cx: float, cy: float) -> Bounds2D:
    if item_type == "Rect" or item_type == "RoundedRect":
        w = float(geometry_data.get("w_mm", 0.0))
        h = float(geometry_data.get("h_mm", 0.0))
        half_w, half_h = w / 2.0, h / 2.0
        return Bounds2D(
            x_min=cx - half_w,
            x_max=cx + half_w,
            y_min=cy - half_h,
            y_max=cy + half_h,
        )
    elif item_type == "Circle":
        diameter = float(geometry_data.get("diameter_mm", 0.0))
        radius = diameter / 2.0
        return Bounds2D(
            x_min=cx - radius,
            x_max=cx + radius,
            y_min=cy - radius,
            y_max=cy + radius,
        )
    else:

        return Bounds2D(
            x_min=cx - 0.5,
            x_max=cx + 0.5,
            y_min=cy - 0.5,
            y_max=cy + 0.5,
        )


def _extract_islands_from_geometry(geometry_data: dict[str, Any]) -> list[Island]:
    islands = []
    island_data = geometry_data.get("islands", [])

    for island_dict in island_data:
        bounds = Bounds2D(
            x_min=float(island_dict["x_min"]),
            x_max=float(island_dict["x_max"]),
            y_min=float(island_dict["y_min"]),
            y_max=float(island_dict["y_max"]),
        )
        islands.append(Island(bounds=bounds))

    return islands


def _extract_edge_treatment_from_geometry(geometry_data: dict[str, Any]) -> EdgeTreatment | None:
    edge_data = geometry_data.get("edge_treatment")
    if not edge_data:
        return None

    return EdgeTreatment(
        type=edge_data["type"],
        radius_mm=edge_data.get("radius_mm"),
        distance_mm=edge_data.get("distance_mm"),
        rough_allowance_mm=edge_data.get("rough_allowance_mm"),
        finish_allowance_mm=edge_data.get("finish_allowance_mm"),
    )
