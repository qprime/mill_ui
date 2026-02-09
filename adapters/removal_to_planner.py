
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
from core.geometry import extract_shape_geometry
from cam.planner.planner_input import (
    PlannerInput,
    FeatureInput,
    CornerCleanupInput,
    KeepoutInput,
    TabsInput,
    GeometryInput,
)


def removal_intent_to_hint(intent: RemovalIntent) -> dict[str, Any]:
    hint_type = intent.metadata.get(MetadataKeys.HINT_TYPE, FeatureType.POCKET)
    shape = intent.metadata.get(HintKeys.SHAPE, ShapeType.RECT)
    depth_mm = intent.depth_mm()


    cx, cy = intent.bounds.center


    geometry = extract_shape_geometry(shape, intent.bounds, intent.metadata)


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
                TabKeys.HEIGHT_MM: tabs.height_mm,
                TabKeys.WIDTH_MM: tabs.width_mm,
            }

    elif hint_type == FeatureType.POCKET:

        if intent.depth_profile.z_top != 0.0:
            hint[HintKeys.START_DEPTH_MM] = abs(intent.depth_profile.z_top)


        if HintKeys.CORNER_CLEANUP_TOOL_DIAMETER_MM in intent.metadata:
            hint[HintKeys.CORNER_CLEANUP_TOOL_DIAMETER_MM] = intent.metadata[HintKeys.CORNER_CLEANUP_TOOL_DIAMETER_MM]

    if intent.constraints.keepouts:
        hint[HintKeys.KEEPOUTS] = [
            {
                "x_min": keepout.bounds.x_min,
                "x_max": keepout.bounds.x_max,
                "y_min": keepout.bounds.y_min,
                "y_max": keepout.bounds.y_max,
                "reason": keepout.reason,
            }
            for keepout in intent.constraints.keepouts
        ]

    return hint


def _validate_corner_cleanup(intent: RemovalIntent) -> tuple[float, str]:
    corner_tool_diameter = intent.metadata[HintKeys.CORNER_CLEANUP_TOOL_DIAMETER_MM]
    shape = intent.metadata.get(HintKeys.SHAPE, ShapeType.RECT)

    if corner_tool_diameter <= 0.0:
        raise ValueError(
            f"corner_cleanup_tool_diameter_mm must be positive, got: {corner_tool_diameter}"
        )

    if not ShapeType.is_rect(shape):
        raise ValueError(f"Corner cleanup only supported for rectangular pockets, got: {shape}")

    return corner_tool_diameter, shape


def _compute_corners(
    cx: float, cy: float, w_mm: float, h_mm: float,
) -> tuple[tuple[float, float], ...]:
    half_w = w_mm / 2.0
    half_h = h_mm / 2.0
    return (
        (cx - half_w, cy - half_h),
        (cx + half_w, cy - half_h),
        (cx + half_w, cy + half_h),
        (cx - half_w, cy + half_h),
    )


def _classify_feature(hint_type: str, side: str | None) -> str:
    if hint_type == FeatureType.PROFILE:
        return "profiles"
    if hint_type == FeatureType.POCKET:
        return "pockets"
    if hint_type == FeatureType.HOLE:
        return "holes"
    if hint_type in (FeatureType.ENGRAVE, FeatureType.WAVE):
        return "engraves"
    if hint_type == FeatureType.BEVEL:
        return "pockets"
    if hint_type == FeatureType.CHAMFER:
        if side in ("inside", "outside"):
            return "profiles"
        return "engraves"
    return "pockets"


