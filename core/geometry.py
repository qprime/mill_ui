"""Geometry utilities for mill_ui.

This module provides unified geometry calculations used across the codebase,
consolidating duplicate implementations into a single source of truth.

Usage:
    from core.geometry import compute_shape_bounds
    from ir.removal_intent import Bounds2D

    bounds = compute_shape_bounds(
        shape_type="Rect",
        geometry_data={"w_mm": 100, "h_mm": 50},
        center_xy=(200, 150),
    )
"""

from __future__ import annotations

from typing import Any

from ir.removal_intent import Bounds2D
from core.constants import ShapeType, GeometryKeys


def compute_shape_bounds(
    shape_type: str,
    geometry_data: dict[str, Any],
    center_xy: tuple[float, float] | list[float] | None = None,
) -> Bounds2D:
    """Compute bounding box for a shape centered at a given position.

    This is the single source of truth for bounds calculation, replacing
    duplicate implementations in hints_to_removal.py and layout_resolver.py.

    Args:
        shape_type: Shape type string (e.g., "Rect", "Circle", "RoundedRect")
        geometry_data: Dictionary containing shape-specific dimensions
            - For Rect/RoundedRect: {"w_mm": float, "h_mm": float}
            - For Circle: {"diameter_mm": float}
        center_xy: Center point (x, y) in mm. Defaults to (0, 0) if None.

    Returns:
        Bounds2D with x_min, x_max, y_min, y_max

    Supported shapes:
        - Rect, Rectangle, RoundedRect: Uses w_mm and h_mm
        - Circle: Uses diameter_mm

    Unknown shapes return a 1x1 mm box centered at the given point.
    """
    # Normalize center point
    if center_xy is None:
        cx, cy = 0.0, 0.0
    elif isinstance(center_xy, list):
        cx, cy = float(center_xy[0]), float(center_xy[1])
    else:
        cx, cy = float(center_xy[0]), float(center_xy[1])

    # Rectangle types (Rect, Rectangle, RoundedRect)
    if ShapeType.is_rect(shape_type) or shape_type == ShapeType.ROUNDED_RECT:
        w = float(geometry_data.get(GeometryKeys.W_MM, 0.0))
        h = float(geometry_data.get(GeometryKeys.H_MM, 0.0))
        half_w, half_h = w / 2.0, h / 2.0
        return Bounds2D(
            x_min=cx - half_w,
            x_max=cx + half_w,
            y_min=cy - half_h,
            y_max=cy + half_h,
        )

    # Circle
    if ShapeType.is_circle(shape_type):
        diameter = float(geometry_data.get(GeometryKeys.DIAMETER_MM, 0.0))
        radius = diameter / 2.0
        return Bounds2D(
            x_min=cx - radius,
            x_max=cx + radius,
            y_min=cy - radius,
            y_max=cy + radius,
        )

    # Unknown shape: return 1x1 mm box as fallback
    return Bounds2D(
        x_min=cx - 0.5,
        x_max=cx + 0.5,
        y_min=cy - 0.5,
        y_max=cy + 0.5,
    )


def compute_shape_bounds_dict(
    shape_type: str,
    geometry_data: dict[str, Any],
    center_xy: tuple[float, float] | list[float] | None = None,
) -> dict[str, float]:
    """Compute bounding box as a dictionary (for JSON serialization).

    This is a convenience wrapper around compute_shape_bounds() that returns
    a dictionary instead of a Bounds2D object, useful for contexts where
    dict output is preferred (like building island data).

    Args:
        shape_type: Shape type string (e.g., "Rect", "Circle", "RoundedRect")
        geometry_data: Dictionary containing shape-specific dimensions
        center_xy: Center point (x, y) in mm. Defaults to (0, 0) if None.

    Returns:
        Dict with keys: x_min, x_max, y_min, y_max
    """
    bounds = compute_shape_bounds(shape_type, geometry_data, center_xy)
    return {
        GeometryKeys.X_MIN: bounds.x_min,
        GeometryKeys.X_MAX: bounds.x_max,
        GeometryKeys.Y_MIN: bounds.y_min,
        GeometryKeys.Y_MAX: bounds.y_max,
    }
