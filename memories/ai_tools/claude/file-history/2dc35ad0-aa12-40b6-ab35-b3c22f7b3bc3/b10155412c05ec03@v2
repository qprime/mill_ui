"""Adapter: v1 CAM hints → v2 RemovalIntent IR.

Converts legacy operation hints (profile/pocket/hole/engrave) to RemovalIntent records.
One-way adapter (v1 → v2), pure functions with no state changes.

All dimensions in millimeters. Z-axis: positive up, negative down into material.
"""

from __future__ import annotations

from typing import Any

from skills.mill_ui.v2.ir.removal_intent import (
    RemovalIntent,
    Bounds2D,
    Allowance,
    Constraints,
    TabConstraint,
)


def profile_hint_to_removal_intent(
    hint: dict[str, Any],
    sheet_thickness_mm: float,
    region_id_prefix: str = "profile",
) -> RemovalIntent:
    """Convert v1 profile hint to RemovalIntent.

    Args:
        hint: v1 profile hint dict with shape, geometry, depth_mm, center_xy_mm, side, tabs
        sheet_thickness_mm: Sheet thickness for through-cuts
        region_id_prefix: Prefix for generated region_id

    Returns:
        RemovalIntent for this profile operation
    """
    # Extract basic info
    hint_id = hint.get("id", "")
    region_id = f"{region_id_prefix}_{hint_id}" if hint_id else region_id_prefix

    # Extract depth
    depth_mm = float(hint.get("depth_mm", sheet_thickness_mm))

    # Calculate bounds from geometry
    bounds = _geometry_to_bounds(hint.get("shape", ""), hint.get("geometry", {}), hint.get("center_xy_mm"))

    # Extract side (inside/outside/on) for allowance
    side = hint.get("side", "outside").lower()
    allowance = _side_to_allowance(side)

    # Extract tabs if present
    tabs_data = hint.get("tabs")
    constraints = _tabs_to_constraints(tabs_data) if tabs_data else Constraints()

    # Build RemovalIntent
    return RemovalIntent(
        region_id=region_id,
        bounds=bounds,
        z_top=0.0,
        z_bottom=-depth_mm,
        allowance=allowance,
        constraints=constraints,
        metadata={
            "hint_type": "profile",
            "shape": hint.get("shape"),
            "side": side,
            "original_id": hint_id,
        },
    )


def pocket_hint_to_removal_intent(
    hint: dict[str, Any],
    region_id_prefix: str = "pocket",
) -> RemovalIntent:
    """Convert v1 pocket hint to RemovalIntent.

    Args:
        hint: v1 pocket hint dict with shape, geometry, depth_mm, center_xy_mm, start_depth_mm
        region_id_prefix: Prefix for generated region_id

    Returns:
        RemovalIntent for this pocket operation
    """
    # Extract basic info
    hint_id = hint.get("id", "")
    region_id = f"{region_id_prefix}_{hint_id}" if hint_id else region_id_prefix

    # Extract depths
    depth_mm = float(hint.get("depth_mm", 0.0))
    start_depth_mm = float(hint.get("start_depth_mm", 0.0))

    # Calculate bounds from geometry
    bounds = _geometry_to_bounds(hint.get("shape", ""), hint.get("geometry", {}), hint.get("center_xy_mm"))

    # Pockets typically have no special allowance (cut exactly to boundary)
    allowance = Allowance()

    # Build RemovalIntent
    return RemovalIntent(
        region_id=region_id,
        bounds=bounds,
        z_top=-start_depth_mm,  # Start depth (typically 0.0)
        z_bottom=-(start_depth_mm + depth_mm),  # Bottom depth
        allowance=allowance,
        constraints=Constraints(),
        metadata={
            "hint_type": "pocket",
            "shape": hint.get("shape"),
            "original_id": hint_id,
        },
    )


def hole_hint_to_removal_intent(
    hint: dict[str, Any],
    region_id_prefix: str = "hole",
) -> RemovalIntent:
    """Convert v1 hole hint to RemovalIntent.

    Args:
        hint: v1 hole hint dict with shape, geometry, depth_mm, center_xy_mm
        region_id_prefix: Prefix for generated region_id

    Returns:
        RemovalIntent for this hole operation
    """
    # Extract basic info
    hint_id = hint.get("id", "")
    region_id = f"{region_id_prefix}_{hint_id}" if hint_id else region_id_prefix

    # Extract depth
    depth_mm = float(hint.get("depth_mm", 0.0))

    # Calculate bounds from geometry
    bounds = _geometry_to_bounds(hint.get("shape", ""), hint.get("geometry", {}), hint.get("center_xy_mm"))

    # Holes typically have no special allowance
    allowance = Allowance()

    # Build RemovalIntent
    return RemovalIntent(
        region_id=region_id,
        bounds=bounds,
        z_top=0.0,
        z_bottom=-depth_mm,
        allowance=allowance,
        constraints=Constraints(),
        metadata={
            "hint_type": "hole",
            "shape": hint.get("shape"),
            "original_id": hint_id,
        },
    )


