from __future__ import annotations

import math
from functools import lru_cache

import numpy as np

__all__ = ["compute_center_z_ball", "dilate_with_additive_kernel", "spherical_cap_kernel"]


@lru_cache(maxsize=32)
def spherical_cap_kernel(radius_mm: float, pixel_pitch_mm: float) -> np.ndarray:
    if radius_mm <= 0.0:
        raise ValueError(f"spherical_cap_kernel: radius_mm must be > 0, got {radius_mm}")
    if pixel_pitch_mm <= 0.0:
        raise ValueError(f"spherical_cap_kernel: pixel_pitch_mm must be > 0, got {pixel_pitch_mm}")
    r_px = math.ceil(radius_mm / pixel_pitch_mm)
    r_px = max(r_px, 1)
    ys, xs = np.mgrid[-r_px : r_px + 1, -r_px : r_px + 1]
    d_mm_sq = (xs * xs + ys * ys).astype(np.float32) * (float(pixel_pitch_mm) ** 2)
    r_mm_sq = float(radius_mm) * float(radius_mm)
    inside = d_mm_sq <= r_mm_sq
    kernel = np.full((2 * r_px + 1, 2 * r_px + 1), -np.inf, dtype=np.float32)
    z_offset = np.sqrt(np.maximum(0.0, r_mm_sq - d_mm_sq, dtype=np.float32))
    kernel[inside] = z_offset[inside]
    return kernel


def dilate_with_additive_kernel(surface: np.ndarray, kernel: np.ndarray) -> np.ndarray:
    if surface.ndim != 2:
        raise ValueError("dilate_with_additive_kernel: surface must be 2D")
    if kernel.ndim != 2 or kernel.shape[0] != kernel.shape[1] or kernel.shape[0] % 2 == 0:
        raise ValueError("dilate_with_additive_kernel: kernel must be square with odd side length")
    h = np.asarray(surface, dtype=np.float32)
    kh, kw = kernel.shape
    r_px = kh // 2
    src = np.pad(h, ((r_px, r_px), (r_px, r_px)), mode="constant", constant_values=-np.inf)
    out = np.full_like(h, -np.inf, dtype=np.float32)
    for dy in range(kh):
        row = src[dy : dy + h.shape[0], :]
        for dx in range(kw):
            kz = kernel[dy, dx]
            if not np.isfinite(kz):
                continue
            candidate = row[:, dx : dx + h.shape[1]] + kz
            np.maximum(out, candidate, out=out)
    return out


def compute_center_z_ball(surface_mm: np.ndarray, pixel_pitch_mm: float, tool_radius_mm: float) -> np.ndarray:
    kernel = spherical_cap_kernel(float(tool_radius_mm), float(pixel_pitch_mm))
    return dilate_with_additive_kernel(surface_mm, kernel)
