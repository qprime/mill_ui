from __future__ import annotations

from dataclasses import replace
from typing import Any

from layout_ast.layout import Feature, Geometry, Item
from layout_ast.layout import Placement as ASTPlacement
from templates.loader import expand_template

from .types import NestedPart, PartSpec

_CORNER_ROTATION_MAP = {"tl": "bl", "tr": "tl", "br": "tr", "bl": "br"}


def get_part_bounds(part_spec: PartSpec) -> tuple[float, float]:
    return (part_spec.width_mm, part_spec.height_mm)


def _build_geometry_data(
    shape: str,
    shape_params: dict[str, Any] | None,
    w: float,
    h: float,
) -> tuple[str, dict[str, Any]]:
    params = shape_params or {}

    if shape == "RoundedRect":
        radius_mm = params.get("radius_mm", 0.0)
        corners_tuple = params.get("corners")
        corners = frozenset(corners_tuple) if corners_tuple else None

        if corners is not None:
            radius_tl = radius_mm if "tl" in corners else 0.0
            radius_tr = radius_mm if "tr" in corners else 0.0
            radius_bl = radius_mm if "bl" in corners else 0.0
            radius_br = radius_mm if "br" in corners else 0.0
        else:
            radius_tl = radius_tr = radius_bl = radius_br = radius_mm

        data: dict[str, Any] = {
            "w_mm": w,
            "h_mm": h,
            "radius_tl_mm": radius_tl,
            "radius_tr_mm": radius_tr,
            "radius_bl_mm": radius_bl,
            "radius_br_mm": radius_br,
        }
        if radius_tl == radius_tr == radius_bl == radius_br:
            data["radius_mm"] = radius_tl
            data["corner_radius_mm"] = radius_tl
        return ("RoundedRect", data)

    elif shape == "Circle":
        diameter = min(w, h)
        return ("Circle", {"diameter_mm": diameter})

    elif shape == "Polygon":
        points = params.get("points", [])
        return ("Polygon", {"points": points, "holes": []})

    elif shape == "Triangle":
        half_w = w / 2
        half_h = h / 2
        points = [
            [-half_w, -half_h],
            [half_w, -half_h],
            [0.0, half_h],
        ]
        return ("Polygon", {"points": points, "holes": []})

    elif shape == "Ellipse":
        from core.geometry import ellipse_points

        pts = ellipse_points(0.0, 0.0, w / 2, h / 2)
        return ("Polygon", {"points": pts, "holes": []})

    else:
        return ("Rect", {"w_mm": w, "h_mm": h})


def _rotate_corners(shape_params: dict[str, Any] | None) -> dict[str, Any] | None:
    if shape_params is None:
        return None
    corners = shape_params.get("corners")
    if corners is None:
        return shape_params
    rotated = tuple(sorted(_CORNER_ROTATION_MAP[c] for c in corners))
    return {**shape_params, "corners": rotated}


def expand_part_to_items(
    part_spec: PartSpec,
    center_xy: tuple[float, float],
    rotated: bool,
    sheet_thickness_mm: float,
    shape_id_prefix: str = "",
) -> list[Item]:
    cx, cy = center_xy

    if part_spec.template:
        params = part_spec.template_params or {}

        region_w = part_spec.height_mm if rotated else part_spec.width_mm
        region_h = part_spec.width_mm if rotated else part_spec.height_mm

        items = expand_template(
            template_name=part_spec.template,
            params=params,
            region_width=region_w,
            region_height=region_h,
            sheet_thickness=sheet_thickness_mm,
        )

        template_center_x = region_w / 2
        template_center_y = region_h / 2

        result = []
        for i, item in enumerate(items):
            if item.placement is None:
                raise ValueError(f"Template item {i} missing placement")
            item_cx, item_cy = item.placement.center_xy_mm

            offset_x = item_cx - template_center_x
            offset_y = item_cy - template_center_y

            final_x = cx + offset_x
            final_y = cy + offset_y

            new_placement = ASTPlacement(center_xy_mm=(final_x, final_y))
            new_shape_id = f"{shape_id_prefix}{item.shape_id}" if item.shape_id else f"{shape_id_prefix}item{i}"

            result.append(replace(item, placement=new_placement, shape_id=new_shape_id))

        return result

    else:
        w = part_spec.height_mm if rotated else part_spec.width_mm
        h = part_spec.width_mm if rotated else part_spec.height_mm

        shape = part_spec.shape or "Rect"
        shape_params = part_spec.shape_params
        if rotated and shape == "RoundedRect":
            shape_params = _rotate_corners(shape_params)

        item_type, geometry_data = _build_geometry_data(shape, shape_params, w, h)

        holding = part_spec.holding
        feature_kwargs: dict[str, Any] = {
            "type": "profile",
            "depth_mm": 0.0,
            "is_through": True,
            "side": "outside",
        }
        if holding is not None:
            if holding.onion_skin_mm is not None:
                feature_kwargs["onion_skin_mm"] = holding.onion_skin_mm
            if holding.tab_count is not None:
                feature_kwargs["tab_count"] = holding.tab_count
            if holding.tab_height_mm is not None:
                feature_kwargs["tab_height_mm"] = holding.tab_height_mm
            if holding.tab_width_mm is not None:
                feature_kwargs["tab_width_mm"] = holding.tab_width_mm

        return [
            Item(
                kind="shape",
                type=item_type,
                geometry=Geometry(data=geometry_data),
                placement=ASTPlacement(center_xy_mm=(cx, cy)),
                feature=Feature(**feature_kwargs),
                shape_id=f"{shape_id_prefix}{item_type.lower()}",
                label=part_spec.name,
            )
        ]


def placement_to_items(
    placement: NestedPart,
    sheet_thickness_mm: float,
) -> list[Item]:
    prefix = f"{placement.part_spec.name}_{placement.instance_id}_"
    return expand_part_to_items(
        part_spec=placement.part_spec,
        center_xy=(placement.x_mm, placement.y_mm),
        rotated=placement.rotated,
        sheet_thickness_mm=sheet_thickness_mm,
        shape_id_prefix=prefix,
    )


__all__ = [
    "expand_part_to_items",
    "get_part_bounds",
    "placement_to_items",
]
