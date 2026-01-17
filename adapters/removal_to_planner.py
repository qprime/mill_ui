
from __future__ import annotations

from typing import Any

from ir.removal_intent import RemovalIntent
from core.constants import (
    HintKeys,
    GeometryKeys,
    TabKeys,
    MetadataKeys,
    FeatureType,
    ShapeType,
    HintCollectionKeys,
)


def removal_intent_to_v1_hint(intent: RemovalIntent) -> dict[str, Any]:

    hint_type = intent.metadata.get(MetadataKeys.HINT_TYPE, FeatureType.POCKET)
    shape = intent.metadata.get(HintKeys.SHAPE, ShapeType.RECT)


    depth_mm = intent.depth_mm()


    cx = (intent.bounds.x_min + intent.bounds.x_max) / 2.0
    cy = (intent.bounds.y_min + intent.bounds.y_max) / 2.0


    geometry: dict[str, Any] = {}
    if ShapeType.is_rect(shape):
        w_mm = intent.bounds.x_max - intent.bounds.x_min
        h_mm = intent.bounds.y_max - intent.bounds.y_min
        geometry = {GeometryKeys.W_MM: w_mm, GeometryKeys.H_MM: h_mm}
    elif ShapeType.is_circle(shape):

        diameter_mm = intent.bounds.x_max - intent.bounds.x_min
        geometry = {GeometryKeys.DIAMETER_MM: diameter_mm}
    else:

        w_mm = intent.bounds.x_max - intent.bounds.x_min
        h_mm = intent.bounds.y_max - intent.bounds.y_min
        geometry = {GeometryKeys.W_MM: w_mm, GeometryKeys.H_MM: h_mm}


    hint: dict[str, Any] = {
        HintKeys.ID: intent.metadata.get(MetadataKeys.ORIGINAL_ID, intent.region_id),
        HintKeys.SHAPE: shape,
        HintKeys.GEOMETRY: geometry,
        HintKeys.CENTER_XY_MM: (cx, cy),
        HintKeys.DEPTH_MM: depth_mm,
    }


    if hint_type == FeatureType.PROFILE:

        side = intent.metadata.get(HintKeys.SIDE, "outside")
        hint[HintKeys.SIDE] = side


        if intent.constraints.tabs is not None:
            tabs = intent.constraints.tabs
            hint[HintKeys.TABS] = {
                TabKeys.COUNT: tabs.count,
                TabKeys.HEIGHT: tabs.height_mm,
                TabKeys.WIDTH_MM: tabs.width_mm,
            }

    elif hint_type == FeatureType.POCKET:

        if intent.z_top != 0.0:
            hint[HintKeys.START_DEPTH_MM] = abs(intent.z_top)


        if HintKeys.CORNER_CLEANUP_TOOL_DIAMETER_MM in intent.metadata:
            hint[HintKeys.CORNER_CLEANUP_TOOL_DIAMETER_MM] = intent.metadata[HintKeys.CORNER_CLEANUP_TOOL_DIAMETER_MM]


    return hint


def _generate_corner_cleanup_hint(intent: RemovalIntent, pocket_hint: dict[str, Any]) -> dict[str, Any]:
    corner_tool_diameter = intent.metadata[HintKeys.CORNER_CLEANUP_TOOL_DIAMETER_MM]
    shape = intent.metadata.get(HintKeys.SHAPE, ShapeType.RECT)


    if corner_tool_diameter <= 0.0:
        raise ValueError(
            f"corner_cleanup_tool_diameter_mm must be positive, got: {corner_tool_diameter}"
        )


    if not ShapeType.is_rect(shape):
        raise ValueError(f"Corner cleanup only supported for rectangular pockets, got: {shape}")


    geometry = pocket_hint[HintKeys.GEOMETRY]
    w_mm = geometry[GeometryKeys.W_MM]
    h_mm = geometry[GeometryKeys.H_MM]
    cx, cy = pocket_hint[HintKeys.CENTER_XY_MM]
    depth_mm = pocket_hint[HintKeys.DEPTH_MM]
    start_depth_mm = pocket_hint.get(HintKeys.START_DEPTH_MM, 0.0)


    half_w = w_mm / 2.0
    half_h = h_mm / 2.0

    corners = [
        (cx - half_w, cy - half_h),
        (cx + half_w, cy - half_h),
        (cx + half_w, cy + half_h),
        (cx - half_w, cy + half_h),
    ]

    return {
        HintKeys.ID: f"{pocket_hint[HintKeys.ID]}_corners",
        HintKeys.POCKET_ID: pocket_hint[HintKeys.ID],
        HintKeys.SHAPE: ShapeType.RECT,
        HintKeys.GEOMETRY: geometry,
        HintKeys.CENTER_XY_MM: (cx, cy),
        HintKeys.CORNERS: corners,
        HintKeys.CORNER_TOOL_DIAMETER_MM: corner_tool_diameter,
        HintKeys.DEPTH_MM: depth_mm,
        HintKeys.START_DEPTH_MM: start_depth_mm,
    }


def removal_intents_to_v1_hints(
    intents: list[RemovalIntent],
    kerf_width_mm: float = 3.175,
    min_channel_width_mm: float = 6.0,
) -> dict[str, Any]:
    profiles: list[dict[str, Any]] = []
    pockets: list[dict[str, Any]] = []
    holes: list[dict[str, Any]] = []
    engraves: list[dict[str, Any]] = []
    corner_cleanups: list[dict[str, Any]] = []

    for intent in intents:
        hint = removal_intent_to_v1_hint(intent)
        hint_type = intent.metadata.get(MetadataKeys.HINT_TYPE, FeatureType.POCKET)

        if hint_type == FeatureType.PROFILE:
            profiles.append(hint)
        elif hint_type == FeatureType.POCKET:
            pockets.append(hint)

            if HintKeys.CORNER_CLEANUP_TOOL_DIAMETER_MM in intent.metadata:
                corner_cleanups.append(_generate_corner_cleanup_hint(intent, hint))
        elif hint_type == FeatureType.HOLE:
            holes.append(hint)
        elif hint_type == FeatureType.ENGRAVE:
            engraves.append(hint)
        else:

            pockets.append(hint)

    return {
        HintCollectionKeys.UNITS: "mm",
        HintCollectionKeys.KERF_WIDTH_MM: float(kerf_width_mm),
        HintCollectionKeys.MIN_CHANNEL_WIDTH_MM: float(min_channel_width_mm),
        HintCollectionKeys.PROFILES: profiles,
        HintCollectionKeys.POCKETS: pockets,
        HintCollectionKeys.HOLES: holes,
        HintCollectionKeys.ENGRAVES: engraves,
        HintCollectionKeys.CORNER_CLEANUPS: corner_cleanups,
    }
