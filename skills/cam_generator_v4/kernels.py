# skills/cam_generator_v4/kernels.py
# purpose: contact kernel utilities (tool-center Z from heightmap)
# api: compute_center_z_ball
# deps: numpy only

from __future__ import annotations
from typing import Tuple
import math
import numpy as np
from functools import lru_cache


__all__ = ["compute_center_z_ball", "scallop_to_stepover_mm"]

def scallop_to_stepover_mm(tool_radius_mm: float, scallop_mm: float) -> float:
    """Approximate stepover from desired scallop height.
    h ≈ s^2 / (8r)  =>  s ≈ sqrt(8 r h)
    """
    if tool_radius_mm <= 0 or scallop_mm <= 0:
        return 0.0
    return float(math.sqrt(8.0 * tool_radius_mm * scallop_mm))

@lru_cache(maxsize=64)
def _build_spherical_cap_kernel_mm(tool_radius_mm: float, pitch_mm: float) -> Tuple[np.ndarray, int]:
    """Cached spherical-cap kernel. Keyed by (tool_radius_mm, pitch_mm)."""
    if tool_radius_mm <= 0 or pitch_mm <= 0:
        raise ValueError("tool_radius_mm and pitch_mm must be > 0")
    r_px = int(math.ceil(tool_radius_mm / pitch_mm))
    if r_px < 1:
        r_px = 1
    ys, xs = np.mgrid[-r_px:r_px+1, -r_px:r_px+1]
    d2_px = xs*xs + ys*ys
    r2_px = float(r_px * r_px)
    inside = d2_px.astype(np.float32) <= r2_px
    kernel = np.full((2*r_px+1, 2*r_px+1), -np.inf, dtype=np.float32)
    d_mm = np.sqrt(d2_px.astype(np.float32)) * float(pitch_mm)
    r_mm = float(tool_radius_mm)
    z_offset = np.sqrt(np.maximum(0.0, r_mm*r_mm - d_mm*d_mm), dtype=np.float32)
    kernel[inside] = z_offset[inside]
    return kernel, r_px

def compute_center_z_ball(heightmap_mm: np.ndarray, pitch_mm: float, tool_radius_mm: float) -> np.ndarray:
    """Compute tool-center Z map for a ball-nose cutter by grayscale dilation with a spherical-cap kernel.

    Inputs:
      heightmap_mm: 2D float32 array, Z in mm (work coordinates)
      pitch_mm:     mm per pixel
      tool_radius_mm: ball radius in mm

    Output:
      z_center_mm: 2D float32 array (same shape), tool-center Z to reproduce the target without gouge.
    """
    if heightmap_mm.ndim != 2:
        raise ValueError("heightmap_mm must be 2D")
    h = np.asarray(heightmap_mm, dtype=np.float32)
    kernel, r_px = _build_spherical_cap_kernel_mm(tool_radius_mm, pitch_mm)

    # Pad with -inf so max() ignores off-image contributions
    pad = int(r_px)
    src = np.pad(h, ((pad, pad), (pad, pad)), mode="constant", constant_values=-np.inf)

    # Dilation via sliding-window max with additive kernel.
    # We avoid external deps; this is O(r^2 * HW) but fast enough for 100–400mm at typical pitches.
    out = np.full_like(h, -np.inf, dtype=np.float32)
    kh, kw = kernel.shape
    for dy in range(kh):
        ys = dy
        ye = ys + h.shape[0]
        row = src[ys:ye, :]  # view
        for dx in range(kw):
            kz = kernel[dy, dx]
            if np.isneginf(kz):
                continue
            xs = dx
            xe = xs + h.shape[1]
            candidate = row[:, xs:xe] + kz
            # out = maximum(out, candidate)
            mask = candidate > out
            if mask.any():
                out[mask] = candidate[mask]

    # Replace any residual -inf (shouldn't occur) with original heights
    bad = ~np.isfinite(out)
    if bad.any():
        out[bad] = h[bad]
    return out
