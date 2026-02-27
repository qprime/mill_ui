from __future__ import annotations

import logging
from dataclasses import replace
from typing import Any

from adapters.hints_to_removal import (
    _geometry_dict_to_shape_geometry,
    _geometry_to_bounds,
    engrave_hint_to_removal_intent,
    hole_hint_to_removal_intent,
    pocket_hint_to_removal_intent,
    profile_hint_to_removal_intent,
)
from core.constants import (
    FeatureType,
    HintKeys,
    TabKeys,
)
from core.geometry import calculate_angled_depth
from ir.removal_intent import (
    Allowance,
    BevelSpec,
    ChamferSpec,
    Constraints,
    DepthProfile,
    EdgeFeatureSpec,
    RemovalIntent,
)
from layout_ast.layout import Feature, Item, LayoutAST

logger = logging.getLogger(__name__)


def ast_to_removal_intents(
    ast: LayoutAST,
    warnings: list[str] | None = None,
) -> list[RemovalIntent]:
    intents: list[RemovalIntent] = []

    for item in ast.items:
        if item.kind != "shape" or not item.feature:
            continue

        try:
            intent = item_to_removal_intent(item, sheet_thickness_mm=ast.sheet.thickness_mm)
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
        HintKeys.DEPTH_MM: _resolve_depth(item.feature, sheet_thickness_mm),
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
        intent = profile_hint_to_removal_intent(hint, sheet_thickness_mm=sheet_thickness_mm)
        if item.feature.feeds_override is not None:
            intent = replace(intent, feeds_override=item.feature.feeds_override)
        return intent

    elif item.feature.type == FeatureType.POCKET:
        if item.feature.corner_cleanup_tool_diameter_mm is not None:
            hint[HintKeys.CORNER_CLEANUP_TOOL_DIAMETER_MM] = item.feature.corner_cleanup_tool_diameter_mm
        intent = pocket_hint_to_removal_intent(hint)
        if item.feature.dogbone is not None:
            intent = replace(intent, dogbone=item.feature.dogbone)
        if item.feature.feeds_override is not None:
            intent = replace(intent, feeds_override=item.feature.feeds_override)
        return intent

    elif item.feature.type == FeatureType.HOLE:
        intent = hole_hint_to_removal_intent(hint)
        if item.feature.feeds_override is not None:
            intent = replace(intent, feeds_override=item.feature.feeds_override)
        return intent

    elif item.feature.type == FeatureType.ENGRAVE:
        intent = engrave_hint_to_removal_intent(hint)
        if item.feature.feeds_override is not None:
            intent = replace(intent, feeds_override=item.feature.feeds_override)
        return intent

    elif item.feature.type == FeatureType.BEVEL:
        bevel_width = item.feature.bevel_width_mm or 0.0
        bevel_angle = item.feature.bevel_angle_deg or 45.0
        inner_depth = item.feature.bevel_inner_depth_mm or 0.0
        calculated_depth = calculate_angled_depth(bevel_width, bevel_angle, inner_depth)

        return _build_edge_feature_intent(
            hint,
            item,
            FeatureType.BEVEL,
            calculated_depth,
            edge_feature=BevelSpec(width_mm=bevel_width, angle_deg=bevel_angle, inner_depth_mm=inner_depth),
        )

    elif item.feature.type == FeatureType.CHAMFER:
        chamfer_width = item.feature.chamfer_width_mm or 0.0
        chamfer_angle = item.feature.chamfer_angle_deg or 45.0
        side = item.feature.side or "outside"
        calculated_depth = calculate_angled_depth(chamfer_width, chamfer_angle)

        return _build_edge_feature_intent(
            hint,
            item,
            FeatureType.CHAMFER,
            calculated_depth,
            side=side,
            edge_feature=ChamferSpec(width_mm=chamfer_width, angle_deg=chamfer_angle),
        )

    else:
        raise ValueError(f"Unknown feature type: {item.feature.type}")


def _resolve_depth(feature: Feature, sheet_thickness_mm: float) -> float:
    if feature.is_through:
        return sheet_thickness_mm
    return float(feature.depth_mm)


def _build_edge_feature_intent(
    hint: dict[str, Any],
    item: Item,
    feature_type: str,
    depth_mm: float,
    side: str | None = None,
    edge_feature: EdgeFeatureSpec | None = None,
) -> RemovalIntent:
    shape = hint[HintKeys.SHAPE]
    geometry = hint[HintKeys.GEOMETRY]
    bounds = _geometry_to_bounds(shape, geometry, hint[HintKeys.CENTER_XY_MM])
    depth_profile = DepthProfile.constant(z_top=0.0, z_bottom=-depth_mm)
    shape_geometry = _geometry_dict_to_shape_geometry(shape, geometry)

    assert item.feature is not None
    return RemovalIntent(
        region_id=f"{feature_type}_{hint[HintKeys.ID]}",
        bounds=bounds,
        depth_profile=depth_profile,
        hint_type=feature_type,
        shape=shape,
        side=side,
        item_type=item.type,
        feature_type=item.feature.type,
        shape_id=item.shape_id,
        shape_geometry=shape_geometry,
        edge_feature=edge_feature,
        allowance=Allowance(),
        constraints=Constraints(),
        feeds_override=item.feature.feeds_override,
    )


__all__ = [
    "ast_to_removal_intents",
    "item_to_removal_intent",
]
