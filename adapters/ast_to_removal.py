
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
    intents: list[RemovalIntent] = []

    for item in ast.items:

        if item.kind != "shape" or not item.feature:
            continue

        try:
            intent = item_to_removal_intent(
                item,
                sheet_thickness_mm=ast.sheet.thickness_mm
            )
            intents.append(intent)
        except ValueError as e:


            continue

    return intents


def item_to_removal_intent(
    item: Item,
    sheet_thickness_mm: float,
) -> RemovalIntent:
    if not item.geometry:
        raise ValueError(f"Item {item.shape_id} has no geometry")
    if not item.placement:
        raise ValueError(f"Item {item.shape_id} has no placement")
    if not item.feature:
        raise ValueError(f"Item {item.shape_id} has no feature")


    hint = {
        "id": item.shape_id or "",
        "shape": item.type,
        "geometry": item.geometry.data,
        "center_xy_mm": item.placement.center_xy_mm,
        "depth_mm": _resolve_depth(item.feature.depth, item.feature.depth_mm, sheet_thickness_mm),
    }


    if item.feature.type == "profile":
        if item.feature.side:
            hint["side"] = item.feature.side

        if item.feature.tab_count is not None and item.feature.tab_height_mm is not None:
            hint["tabs"] = {
                "count": item.feature.tab_count,
                "height_mm": item.feature.tab_height_mm,
                "width_mm": item.feature.tab_width_mm,
            }
        return profile_hint_to_removal_intent(hint, sheet_thickness_mm=sheet_thickness_mm)

    elif item.feature.type == "pocket":

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
    if depth_mm is not None:
        return float(depth_mm)

    if depth == "through":
        return sheet_thickness_mm

    if depth == "half":
        return sheet_thickness_mm / 2.0


    return sheet_thickness_mm


__all__ = [
    "ast_to_removal_intents",
    "item_to_removal_intent",
]
