"""Geometry utilities for mill_ui.

This module provides unified geometry calculations used across the codebase,
consolidating duplicate implementations into a single source of truth.

Usage:
    from core.geometry import compute_shape_bounds, arc_points
    from ir.removal_intent import Bounds2D

    bounds = compute_shape_bounds(
        shape_type="Rect",
        geometry_data={"w_mm": 100, "h_mm": 50},
        center_xy=(200, 150),
    )

    # Generate points along an arc
    points = arc_points(
        center=(100, 100),
        radius=50,
        start_deg=0,
        end_deg=180,
        segments=20,
    )
"""

from __future__ import annotations

import math
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
            - For Polygon/Polyline: {"points": [[x, y], ...]} (relative to center_xy)
            - For Line: {"start": [x, y], "end": [x, y]} (absolute coordinates)
        center_xy: Center point (x, y) in mm. Defaults to (0, 0) if None.

    Returns:
        Bounds2D with x_min, x_max, y_min, y_max

    Supported shapes:
        - Rect, Rectangle, RoundedRect: Uses w_mm and h_mm centered at center_xy
        - Circle: Uses diameter_mm centered at center_xy
        - Polygon: Uses points array (relative to center_xy)
        - Polyline: Uses points array (relative to center_xy)
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

    # Polygon - compute bounds from points (relative to center_xy)
    if ShapeType.is_polygon(shape_type):
        points = geometry_data.get(GeometryKeys.POINTS, [])
        if points:
            xs = [float(p[0]) + cx for p in points]
            ys = [float(p[1]) + cy for p in points]
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

    # Polyline - compute bounds from points (relative to center_xy)
    if ShapeType.is_polyline(shape_type):
        points = geometry_data.get(GeometryKeys.POINTS, [])
        if points:
            xs = [float(p[0]) + cx for p in points]
            ys = [float(p[1]) + cy for p in points]
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

    # Line - compute bounds from start and end points (relative to center)
    if ShapeType.is_line(shape_type):
        start = geometry_data.get("start", [])
        end = geometry_data.get("end", [])
        if start and end:
            x1, y1 = float(start[0]) + cx, float(start[1]) + cy
            x2, y2 = float(end[0]) + cx, float(end[1]) + cy
            return Bounds2D(
                x_min=min(x1, x2),
                x_max=max(x1, x2),
                y_min=min(y1, y2),
                y_max=max(y1, y2),
            )
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


def arc_points(
    center: tuple[float, float],
    radius: float,
    start_deg: float,
    end_deg: float,
    segments: int = 20,
) -> list[tuple[float, float]]:
    """Generate points along a circular arc.

    Creates a list of points sampling a circular arc from start_deg to end_deg.
    The arc proceeds counter-clockwise when end_deg > start_deg.

    Args:
        center: Center point (x, y) of the arc
        radius: Radius of the arc in mm
        start_deg: Starting angle in degrees (0 = positive X-axis)
        end_deg: Ending angle in degrees
        segments: Number of line segments to approximate the arc

    Returns:
        List of (x, y) points along the arc, including both endpoints.
        Returns segments + 1 points.

    Example:
        # Half circle from right to left (0° to 180°)
        points = arc_points((100, 100), 50, 0, 180, segments=20)
        # Returns 21 points from (150, 100) to (50, 100)
    """
    if segments < 1:
        raise ValueError(f"segments must be >= 1, got {segments}")
    if radius < 0:
        raise ValueError(f"radius must be non-negative, got {radius}")

    cx, cy = center
    points = []

    for i in range(segments + 1):
        t = i / segments
        angle_deg = start_deg + t * (end_deg - start_deg)
        angle_rad = math.radians(angle_deg)
        x = cx + radius * math.cos(angle_rad)
        y = cy + radius * math.sin(angle_rad)
        points.append((x, y))

    return points
