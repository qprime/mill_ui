
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
    MetadataKeys,
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

    elif item.feature.type == FeatureType.BEVEL:
        # Bevel (raised panel border) - store bevel parameters in metadata
        # CAM backend chooses machining strategy (chamfer mill, ball nose ramp, etc.)
        from ir.removal_intent import DepthProfile, Allowance, Constraints
        from adapters.hints_to_removal import _geometry_to_bounds
        import math

        bevel_width = item.feature.bevel_width_mm or 0.0
        bevel_angle = item.feature.bevel_angle_deg or 45.0
        inner_depth = item.feature.bevel_inner_depth_mm or 0.0

        # Calculate depth from bevel width and angle for bounds/depth_mm
        if bevel_angle > 0 and bevel_angle < 90:
            calculated_depth = bevel_width * math.tan(math.radians(bevel_angle))
        else:
            calculated_depth = inner_depth if inner_depth > 0 else bevel_width

        bounds = _geometry_to_bounds(
            hint[HintKeys.SHAPE],
            hint[HintKeys.GEOMETRY],
            hint[HintKeys.CENTER_XY_MM],
        )

        # Use constant depth profile - bevel details go in metadata
        depth_profile = DepthProfile.constant(
            z_top=0.0,
            z_bottom=-calculated_depth,
        )

        return RemovalIntent(
            region_id=f"bevel_{hint[HintKeys.ID]}",
            bounds=bounds,
            depth_profile=depth_profile,
            allowance=Allowance(),
            constraints=Constraints(),
            metadata={
                MetadataKeys.HINT_TYPE: FeatureType.BEVEL,
                MetadataKeys.ITEM_TYPE: item.type,
                MetadataKeys.FEATURE_TYPE: item.feature.type,
                MetadataKeys.SHAPE_ID: item.shape_id,
                MetadataKeys.BEVEL: {
                    MetadataKeys.WIDTH_MM: bevel_width,
                    MetadataKeys.ANGLE_DEG: bevel_angle,
                    MetadataKeys.INNER_DEPTH_MM: inner_depth,
                },
            },
        )

    elif item.feature.type == FeatureType.CHAMFER:
        # Chamfer - store chamfer parameters in metadata
        # CAM backend chooses machining strategy (chamfer mill, V-bit, etc.)
        from ir.removal_intent import DepthProfile, Allowance, Constraints
        from adapters.hints_to_removal import _geometry_to_bounds
        import math

        chamfer_width = item.feature.chamfer_width_mm or 0.0
        chamfer_angle = item.feature.chamfer_angle_deg or 45.0
        side = item.feature.side or "outside"

        # Calculate depth from chamfer width and angle for bounds/depth_mm
        if chamfer_angle > 0 and chamfer_angle < 90:
            calculated_depth = chamfer_width * math.tan(math.radians(chamfer_angle))
        else:
            calculated_depth = chamfer_width

        bounds = _geometry_to_bounds(
            hint[HintKeys.SHAPE],
            hint[HintKeys.GEOMETRY],
            hint[HintKeys.CENTER_XY_MM],
        )

        # Use constant depth profile - chamfer details go in metadata
        depth_profile = DepthProfile.constant(
            z_top=0.0,
            z_bottom=-calculated_depth,
        )

        return RemovalIntent(
            region_id=f"chamfer_{hint[HintKeys.ID]}",
            bounds=bounds,
            depth_profile=depth_profile,
            allowance=Allowance(),
            constraints=Constraints(),
            metadata={
                MetadataKeys.HINT_TYPE: FeatureType.CHAMFER,
                MetadataKeys.ITEM_TYPE: item.type,
                MetadataKeys.FEATURE_TYPE: item.feature.type,
                MetadataKeys.SHAPE_ID: item.shape_id,
                HintKeys.SIDE: side,
                MetadataKeys.CHAMFER: {
                    MetadataKeys.WIDTH_MM: chamfer_width,
                    MetadataKeys.ANGLE_DEG: chamfer_angle,
                },
            },
        )

    elif item.feature.type == FeatureType.WAVE:
        # Wave pattern - store wave parameters in metadata
        # CAM backend generates parallel groove toolpaths following wave shape
        from ir.removal_intent import DepthProfile, Allowance, Constraints
        from adapters.hints_to_removal import _geometry_to_bounds

        bounds = _geometry_to_bounds(
            hint[HintKeys.SHAPE],
            hint[HintKeys.GEOMETRY],
            hint[HintKeys.CENTER_XY_MM],
        )

        depth_mm = item.feature.depth_mm or 0.0

        # Use constant depth profile - wave details go in metadata
        depth_profile = DepthProfile.constant(
            z_top=0.0,
            z_bottom=-depth_mm,
        )

        # Extract wave parameters from geometry data (set by layout_resolver)
        geometry_data = item.geometry.data if item.geometry else {}
        wave_metadata = {
            "wave_count": geometry_data.get("wave_count"),
            "amplitude_mm": geometry_data.get("wave_amplitude_mm"),
            "wavelength_mm": geometry_data.get("wave_wavelength_mm"),
            "groove_width_mm": geometry_data.get("wave_groove_width_mm"),
        }

        return RemovalIntent(
            region_id=f"wave_{hint[HintKeys.ID]}",
            bounds=bounds,
            depth_profile=depth_profile,
            allowance=Allowance(),
            constraints=Constraints(),
            metadata={
                MetadataKeys.HINT_TYPE: FeatureType.WAVE,
                MetadataKeys.ITEM_TYPE: item.type,
                MetadataKeys.FEATURE_TYPE: item.feature.type,
                MetadataKeys.SHAPE_ID: item.shape_id,
                "wave": wave_metadata,
            },
        )

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