def _generate_corner_cleanup_hint(intent: RemovalIntent, pocket_hint: dict[str, Any]) -> dict[str, Any]:
    corner_tool_diameter, _ = _validate_corner_cleanup(intent)

    geometry = pocket_hint[HintKeys.GEOMETRY]
    cx, cy = pocket_hint[HintKeys.CENTER_XY_MM]
    corners = _compute_corners(
        cx, cy, geometry[GeometryKeys.W_MM], geometry[GeometryKeys.H_MM],
    )

    return {
        HintKeys.ID: f"{pocket_hint[HintKeys.ID]}_corners",
        HintKeys.POCKET_ID: pocket_hint[HintKeys.ID],
        HintKeys.SHAPE: ShapeType.RECT,
        HintKeys.GEOMETRY: geometry,
        HintKeys.CENTER_XY_MM: (cx, cy),
        HintKeys.CORNERS: list(corners),
        HintKeys.CORNER_TOOL_DIAMETER_MM: corner_tool_diameter,
        HintKeys.DEPTH_MM: pocket_hint[HintKeys.DEPTH_MM],
        HintKeys.START_DEPTH_MM: pocket_hint.get(HintKeys.START_DEPTH_MM, 0.0),
    }


def removal_intents_to_hints(
    intents: list[RemovalIntent],
    kerf_width_mm: float = 3.175,
    min_channel_width_mm: float = 6.0,
) -> dict[str, Any]:
    buckets: dict[str, list[dict[str, Any]]] = {
        "profiles": [], "pockets": [], "holes": [], "engraves": [],
    }
    corner_cleanups: list[dict[str, Any]] = []
    all_keepouts: list[dict[str, Any]] = []
    seen_keepouts: set[tuple[float, float, float, float]] = set()

    for intent in intents:
        for keepout in intent.constraints.keepouts:
            key = (keepout.bounds.x_min, keepout.bounds.x_max,
                   keepout.bounds.y_min, keepout.bounds.y_max)
            if key not in seen_keepouts:
                seen_keepouts.add(key)
                all_keepouts.append({
                    "x_min": keepout.bounds.x_min,
                    "x_max": keepout.bounds.x_max,
                    "y_min": keepout.bounds.y_min,
                    "y_max": keepout.bounds.y_max,
                    "reason": keepout.reason,
                })

        hint = removal_intent_to_hint(intent)
        hint_type = intent.metadata.get(MetadataKeys.HINT_TYPE, FeatureType.POCKET)
        side = intent.metadata.get(HintKeys.SIDE, "outside")
        bucket = _classify_feature(hint_type, side)
        buckets[bucket].append(hint)

        if bucket == "pockets" and HintKeys.CORNER_CLEANUP_TOOL_DIAMETER_MM in intent.metadata:
            corner_cleanups.append(_generate_corner_cleanup_hint(intent, hint))

    return {
        HintCollectionKeys.UNITS: "mm",
        HintCollectionKeys.KERF_WIDTH_MM: float(kerf_width_mm),
        HintCollectionKeys.MIN_CHANNEL_WIDTH_MM: float(min_channel_width_mm),
        HintCollectionKeys.PROFILES: buckets["profiles"],
        HintCollectionKeys.POCKETS: buckets["pockets"],
        HintCollectionKeys.HOLES: buckets["holes"],
        HintCollectionKeys.ENGRAVES: buckets["engraves"],
        HintCollectionKeys.CORNER_CLEANUPS: corner_cleanups,
        HintCollectionKeys.KEEPOUTS: all_keepouts,
    }


