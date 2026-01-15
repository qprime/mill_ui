
from __future__ import annotations

from typing import Any

from ir.removal_intent import RemovalIntent


def removal_intent_to_v1_hint(intent: RemovalIntent) -> dict[str, Any]:

    hint_type = intent.metadata.get("hint_type", "pocket")
    shape = intent.metadata.get("shape", "Rect")


    depth_mm = intent.depth_mm()


    cx = (intent.bounds.x_min + intent.bounds.x_max) / 2.0
    cy = (intent.bounds.y_min + intent.bounds.y_max) / 2.0


    geometry: dict[str, Any] = {}
    if shape.lower() in ("rect", "rectangle"):
        w_mm = intent.bounds.x_max - intent.bounds.x_min
        h_mm = intent.bounds.y_max - intent.bounds.y_min
        geometry = {"w_mm": w_mm, "h_mm": h_mm}
    elif shape.lower() == "circle":

        diameter_mm = intent.bounds.x_max - intent.bounds.x_min
        geometry = {"diameter_mm": diameter_mm}
    else:

        w_mm = intent.bounds.x_max - intent.bounds.x_min
        h_mm = intent.bounds.y_max - intent.bounds.y_min
        geometry = {"w_mm": w_mm, "h_mm": h_mm}


    hint: dict[str, Any] = {
        "id": intent.metadata.get("original_id", intent.region_id),
        "shape": shape,
        "geometry": geometry,
        "center_xy_mm": (cx, cy),
        "depth_mm": depth_mm,
    }


    if hint_type == "profile":

        side = intent.metadata.get("side", "outside")
        hint["side"] = side


        if intent.constraints.tabs is not None:
            tabs = intent.constraints.tabs
            hint["tabs"] = {
                "count": tabs.count,
                "height": tabs.height_mm,
                "width_mm": tabs.width_mm,
            }

    elif hint_type == "pocket":

        if intent.z_top != 0.0:
            hint["start_depth_mm"] = abs(intent.z_top)


        if "corner_cleanup_tool_diameter_mm" in intent.metadata:
            hint["corner_cleanup_tool_diameter_mm"] = intent.metadata["corner_cleanup_tool_diameter_mm"]


    return hint


def _generate_corner_cleanup_hint(intent: RemovalIntent, pocket_hint: dict[str, Any]) -> dict[str, Any]:
    corner_tool_diameter = intent.metadata["corner_cleanup_tool_diameter_mm"]
    shape = intent.metadata.get("shape", "Rect")


    if corner_tool_diameter <= 0.0:
        raise ValueError(
            f"corner_cleanup_tool_diameter_mm must be positive, got: {corner_tool_diameter}"
        )


    if shape.lower() not in ("rect", "rectangle"):
        raise ValueError(f"Corner cleanup only supported for rectangular pockets, got: {shape}")


    geometry = pocket_hint["geometry"]
    w_mm = geometry["w_mm"]
    h_mm = geometry["h_mm"]
    cx, cy = pocket_hint["center_xy_mm"]
    depth_mm = pocket_hint["depth_mm"]
    start_depth_mm = pocket_hint.get("start_depth_mm", 0.0)


    half_w = w_mm / 2.0
    half_h = h_mm / 2.0

    corners = [
        (cx - half_w, cy - half_h),
        (cx + half_w, cy - half_h),
        (cx + half_w, cy + half_h),
        (cx - half_w, cy + half_h),
    ]

    return {
        "id": f"{pocket_hint['id']}_corners",
        "pocket_id": pocket_hint["id"],
        "shape": "Rect",
        "geometry": geometry,
        "center_xy_mm": (cx, cy),
        "corners": corners,
        "corner_tool_diameter_mm": corner_tool_diameter,
        "depth_mm": depth_mm,
        "start_depth_mm": start_depth_mm,
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
        hint_type = intent.metadata.get("hint_type", "pocket")

        if hint_type == "profile":
            profiles.append(hint)
        elif hint_type == "pocket":
            pockets.append(hint)

            if "corner_cleanup_tool_diameter_mm" in intent.metadata:
                corner_cleanups.append(_generate_corner_cleanup_hint(intent, hint))
        elif hint_type == "hole":
            holes.append(hint)
        elif hint_type == "engrave":
            engraves.append(hint)
        else:

            pockets.append(hint)

    return {
        "units": "mm",
        "kerf_width_mm": float(kerf_width_mm),
        "min_channel_width_mm": float(min_channel_width_mm),
        "profiles": profiles,
        "pockets": pockets,
        "holes": holes,
        "engraves": engraves,
        "corner_cleanups": corner_cleanups,
    }
