
from __future__ import annotations

import logging
from typing import Optional

from layout_ast.layout import LayoutAST, Item
from ir.removal_intent import RemovalIntent

logger = logging.getLogger(__name__)
from adapters.hints_to_removal import (
    item_to_removal_intent as _item_to_removal_intent,
    profile_hint_to_removal_intent,
    pocket_hint_to_removal_intent,
    hole_hint_to_removal_intent,
    engrave_hint_to_removal_intent,
)
from core.constants import (
    HintKeys,
    TabKeys,
    FeatureType,
    DepthMode,
)


def ast_to_removal_intents(
    ast: LayoutAST,
    warnings: Optional[list[str]] = None,
) -> list[RemovalIntent]:
    """Convert LayoutAST to list of RemovalIntent.

    Args:
        ast: The layout AST to convert.
        warnings: Optional list to collect warning messages. If provided,
            conversion errors will be appended as strings instead of being
            silently ignored.

    Returns:
        List of RemovalIntent objects for valid items.
    """
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
            msg = f"Skipping item '{item.shape_id}': {e}"
            logger.warning(msg)
            if warnings is not None:
                warnings.append(msg)
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
        HintKeys.ID: item.shape_id or "",
        HintKeys.SHAPE: item.type,
        HintKeys.GEOMETRY: item.geometry.data,
        HintKeys.CENTER_XY_MM: item.placement.center_xy_mm,
        HintKeys.DEPTH_MM: _resolve_depth(item.feature.depth, item.feature.depth_mm, sheet_thickness_mm),
    }


    if item.feature.type == FeatureType.PROFILE:
        if item.feature.side:
            hint[HintKeys.SIDE] = item.feature.side

        if item.feature.tab_count is not None and item.feature.tab_height_mm is not None:
            hint[HintKeys.TABS] = {
                TabKeys.COUNT: item.feature.tab_count,
                TabKeys.HEIGHT_MM: item.feature.tab_height_mm,
                TabKeys.WIDTH_MM: item.feature.tab_width_mm,
            }
        return profile_hint_to_removal_intent(hint, sheet_thickness_mm=sheet_thickness_mm)

    elif item.feature.type == FeatureType.POCKET:

        if item.feature.corner_cleanup_tool_diameter_mm is not None:
            hint[HintKeys.CORNER_CLEANUP_TOOL_DIAMETER_MM] = item.feature.corner_cleanup_tool_diameter_mm
        return pocket_hint_to_removal_intent(hint)

    elif item.feature.type == FeatureType.HOLE:
        return hole_hint_to_removal_intent(hint)

    elif item.feature.type == FeatureType.ENGRAVE:
        return engrave_hint_to_removal_intent(hint)

    else:
        raise ValueError(f"Unknown feature type: {item.feature.type}")


def _resolve_depth(depth: str | None, depth_mm: float | None, sheet_thickness_mm: float) -> float:
    """Resolve depth to millimeters.

    Args:
        depth: String depth mode ("through", "half") or None
        depth_mm: Explicit depth in mm, takes precedence if provided
        sheet_thickness_mm: Sheet thickness for resolving relative depths

    Returns:
        Depth in millimeters
    """
    if depth_mm is not None:
        return float(depth_mm)

    # Use DepthMode.resolve() for string modes, defaults to sheet thickness
    return DepthMode.resolve(depth, sheet_thickness_mm)


__all__ = [
    "ast_to_removal_intents",
    "item_to_removal_intent",
]
