from __future__ import annotations

import math


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


__all__ = [
    "generate_angular_positions",
    "radial_point",
    "rotate_point",
]
