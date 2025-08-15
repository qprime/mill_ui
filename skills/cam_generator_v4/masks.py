# path: cam_generator/masks.py
# desc: Build XY masks for passes and apply radius-aware erosion
# api: make_mask
# tags: mask,morphology

from __future__ import annotations

from typing import Tuple

import numpy as np

__all__ = ["make_mask"]


def _chessboard_distance(mask: np.ndarray) -> np.ndarray:
    h, w = mask.shape
    inf = 10**9
    d = np.full((h, w), inf, dtype=np.int32)
    d[~mask] = 0
    for y in range(h):
        for x in range(w):
            v = d[y, x]
            if y > 0:
                v = min(v, d[y - 1, x] + 1)
                if x > 0:
                    v = min(v, d[y - 1, x - 1] + 1)
                if x + 1 < w:
                    v = min(v, d[y - 1, x + 1] + 1)
            if x > 0:
                v = min(v, d[y, x - 1] + 1)
            d[y, x] = v
    for y in range(h - 1, -1, -1):
        for x in range(w - 1, -1, -1):
            v = d[y, x]
            if y + 1 < h:
                v = min(v, d[y + 1, x] + 1)
                if x > 0:
                    v = min(v, d[y + 1, x - 1] + 1)
                if x + 1 < w:
                    v = min(v, d[y + 1, x + 1] + 1)
            if x + 1 < w:
                v = min(v, d[y, x + 1] + 1)
            d[y, x] = v
    return d


def make_mask(top: np.ndarray, bot: np.ndarray, pixel_pitch_mm: float, tool_radius_mm: float, epsilon: float = 1e-4) -> np.ndarray:
    base = (top - bot) > epsilon
    r_px = max(0, int(round(tool_radius_mm / pixel_pitch_mm)))
    if r_px <= 0:
        return base
    dist = _chessboard_distance(base)
    return dist > r_px

def rest_mask_ball(heightmap_mm: np.ndarray,
                   pixel_pitch_mm: float,
                   prev_tool_radius_mm: float,
                   this_tool_radius_mm: float,
                   tol_mm: float = 0.01) -> np.ndarray:
    """
    True where the smaller tool (this_tool_radius_mm) can go meaningfully deeper
    than the larger tool (prev_tool_radius_mm) on this heightfield.
    """
    from skills.cam_generator_v4.kernels import compute_center_z_ball  # local import = paste-friendly

    z_prev = compute_center_z_ball(heightmap_mm, pixel_pitch_mm, prev_tool_radius_mm)
    z_this = compute_center_z_ball(heightmap_mm, pixel_pitch_mm, this_tool_radius_mm)

    # If the smaller tool's center surface is lower than the bigger tool's by tol, it can remove stock there.
    return (z_this + float(tol_mm)) < z_prev