def _intent_to_feature_input(intent: RemovalIntent) -> FeatureInput:
    hint_type = intent.metadata.get(MetadataKeys.HINT_TYPE, FeatureType.POCKET)
    shape = intent.metadata.get(HintKeys.SHAPE, ShapeType.RECT)
    depth_mm = intent.depth_mm()
    cx, cy = intent.bounds.center

    geometry_dict = extract_shape_geometry(shape, intent.bounds, intent.metadata)
    geometry = GeometryInput(shape=shape, data=geometry_dict)

    tabs: TabsInput | None = None
    if intent.constraints.tabs is not None:
        t = intent.constraints.tabs
        tabs = TabsInput(count=t.count, height_mm=t.height_mm, width_mm=t.width_mm)

    keepouts = tuple(
        KeepoutInput(
            x_min=k.bounds.x_min,
            x_max=k.bounds.x_max,
            y_min=k.bounds.y_min,
            y_max=k.bounds.y_max,
            reason=k.reason,
        )
        for k in intent.constraints.keepouts
    )

    side = intent.metadata.get(HintKeys.SIDE) if hint_type == FeatureType.PROFILE else None
    start_depth_mm = abs(intent.depth_profile.z_top) if intent.depth_profile.z_top != 0.0 else 0.0
    corner_cleanup_diameter = intent.metadata.get(HintKeys.CORNER_CLEANUP_TOOL_DIAMETER_MM)

    return FeatureInput(
        id=intent.metadata.get(MetadataKeys.ORIGINAL_ID, intent.region_id),
        shape=shape,
        geometry=geometry,
        center_xy_mm=(cx, cy),
        depth_mm=depth_mm,
        start_depth_mm=start_depth_mm,
        side=side,
        tabs=tabs,
        keepouts=keepouts,
        corner_cleanup_tool_diameter_mm=corner_cleanup_diameter,
        metadata={},
    )


def _generate_corner_cleanup_input(
    intent: RemovalIntent,
    feature: FeatureInput,
) -> CornerCleanupInput:
    corner_tool_diameter, _ = _validate_corner_cleanup(intent)

    cx, cy = feature.center_xy_mm
    corners = _compute_corners(
        cx, cy,
        feature.geometry.data.get(GeometryKeys.W_MM, 0.0),
        feature.geometry.data.get(GeometryKeys.H_MM, 0.0),
    )

    return CornerCleanupInput(
        id=f"{feature.id}_corners",
        pocket_id=feature.id,
        shape=ShapeType.RECT,
        geometry=feature.geometry,
        center_xy_mm=(cx, cy),
        corners=corners,
        corner_tool_diameter_mm=corner_tool_diameter,
        depth_mm=feature.depth_mm,
        start_depth_mm=feature.start_depth_mm,
    )


def removal_intents_to_planner_input(
    intents: list[RemovalIntent],
    kerf_width_mm: float = 3.175,
    min_channel_width_mm: float = 6.0,
) -> PlannerInput:
    buckets: dict[str, list[FeatureInput]] = {
        "profiles": [], "pockets": [], "holes": [], "engraves": [],
    }
    corner_cleanups: list[CornerCleanupInput] = []
    all_keepouts: list[KeepoutInput] = []
    seen_keepouts: set[tuple[float, float, float, float]] = set()

    for intent in intents:
        for keepout in intent.constraints.keepouts:
            key = (keepout.bounds.x_min, keepout.bounds.x_max,
                   keepout.bounds.y_min, keepout.bounds.y_max)
            if key not in seen_keepouts:
                seen_keepouts.add(key)
                all_keepouts.append(KeepoutInput(
                    x_min=keepout.bounds.x_min,
                    x_max=keepout.bounds.x_max,
                    y_min=keepout.bounds.y_min,
                    y_max=keepout.bounds.y_max,
                    reason=keepout.reason,
                ))

        feature = _intent_to_feature_input(intent)
        hint_type = intent.metadata.get(MetadataKeys.HINT_TYPE, FeatureType.POCKET)
        side = intent.metadata.get(HintKeys.SIDE, "outside")
        bucket = _classify_feature(hint_type, side)
        buckets[bucket].append(feature)

        if bucket == "pockets" and HintKeys.CORNER_CLEANUP_TOOL_DIAMETER_MM in intent.metadata:
            corner_cleanups.append(_generate_corner_cleanup_input(intent, feature))

    return PlannerInput(
        units="mm",
        kerf_width_mm=float(kerf_width_mm),
        min_channel_width_mm=float(min_channel_width_mm),
        profiles=tuple(buckets["profiles"]),
        pockets=tuple(buckets["pockets"]),
        holes=tuple(buckets["holes"]),
        engraves=tuple(buckets["engraves"]),
        corner_cleanups=tuple(corner_cleanups),
        keepouts=tuple(all_keepouts),
    )
