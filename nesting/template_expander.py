"""Template expansion for nesting.

This module connects PartSpec with the template system to expand
parts into LayoutAST Items at specific positions.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Protocol

from layout_ast.layout import LayoutAST, Item, Placement as ASTPlacement, Geometry

from .types import PartSpec, NestedPart


class TemplateProtocol(Protocol):
    """Protocol for template classes."""

    @staticmethod
    def expand_to_ast(params: dict[str, Any], sheet_thickness_mm: float) -> LayoutAST:
        """Expand template parameters to LayoutAST."""
        ...


# Template registry - maps template names to classes
TEMPLATE_REGISTRY: dict[str, TemplateProtocol] = {}


def register_template(name: str, template_class: TemplateProtocol) -> None:
    """Register a template class.

    Args:
        name: Template name (e.g., "Shaker")
        template_class: Class implementing TemplateProtocol
    """
    TEMPLATE_REGISTRY[name] = template_class


def _init_templates() -> None:
    """Initialize template registry with built-in templates."""
    try:
        from templates import Shaker
        register_template("Shaker", Shaker)
    except ImportError:
        pass  # Templates module not available


# Initialize on module load
_init_templates()


def get_part_bounds(part_spec: PartSpec) -> tuple[float, float]:
    """Get bounding box dimensions for a part.

    For parts with templates, this returns the outer dimensions
    that the template will produce.

    Args:
        part_spec: Part specification

    Returns:
        (width, height) in mm
    """
    # For now, use explicit dimensions from PartSpec
    # Templates could override this if they produce different bounds
    return (part_spec.width_mm, part_spec.height_mm)


def expand_part_to_items(
    part_spec: PartSpec,
    center_xy: tuple[float, float],
    rotated: bool,
    sheet_thickness_mm: float,
    shape_id_prefix: str = "",
) -> list[Item]:
    """Expand a PartSpec into positioned Items.

    Args:
        part_spec: Part specification (may have template)
        center_xy: Center position on sheet
        rotated: Whether part is rotated 90 degrees
        sheet_thickness_mm: Material thickness
        shape_id_prefix: Prefix for shape IDs (e.g., "door1_")

    Returns:
        List of Items positioned at center_xy
    """
    cx, cy = center_xy

    if part_spec.template and part_spec.template in TEMPLATE_REGISTRY:
        # Expand template
        template_class = TEMPLATE_REGISTRY[part_spec.template]
        params = part_spec.template_params or {}

        # Ensure outer dimensions are set from PartSpec if not in params
        if "outer_w" not in params:
            params = {**params, "outer_w": part_spec.width_mm}
        if "outer_h" not in params:
            params = {**params, "outer_h": part_spec.height_mm}

        # Generate AST from template
        template_ast = template_class.expand_to_ast(params, sheet_thickness_mm)

        # Calculate offset from template's center to our placement
        template_center_x = template_ast.sheet.width_mm / 2
        template_center_y = template_ast.sheet.height_mm / 2

        # Reposition items from template
        items = []
        for i, item in enumerate(template_ast.items):
            item_cx, item_cy = item.placement.center_xy_mm
            # Offset from template center
            offset_x = item_cx - template_center_x
            offset_y = item_cy - template_center_y

            # Apply rotation if needed
            if rotated:
                # Rotate 90 degrees: (x, y) -> (-y, x)
                new_offset_x = -offset_y
                new_offset_y = offset_x
                offset_x, offset_y = new_offset_x, new_offset_y

                # Also need to swap width/height for Rect geometries
                if item.type == "Rect":
                    old_w = item.geometry.data.get("w_mm", 0)
                    old_h = item.geometry.data.get("h_mm", 0)
                    new_geom = Geometry(data={"w_mm": old_h, "h_mm": old_w})
                    item = replace(item, geometry=new_geom)

            # Calculate final position
            final_x = cx + offset_x
            final_y = cy + offset_y

            # Update placement and shape_id
            new_placement = ASTPlacement(center_xy_mm=(final_x, final_y))
            new_shape_id = f"{shape_id_prefix}{item.shape_id}" if item.shape_id else f"{shape_id_prefix}item{i}"

            items.append(replace(item, placement=new_placement, shape_id=new_shape_id))

        return items

    else:
        # No template - create simple rect profile
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
    """Create default feature for simple rect parts."""
    from layout_ast.layout import Feature
    return Feature(type="profile", depth="through", side="outside")


def placement_to_items(
    placement: NestedPart,
    sheet_thickness_mm: float,
) -> list[Item]:
    """Convert a NestedPart to LayoutAST Items.

    Args:
        placement: NestedPart from nesting solution
        sheet_thickness_mm: Material thickness

    Returns:
        List of positioned Items
    """
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
