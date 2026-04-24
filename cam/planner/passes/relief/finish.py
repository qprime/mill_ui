from __future__ import annotations

import math

import numpy as np

from cam.moves import CutMove, Move, RapidMove, SetFeedMove, SetRpmMove
from cam.planner.planner_input import HeightfieldFeatureInput
from ir.removal_intent import HeightfieldToolAssignment

from ..tools import ToolSelection

_DECIMATE_XY_TOL_MM = 0.02
_DECIMATE_Z_TOL_MM = 0.005


def _sample_safe_surface_nearest(
    safe_surface: np.ndarray,
    xs_mm: np.ndarray,
    ys_mm: np.ndarray,
    x_min: float,
    y_min: float,
    width_mm: float,
    height_mm: float,
) -> np.ndarray:
    h_px, w_px = safe_surface.shape
    u = (xs_mm - x_min) / width_mm
    v = (ys_mm - y_min) / height_mm
    cols = np.clip(np.rint(u * (w_px - 1)).astype(np.int64), 0, w_px - 1)
    rows = np.clip(np.rint((1.0 - v) * (h_px - 1)).astype(np.int64), 0, h_px - 1)
    sampled: np.ndarray = safe_surface[rows, cols].astype(np.float32, copy=False)
    return sampled


def _scanline_bounds(
    angle_rad: float, x_min: float, x_max: float, y_min: float, y_max: float
) -> tuple[float, float, float, float]:
    corners = [
        (x_min, y_min),
        (x_max, y_min),
        (x_max, y_max),
        (x_min, y_max),
    ]
    cos_a = math.cos(angle_rad)
    sin_a = math.sin(angle_rad)
    u_values = [cx * cos_a + cy * sin_a for cx, cy in corners]
    v_values = [-cx * sin_a + cy * cos_a for cx, cy in corners]
    return min(u_values), max(u_values), min(v_values), max(v_values)


def _emit_finish_moves(
    feature: HeightfieldFeatureInput,
    tool: ToolSelection,
    assignment: HeightfieldToolAssignment,
    safe_surface: np.ndarray,
    safe_z: float,
) -> list[Move]:
    if assignment.angle_deg is None:
        raise ValueError(f"Heightfield finish '{feature.id}': angle_deg required")
    if tool.diameter <= 0.0:
        raise ValueError(f"Heightfield finish '{feature.id}': tool diameter must be positive")

    cx, cy = feature.center_xy_mm
    half_w = feature.width_mm * 0.5
    half_h = feature.height_mm * 0.5
    x_min = cx - half_w
    x_max = cx + half_w
    y_min = cy - half_h
    y_max = cy + half_h

    width = x_max - x_min
    height = y_max - y_min

    stepover_mm = assignment.stepover_frac * tool.diameter
    if stepover_mm <= 0.0:
        raise ValueError(f"Heightfield finish '{feature.id}': stepover must be positive, got {stepover_mm}")

    sample_pitch_mm = max(0.1, 0.25 * tool.diameter)

    angle_rad = math.radians(assignment.angle_deg)
    cos_a = math.cos(angle_rad)
    sin_a = math.sin(angle_rad)

    u_min, u_max, v_min, v_max = _scanline_bounds(angle_rad, x_min, x_max, y_min, y_max)
    u_span = u_max - u_min
    v_span = v_max - v_min
    if u_span <= 0.0 or v_span <= 0.0:
        return []

    n_samples = max(2, math.ceil(u_span / sample_pitch_mm) + 1)
    n_lines = max(2, math.ceil(v_span / stepover_mm) + 1)

    moves: list[Move] = []
    moves.append(SetRpmMove(rpm=tool.rpm))
    moves.append(SetFeedMove(feed=tool.feed_xy))
    moves.append(RapidMove(z=safe_z))

    u_values = np.linspace(u_min, u_max, n_samples)
    v_values = np.linspace(v_min, v_max, n_lines)

    for j, v in enumerate(v_values):
        sweep_u = u_values if (j % 2 == 0) else u_values[::-1]
        xs = sweep_u * cos_a - v * sin_a
        ys = sweep_u * sin_a + v * cos_a
        xs_clipped = np.clip(xs, x_min, x_max)
        ys_clipped = np.clip(ys, y_min, y_max)
        zs = _sample_safe_surface_nearest(safe_surface, xs_clipped, ys_clipped, x_min, y_min, width, height)

        moves.append(RapidMove(x=float(xs_clipped[0]), y=float(ys_clipped[0])))
        moves.append(CutMove(z=float(zs[0]), feed=tool.feed_z))

        prev_x = float(xs_clipped[0])
        prev_y = float(ys_clipped[0])
        prev_z = float(zs[0])
        for i in range(1, xs_clipped.size):
            xf = float(xs_clipped[i])
            yf = float(ys_clipped[i])
            zf = float(zs[i])
            last_point = i == xs_clipped.size - 1
            dx = xf - prev_x
            dy = yf - prev_y
            dz = zf - prev_z
            xy_dist = math.hypot(dx, dy)
            if not last_point and xy_dist < _DECIMATE_XY_TOL_MM and abs(dz) < _DECIMATE_Z_TOL_MM:
                continue
            moves.append(CutMove(x=xf, y=yf, z=zf, feed=tool.feed_xy))
            prev_x, prev_y, prev_z = xf, yf, zf
        moves.append(RapidMove(z=safe_z))

    return moves


__all__ = ["_emit_finish_moves"]
