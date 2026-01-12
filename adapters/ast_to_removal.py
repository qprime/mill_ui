"""Adapter: LayoutAST → RemovalIntent IR.

Provides clean, high-level API for converting LayoutAST items to RemovalIntent records.
This is the canonical AST → IR adapter as documented in the README.

All dimensions in millimeters. Z-axis: positive up, negative down into material.
"""

from __future__ import annotations

from layout_ast.layout import LayoutAST, Item
from ir.removal_intent import RemovalIntent
from adapters.hints_to_removal import (
    item_to_removal_intent as _item_to_removal_intent,
    profile_hint_to_removal_intent,
    pocket_hint_to_removal_intent,
    hole_hint_to_removal_intent,
    engrave_hint_to_removal_intent,
)


def ast_to_removal_intents(ast: LayoutAST) -> list[RemovalIntent]:
    """Convert entire LayoutAST to list of RemovalIntents.

    This is the primary entry point for AST → IR conversion.

    Args:
        ast: LayoutAST instance with sheet and items

    Returns:
        List of RemovalIntent records (one per shape feature)

    Example:
        >>> ast = parse_pml(pml_text)
        >>> intents = ast_to_removal_intents(ast)
        >>> for intent in intents:
        ...     print(f"{intent.region_id}: {intent.depth_mm()}mm deep")
    """
    intents: list[RemovalIntent] = []

    for item in ast.items:
        # Skip items without features (templates, components, etc.)
        if item.kind != "shape" or not item.feature:
            continue

        try:
            intent = item_to_removal_intent(
                item,
                sheet_thickness_mm=ast.sheet.thickness_mm
            )
            intents.append(intent)
        except ValueError as e:
            # Skip items with invalid geometry/placement/feature
            # Log warning in production, silently skip for now
            continue

    return intents


def item_to_removal_intent(
    item: Item,
    sheet_thickness_mm: float,
) -> RemovalIntent:
    """Convert single LayoutAST Item to RemovalIntent.

    Handles conversion based on feature type (profile, pocket, hole, engrave).

    Args:
        item: LayoutAST Item with geometry, placement, and feature
        sheet_thickness_mm: Sheet thickness for through-cut depth calculation

    Returns:
        RemovalIntent for this item's feature operation

    Raises:
        ValueError: If item lacks necessary attributes or has unknown feature type

    Example:
        >>> item = Item(
        ...     kind="shape",
        ...     type="Rect",
        ...     geometry=Geometry(data={"w_mm": 100, "h_mm": 50}),
        ...     placement=Placement(center_xy_mm=(150, 75)),
        ...     feature=Feature(type="profile", depth="through", side="outside"),
        ...     shape_id="outer"
        ... )
        >>> intent = item_to_removal_intent(item, sheet_thickness_mm=19.0)
        >>> assert intent.depth_mm() == 19.0
    """
    if not item.geometry:
        raise ValueError(f"Item {item.shape_id} has no geometry")
    if not item.placement:
        raise ValueError(f"Item {item.shape_id} has no placement")
    if not item.feature:
        raise ValueError(f"Item {item.shape_id} has no feature")

    # Convert to intermediate hint dict format
    # (This maintains compatibility with existing hint-based conversion)
    hint = {
        "id": item.shape_id or "",
        "shape": item.type,
        "geometry": item.geometry.data,
        "center_xy_mm": item.placement.center_xy_mm,
        "depth_mm": _resolve_depth(item.feature.depth, item.feature.depth_mm, sheet_thickness_mm),
    }

    # Add feature-specific fields
    if item.feature.type == "profile":
        if item.feature.side:
            hint["side"] = item.feature.side
        return profile_hint_to_removal_intent(hint, sheet_thickness_mm=sheet_thickness_mm)

    elif item.feature.type == "pocket":
        # Add corner cleanup metadata if specified
        if item.feature.corner_cleanup_tool_diameter_mm is not None:
            hint["corner_cleanup_tool_diameter_mm"] = item.feature.corner_cleanup_tool_diameter_mm
        return pocket_hint_to_removal_intent(hint)

    elif item.feature.type == "hole":
        return hole_hint_to_removal_intent(hint)

    elif item.feature.type == "engrave":
        return engrave_hint_to_removal_intent(hint)

    else:
        raise ValueError(f"Unknown feature type: {item.feature.type}")


def _resolve_depth(depth: str | None, depth_mm: float | None, sheet_thickness_mm: float) -> float:
    """Resolve feature depth to numeric value in millimeters.

    Args:
        depth: Symbolic depth ("through", "half", etc.) or None
        depth_mm: Explicit depth in mm or None
        sheet_thickness_mm: Sheet thickness for symbolic depth resolution

    Returns:
        Resolved depth in millimeters
    """
    if depth_mm is not None:
        return float(depth_mm)

    if depth == "through":
        return sheet_thickness_mm

    if depth == "half":
        return sheet_thickness_mm / 2.0

    # Default: through-cut
    return sheet_thickness_mm


__all__ = [
    "ast_to_removal_intents",
    "item_to_removal_intent",
]
