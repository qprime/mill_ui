"""Adapter: RemovalIntent IR → v1 planner hints.

Reverse adapter enabling v1 planners to consume RemovalIntent IR.
Used for equivalence validation (v2 path should produce identical G-code to v1 path).

All dimensions in millimeters. Z-axis: positive up, negative down into material.
"""

from __future__ import annotations

from typing import Any

from ir.removal_intent import RemovalIntent


def removal_intent_to_v1_hint(intent: RemovalIntent) -> dict[str, Any]:
    """Convert single RemovalIntent to v1 hint format.

    Args:
        intent: RemovalIntent to convert

    Returns:
        v1 hint dict compatible with build_cam_hints() output format
    """
    # Extract metadata to determine hint type
    hint_type = intent.metadata.get("hint_type", "pocket")
    shape = intent.metadata.get("shape", "Rect")

    # Calculate depth from z_top/z_bottom
    depth_mm = intent.depth_mm()

    # Calculate center from bounds
    cx = (intent.bounds.x_min + intent.bounds.x_max) / 2.0
    cy = (intent.bounds.y_min + intent.bounds.y_max) / 2.0

    # Build geometry dict based on shape
    geometry: dict[str, Any] = {}
    if shape.lower() in ("rect", "rectangle"):
        w_mm = intent.bounds.x_max - intent.bounds.x_min
        h_mm = intent.bounds.y_max - intent.bounds.y_min
        geometry = {"w_mm": w_mm, "h_mm": h_mm}
    elif shape.lower() == "circle":
        # Calculate diameter from bounds (assumes square bounds for circle)
        diameter_mm = intent.bounds.x_max - intent.bounds.x_min
        geometry = {"diameter_mm": diameter_mm}
    else:
        # Default to rect geometry for unknown shapes
        w_mm = intent.bounds.x_max - intent.bounds.x_min
        h_mm = intent.bounds.y_max - intent.bounds.y_min
        geometry = {"w_mm": w_mm, "h_mm": h_mm}

    # Build base hint record
    hint: dict[str, Any] = {
        "id": intent.metadata.get("original_id", intent.region_id),
        "shape": shape,
        "geometry": geometry,
        "center_xy_mm": (cx, cy),
        "depth_mm": depth_mm,
    }

    # Add hint-type-specific fields
    if hint_type == "profile":
        # Profile-specific: side, tabs
        side = intent.metadata.get("side", "outside")
        hint["side"] = side

        # Add tabs if present
        if intent.constraints.tabs is not None:
            tabs = intent.constraints.tabs
            hint["tabs"] = {
                "count": tabs.count,
                "height": tabs.height_mm,
                "width_mm": tabs.width_mm,
            }

    elif hint_type == "pocket":
        # Pocket-specific: start_depth_mm if z_top != 0
        if intent.z_top != 0.0:
            hint["start_depth_mm"] = abs(intent.z_top)

    # hole and engrave types have no special fields beyond base hint

    return hint


def removal_intents_to_v1_hints(
    intents: list[RemovalIntent],
    kerf_width_mm: float = 3.175,
    min_channel_width_mm: float = 6.0,
) -> dict[str, Any]:
    """Convert list of RemovalIntent to v1 hints structure.

    Args:
        intents: List of RemovalIntent to convert
        kerf_width_mm: Kerf width for profiles (default 3.175mm = 1/8")
        min_channel_width_mm: Minimum channel width (default 6mm)

    Returns:
        v1 hints dict compatible with plan_passes() input:
        {
            "units": "mm",
            "kerf_width_mm": float,
            "min_channel_width_mm": float,
            "profiles": [...],
            "pockets": [...],
            "holes": [...],
            "engraves": [...]
        }
    """
    profiles: list[dict[str, Any]] = []
    pockets: list[dict[str, Any]] = []
    holes: list[dict[str, Any]] = []
    engraves: list[dict[str, Any]] = []

    for intent in intents:
        hint = removal_intent_to_v1_hint(intent)
        hint_type = intent.metadata.get("hint_type", "pocket")

        if hint_type == "profile":
            profiles.append(hint)
        elif hint_type == "pocket":
            pockets.append(hint)
        elif hint_type == "hole":
            holes.append(hint)
        elif hint_type == "engrave":
            engraves.append(hint)
        else:
            # Default unknown types to pockets
            pockets.append(hint)

    return {
        "units": "mm",
        "kerf_width_mm": float(kerf_width_mm),
        "min_channel_width_mm": float(min_channel_width_mm),
        "profiles": profiles,
        "pockets": pockets,
        "holes": holes,
        "engraves": engraves,
    }
