
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

    if center_xy is None:
        cx, cy = 0.0, 0.0
    elif isinstance(center_xy, list):
        cx, cy = float(center_xy[0]), float(center_xy[1])
    else:
        cx, cy = float(center_xy[0]), float(center_xy[1])


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


    if ShapeType.is_circle(shape_type):
        diameter = float(geometry_data.get(GeometryKeys.DIAMETER_MM, 0.0))
        radius = diameter / 2.0
        return Bounds2D(
            x_min=cx - radius,
            x_max=cx + radius,
            y_min=cy - radius,
            y_max=cy + radius,
        )


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

        return Bounds2D(
            x_min=cx - 0.5,
            x_max=cx + 0.5,
            y_min=cy - 0.5,
            y_max=cy + 0.5,
        )


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

        return Bounds2D(
            x_min=cx - 0.5,
            x_max=cx + 0.5,
            y_min=cy - 0.5,
            y_max=cy + 0.5,
        )


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
