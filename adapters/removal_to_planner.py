from __future__ import annotations

from typing import Any

from cam.planner.planner_input import (
    CornerCleanupInput,
    EdgeFeatureInput,
    EdgeTreatmentInput,
    FeatureInput,
    GeometryInput,
    KeepoutInput,
    PlannerInput,
    TabsInput,
)
from core.constants import (
    FeatureType,
    ShapeType,
)
from core.geometry import extract_shape_geometry
from ir.removal_intent import RemovalIntent


def removal_intent_to_hint(intent: RemovalIntent) -> dict[str, Any]:
    return _intent_to_feature_input(intent).to_dict()


def _validate_corner_cleanup(intent: RemovalIntent) -> tuple[float, str]:
    corner_tool_diameter = intent.corner_cleanup_tool_diameter_mm
    shape = intent.shape or ShapeType.RECT

    if corner_tool_diameter is None or corner_tool_diameter <= 0.0:
        raise ValueError(f"corner_cleanup_tool_diameter_mm must be positive, got: {corner_tool_diameter}")

    if not ShapeType.is_rect(shape):
        raise ValueError(f"Corner cleanup only supported for rectangular pockets, got: {shape}")

    return corner_tool_diameter, shape


def _compute_corners(
    cx: float,
    cy: float,
    w_mm: float,
    h_mm: float,
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
    if hint_type == FeatureType.ENGRAVE:
        return "engraves"
    if hint_type in (FeatureType.BEVEL, FeatureType.CHAMFER):
        return "edge_features"
    return "pockets"


def _intent_to_feature_input(intent: RemovalIntent) -> FeatureInput:
    hint_type = intent.hint_type or FeatureType.POCKET
    shape = intent.shape or ShapeType.RECT
    depth_mm = intent.depth_mm()
    cx, cy = intent.bounds.center

    shape_geom = extract_shape_geometry(shape, intent.bounds, intent.shape_geometry)
    geometry = GeometryInput(shape=shape, geometry=shape_geom)

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

    side = intent.side if hint_type == FeatureType.PROFILE else None
    start_depth_mm = abs(intent.depth_profile.z_top) if intent.depth_profile.z_top != 0.0 else 0.0

    edge_treatment: EdgeTreatmentInput | None = None
    if intent.constraints.edge_treatment is not None:
        edge_treatment = EdgeTreatmentInput.from_edge_treatment(intent.constraints.edge_treatment)

    return FeatureInput(
        id=intent.original_id if intent.original_id is not None else intent.region_id,
        shape=shape,
        geometry=geometry,
        center_xy_mm=(cx, cy),
        depth_mm=depth_mm,
        start_depth_mm=start_depth_mm,
        side=side,
        tabs=tabs,
        keepouts=keepouts,
        corner_cleanup_tool_diameter_mm=intent.corner_cleanup_tool_diameter_mm,
        edge_treatment=edge_treatment,
        feeds_override=intent.feeds_override,
    )


def _generate_corner_cleanup_input(
    intent: RemovalIntent,
    feature: FeatureInput,
) -> CornerCleanupInput:
    corner_tool_diameter, _ = _validate_corner_cleanup(intent)

    cx, cy = feature.center_xy_mm
    corners = _compute_corners(
        cx,
        cy,
        feature.geometry.geometry.w_mm or 0.0,
        feature.geometry.geometry.h_mm or 0.0,
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


def _intent_to_edge_feature_input(intent: RemovalIntent) -> EdgeFeatureInput:
    shape = intent.shape or ShapeType.RECT
    depth_mm = intent.depth_mm()
    cx, cy = intent.bounds.center

    shape_geom = extract_shape_geometry(shape, intent.bounds, intent.shape_geometry)
    geometry = GeometryInput(shape=shape, geometry=shape_geom)
    start_depth_mm = abs(intent.depth_profile.z_top) if intent.depth_profile.z_top != 0.0 else 0.0

    return EdgeFeatureInput(
        id=intent.original_id if intent.original_id is not None else intent.region_id,
        shape=shape,
        geometry=geometry,
        center_xy_mm=(cx, cy),
        depth_mm=depth_mm,
        start_depth_mm=start_depth_mm,
        side=intent.side,
        edge_feature=intent.edge_feature,
    )


def removal_intents_to_planner_input(
    intents: list[RemovalIntent],
    kerf_width_mm: float = 3.175,
    min_channel_width_mm: float = 6.0,
) -> PlannerInput:
    buckets: dict[str, list[FeatureInput]] = {
        "profiles": [],
        "pockets": [],
        "holes": [],
        "engraves": [],
    }
    edge_features: list[EdgeFeatureInput] = []
    corner_cleanups: list[CornerCleanupInput] = []
    all_keepouts: list[KeepoutInput] = []
    seen_keepouts: set[tuple[int, int, int, int]] = set()

    for intent in intents:
        for keepout in intent.constraints.keepouts:
            key = (
                round(keepout.bounds.x_min * 1000),
                round(keepout.bounds.x_max * 1000),
                round(keepout.bounds.y_min * 1000),
                round(keepout.bounds.y_max * 1000),
            )
            if key not in seen_keepouts:
                seen_keepouts.add(key)
                all_keepouts.append(
                    KeepoutInput(
                        x_min=keepout.bounds.x_min,
                        x_max=keepout.bounds.x_max,
                        y_min=keepout.bounds.y_min,
                        y_max=keepout.bounds.y_max,
                        reason=keepout.reason,
                    )
                )

        hint_type = intent.hint_type or FeatureType.POCKET
        side = intent.side or "outside"
        bucket = _classify_feature(hint_type, side)

        if bucket == "edge_features":
            edge_features.append(_intent_to_edge_feature_input(intent))
        else:
            feature = _intent_to_feature_input(intent)
            buckets[bucket].append(feature)

            if bucket == "pockets" and intent.corner_cleanup_tool_diameter_mm is not None:
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
        edge_features=tuple(edge_features),
        keepouts=tuple(all_keepouts),
    )


def removal_intents_to_hints(
    intents: list[RemovalIntent],
    kerf_width_mm: float = 3.175,
    min_channel_width_mm: float = 6.0,
) -> dict[str, Any]:
    planner_input = removal_intents_to_planner_input(
        intents,
        kerf_width_mm=kerf_width_mm,
        min_channel_width_mm=min_channel_width_mm,
    )
    return planner_input.to_hints_dict()
