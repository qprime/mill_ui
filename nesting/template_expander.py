
from __future__ import annotations

from dataclasses import replace
from typing import Any, Protocol

from layout_ast.layout import LayoutAST, Item, Placement as ASTPlacement, Geometry

from .types import PartSpec, NestedPart


class TemplateProtocol(Protocol):

    @staticmethod
    def expand_to_ast(params: dict[str, Any], sheet_thickness_mm: float) -> LayoutAST:
        ...


TEMPLATE_REGISTRY: dict[str, TemplateProtocol] = {}


def register_template(name: str, template_class: TemplateProtocol) -> None:
    TEMPLATE_REGISTRY[name] = template_class


def _init_templates() -> None:
    try:
        from templates import Shaker
        register_template("Shaker", Shaker)
    except ImportError:
        pass


_init_templates()


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

    if part_spec.template and part_spec.template in TEMPLATE_REGISTRY:

        template_class = TEMPLATE_REGISTRY[part_spec.template]
        params = part_spec.template_params or {}


        if "outer_w" not in params:
            params = {**params, "outer_w": part_spec.width_mm}
        if "outer_h" not in params:
            params = {**params, "outer_h": part_spec.height_mm}


        template_ast = template_class.expand_to_ast(params, sheet_thickness_mm)


        template_center_x = template_ast.sheet.width_mm / 2
        template_center_y = template_ast.sheet.height_mm / 2


        items = []
        for i, item in enumerate(template_ast.items):
            item_cx, item_cy = item.placement.center_xy_mm

            offset_x = item_cx - template_center_x
            offset_y = item_cy - template_center_y


            if rotated:

                new_offset_x = -offset_y
                new_offset_y = offset_x
                offset_x, offset_y = new_offset_x, new_offset_y


                if item.type == "Rect":
                    old_w = item.geometry.data.get("w_mm", 0)
                    old_h = item.geometry.data.get("h_mm", 0)
                    new_geom = Geometry(data={"w_mm": old_h, "h_mm": old_w})
                    item = replace(item, geometry=new_geom)


            final_x = cx + offset_x
            final_y = cy + offset_y


            new_placement = ASTPlacement(center_xy_mm=(final_x, final_y))
            new_shape_id = f"{shape_id_prefix}{item.shape_id}" if item.shape_id else f"{shape_id_prefix}item{i}"

            items.append(replace(item, placement=new_placement, shape_id=new_shape_id))

        return items

    else:

        w = part_spec.height_mm if rotated else part_spec.width_mm
        h = part_spec.width_mm if rotated else part_spec.height_mm

        return [
            Item(
                kind="shape",
                type="Rect",
                geometry=Geometry(data={"w_mm": w, "h_mm": h}),
                placement=ASTPlacement(center_xy_mm=(cx, cy)),
                feature=_default_feature(),
                shape_id=f"{shape_id_prefix}rect",
            )
        ]


def _default_feature():
    from layout_ast.layout import Feature
    return Feature(type="profile", depth="through", side="outside")


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
    "TEMPLATE_REGISTRY",
    "register_template",
    "get_part_bounds",
    "expand_part_to_items",
    "placement_to_items",
]