def engrave_hint_to_removal_intent(
    hint: dict[str, Any],
    region_id_prefix: str = "engrave",
) -> RemovalIntent:
    """Convert v1 engrave hint to RemovalIntent.

    Args:
        hint: v1 engrave hint dict with shape, geometry, depth_mm, center_xy_mm
        region_id_prefix: Prefix for generated region_id

    Returns:
        RemovalIntent for this engrave operation
    """
    # Extract basic info
    hint_id = hint.get("id", "")
    region_id = f"{region_id_prefix}_{hint_id}" if hint_id else region_id_prefix

    # Extract depth (typically shallow for engraves)
    depth_mm = float(hint.get("depth_mm", 0.0))

    # Calculate bounds from geometry
    bounds = _geometry_to_bounds(hint.get("shape", ""), hint.get("geometry", {}), hint.get("center_xy_mm"))

    # Engraves typically have no special allowance
    allowance = Allowance()

    # Build RemovalIntent
    return RemovalIntent(
        region_id=region_id,
        bounds=bounds,
        z_top=0.0,
        z_bottom=-depth_mm,
        allowance=allowance,
        constraints=Constraints(),
        metadata={
            "hint_type": "engrave",
            "shape": hint.get("shape"),
            "original_id": hint_id,
        },
    )


# Helper functions

def _geometry_to_bounds(shape: str, geometry: dict[str, Any], center_xy: tuple[float, float] | list[float] | None) -> Bounds2D:
    """Calculate 2D bounds from shape geometry and placement."""
    if center_xy is None:
        center_xy = (0.0, 0.0)
    elif isinstance(center_xy, list):
        center_xy = (float(center_xy[0]), float(center_xy[1]))

    cx, cy = float(center_xy[0]), float(center_xy[1])

    shape_lower = shape.lower()

    if shape_lower in ("rect", "rectangle"):
        w = float(geometry.get("w_mm", 0.0))
        h = float(geometry.get("h_mm", 0.0))
        half_w, half_h = w / 2.0, h / 2.0
        return Bounds2D(
            x_min=cx - half_w,
            x_max=cx + half_w,
            y_min=cy - half_h,
            y_max=cy + half_h,
        )

    elif shape_lower == "circle":
        diameter = float(geometry.get("diameter_mm", 0.0))
        radius = diameter / 2.0
        return Bounds2D(
            x_min=cx - radius,
            x_max=cx + radius,
            y_min=cy - radius,
            y_max=cy + radius,
        )

    else:
        # Default: assume 1mm bounding box at center (fallback)
        return Bounds2D(
            x_min=cx - 0.5,
            x_max=cx + 0.5,
            y_min=cy - 0.5,
            y_max=cy + 0.5,
        )


def _side_to_allowance(side: str) -> Allowance:
    """Convert v1 profile side (inside/outside/on) to Allowance."""
    side_lower = side.lower()

    if side_lower == "outside":
        # Outside cut: leave material outside boundary (negative = remove more)
        return Allowance(outside=0.0)
    elif side_lower == "inside":
        # Inside cut: leave material inside boundary
        return Allowance(inside=0.0)
    elif side_lower == "on":
        # On-line cut: cut on the boundary
        return Allowance(on=0.0)
    else:
        # Default to outside
        return Allowance(outside=0.0)


def _tabs_to_constraints(tabs_data: dict[str, Any] | None) -> Constraints:
    """Convert v1 tabs dict to Constraints with TabConstraint."""
    if not tabs_data:
        return Constraints()

    count = int(tabs_data.get("count", 0))
    height_mm = float(tabs_data.get("height", tabs_data.get("height_mm", 3.0)))
    width_mm = float(tabs_data.get("width_mm", tabs_data.get("width", 10.0)))

    tab = TabConstraint(count=count, height_mm=height_mm, width_mm=width_mm)
    return Constraints(tabs=tab)
