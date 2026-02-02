
from __future__ import annotations

from dataclasses import replace

from layout_ast.layout import Item, Placement as ASTPlacement, Geometry, Feature

from .types import PartSpec, NestedPart
from templates.loader import expand_template


def get_part_bounds(part_spec: PartSpec) -> tuple[float, float]:
    return (part_spec.width_mm, part_spec.height_mm)


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

        return [
            Item(
                kind="shape",
                type="Rect",
                geometry=Geometry(data={"w_mm": w, "h_mm": h}),
                placement=ASTPlacement(center_xy_mm=(cx, cy)),
                feature=Feature(type="profile", depth_mm=0.0, is_through=True, side="outside"),
                shape_id=f"{shape_id_prefix}rect",
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
    "get_part_bounds",
    "expand_part_to_items",
    "placement_to_items",
]
