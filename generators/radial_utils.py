from __future__ import annotations

import math
from collections.abc import Sequence

import shapely


def generate_angular_positions(
    rays: int,
    minor_subdivisions: int = 0,
    start_deg: float = 0.0,
    end_deg: float = 360.0,
) -> list[tuple[float, bool]]:
    is_full_circle = abs(end_deg - start_deg) >= 360.0
    total_per_interval = 1 + minor_subdivisions
    total_positions = rays * total_per_interval
    if is_full_circle:
        angle_step = (end_deg - start_deg) / total_positions
    else:
        angle_step = (end_deg - start_deg) / (total_positions - 1) if total_positions > 1 else 0.0

    positions: list[tuple[float, bool]] = []
    for i in range(total_positions):
        angle = start_deg + i * angle_step
        is_major = (i % total_per_interval) == 0
        positions.append((angle, is_major))

    return positions


def radial_point(
    center: tuple[float, float],
    radius: float,
    angle_deg: float,
) -> tuple[float, float]:
    angle_rad = math.radians(angle_deg)
    return (
        center[0] + radius * math.cos(angle_rad),
        center[1] + radius * math.sin(angle_rad),
    )


def rotate_point(
    point: tuple[float, float],
    angle_deg: float,
    center: tuple[float, float] = (0.0, 0.0),
) -> tuple[float, float]:
    angle_rad = math.radians(angle_deg)
    cos_a = math.cos(angle_rad)
    sin_a = math.sin(angle_rad)
    dx = point[0] - center[0]
    dy = point[1] - center[1]
    return (
        center[0] + dx * cos_a - dy * sin_a,
        center[1] + dx * sin_a + dy * cos_a,
    )


def spiral_positions(
    count: int,
    spacing_mm: float,
    angle_deg: float,
) -> list[tuple[tuple[float, float], float]]:
    positions: list[tuple[tuple[float, float], float]] = []
    for i in range(count):
        radius = spacing_mm * math.sqrt(i)
        theta = math.radians(i * angle_deg)
        positions.append(((radius * math.cos(theta), radius * math.sin(theta)), theta))
    return positions


def closest_pair_distance(points: Sequence[tuple[float, float]]) -> float:
    if len(points) < 2:
        return math.inf
    geometries = shapely.points(list(points))
    tree = shapely.STRtree(geometries)
    _, distances = tree.query_nearest(geometries, exclusive=True, return_distance=True)
    return float(distances.min())


__all__ = [
    "closest_pair_distance",
    "generate_angular_positions",
    "radial_point",
    "rotate_point",
    "spiral_positions",
]
