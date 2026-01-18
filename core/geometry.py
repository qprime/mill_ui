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
        shape_type: Shape type string (e.g., "Rect", "Circle", "Polygon", "Line", "Polyline")
        geometry_data: Dictionary containing shape-specific dimensions
            - For Rect/RoundedRect: {"w_mm": float, "h_mm": float}
            - For Circle: {"diameter_mm": float}
            - For Polygon/Polyline: {"points": [[x, y], ...]} (absolute coordinates)
            - For Line: {"start": [x, y], "end": [x, y]} (absolute coordinates)
        center_xy: Center point (x, y) in mm. Defaults to (0, 0) if None.
            Note: Polygon, Polyline, and Line use absolute points, so center_xy is ignored.

    Returns:
        Bounds2D with x_min, x_max, y_min, y_max

    Supported shapes:
        - Rect, Rectangle, RoundedRect: Uses w_mm and h_mm centered at center_xy
        - Circle: Uses diameter_mm centered at center_xy
        - Polygon: Uses points array (absolute coordinates, center_xy ignored)
        - Polyline: Uses points array (absolute coordinates, center_xy ignored)
        - Line: Uses start/end points (absolute coordinates, center_xy ignored)

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

    # Polygon - compute bounds from points (ignores center_xy, points are absolute)
    if ShapeType.is_polygon(shape_type):
        points = geometry_data.get(GeometryKeys.POINTS, [])
        if points:
            xs = [float(p[0]) for p in points]
            ys = [float(p[1]) for p in points]
            return Bounds2D(
                x_min=min(xs),
                x_max=max(xs),
                y_min=min(ys),
                y_max=max(ys),
            )
        # Polygon with no points - return 1x1 at center
        return Bounds2D(
            x_min=cx - 0.5,
            x_max=cx + 0.5,
            y_min=cy - 0.5,
            y_max=cy + 0.5,
        )

    # Polyline - compute bounds from points (same as Polygon)
    if ShapeType.is_polyline(shape_type):
        points = geometry_data.get(GeometryKeys.POINTS, [])
        if points:
            xs = [float(p[0]) for p in points]
            ys = [float(p[1]) for p in points]
            return Bounds2D(
                x_min=min(xs),
                x_max=max(xs),
                y_min=min(ys),
                y_max=max(ys),
            )
        # Polyline with no points - return 1x1 at center
        return Bounds2D(
            x_min=cx - 0.5,
            x_max=cx + 0.5,
            y_min=cy - 0.5,
            y_max=cy + 0.5,
        )

    # Line - compute bounds from start and end points
    if ShapeType.is_line(shape_type):
        start = geometry_data.get("start", [])
        end = geometry_data.get("end", [])
        if start and end:
            x1, y1 = float(start[0]), float(start[1])
            x2, y2 = float(end[0]), float(end[1])
            return Bounds2D(
                x_min=min(x1, x2),
                x_max=max(x1, x2),
                y_min=min(y1, y2),
                y_max=max(y1, y2),
            )
        # Line with no points - return 1x1 at center
        return Bounds2D(
            x_min=cx - 0.5,
            x_max=cx + 0.5,
            y_min=cy - 0.5,
            y_max=cy + 0.5,
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
