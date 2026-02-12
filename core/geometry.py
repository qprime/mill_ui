
from __future__ import annotations

import math
from typing import Any, TYPE_CHECKING

from ir.removal_intent import Bounds2D
from core.constants import ShapeType, GeometryKeys

if TYPE_CHECKING:
    from domains import Domain


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


def calculate_angled_depth(width: float, angle_deg: float, fallback: float = 0.0) -> float:
    if 0.0 < angle_deg < 90.0:
        return width * math.tan(math.radians(angle_deg))
    return fallback if fallback > 0.0 else width


def bounds_overlap(a: Bounds2D, b: Bounds2D, epsilon: float = 0.0) -> bool:
    x_overlap = not (a.x_max <= b.x_min + epsilon or b.x_max <= a.x_min + epsilon)
    y_overlap = not (a.y_max <= b.y_min + epsilon or b.y_max <= a.y_min + epsilon)
    return x_overlap and y_overlap


def clip_line_to_domain(
    line_start: tuple[float, float],
    line_end: tuple[float, float],
    domain: Domain,
) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    from shapely.geometry import LineString

    line = LineString([line_start, line_end])
    polygon = domain.polygon

    intersection = line.intersection(polygon)

    if intersection.is_empty:
        return []

    segments = []

    if intersection.geom_type == "LineString":
        coords = list(intersection.coords)
        if len(coords) >= 2:
            segments.append(
                ((coords[0][0], coords[0][1]), (coords[-1][0], coords[-1][1]))
            )
    elif intersection.geom_type == "MultiLineString":
        for geom in intersection.geoms:
            coords = list(geom.coords)
            if len(coords) >= 2:
                segments.append(
                    ((coords[0][0], coords[0][1]), (coords[-1][0], coords[-1][1]))
                )

    return segments


def extract_shape_geometry(
    shape: str,
    bounds: Bounds2D,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    geometry: dict[str, Any] = {}

    if ShapeType.is_rect(shape):
        geometry = {
            GeometryKeys.W_MM: bounds.width,
            GeometryKeys.H_MM: bounds.height,
        }
    elif ShapeType.is_circle(shape):
        if GeometryKeys.DIAMETER_MM in metadata:
            diameter_mm = metadata[GeometryKeys.DIAMETER_MM]
        else:
            diameter_mm = bounds.width
        geometry = {GeometryKeys.DIAMETER_MM: diameter_mm}
    elif ShapeType.is_polygon(shape):
        if GeometryKeys.POINTS in metadata:
            geometry = {GeometryKeys.POINTS: metadata[GeometryKeys.POINTS]}
        else:
            geometry = {
                GeometryKeys.W_MM: bounds.width,
                GeometryKeys.H_MM: bounds.height,
            }
    elif shape == ShapeType.ROUNDED_RECT:
        geometry = {
            GeometryKeys.W_MM: bounds.width,
            GeometryKeys.H_MM: bounds.height,
        }
        if GeometryKeys.RADIUS_MM in metadata:
            geometry[GeometryKeys.RADIUS_MM] = metadata[GeometryKeys.RADIUS_MM]
        for key in (GeometryKeys.RADIUS_TL_MM, GeometryKeys.RADIUS_TR_MM,
                    GeometryKeys.RADIUS_BR_MM, GeometryKeys.RADIUS_BL_MM):
            if key in metadata:
                geometry[key] = metadata[key]
    elif ShapeType.is_polyline(shape):
        if GeometryKeys.POINTS in metadata:
            geometry = {GeometryKeys.POINTS: metadata[GeometryKeys.POINTS]}
        else:
            geometry = {
                GeometryKeys.W_MM: bounds.width,
                GeometryKeys.H_MM: bounds.height,
            }
    else:
        geometry = {
            GeometryKeys.W_MM: bounds.width,
            GeometryKeys.H_MM: bounds.height,
        }

    return geometry


def extract_circle_diameter(
    shape: str,
    geometry: dict[str, Any],
) -> float | None:
    if ShapeType.is_circle(shape) and GeometryKeys.DIAMETER_MM in geometry:
        return float(geometry[GeometryKeys.DIAMETER_MM])
    return None


def extract_polygon_points(
    shape: str,
    geometry: dict[str, Any],
) -> list[list[float]] | None:
    if (ShapeType.is_polygon(shape) or ShapeType.is_polyline(shape)) and GeometryKeys.POINTS in geometry:
        return geometry[GeometryKeys.POINTS]
    return None
