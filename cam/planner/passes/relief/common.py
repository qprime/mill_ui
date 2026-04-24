from __future__ import annotations

import numpy as np

from generators.area.heightfield_loader import load_heightfield


def load_surface(
    image_path: str,
    width_mm: float,
    height_mm: float,
    depth_mm: float,
    z_top: float,
    white_is_high: bool,
) -> tuple[np.ndarray, float]:
    """
    Returns (surface_z_mm, pixel_pitch_mm).

    surface_z_mm[row, col] is absolute Z of the surface at pixel (row, col) in sheet coords.
    White (1.0) with white_is_high=True means "keep material" → z = z_top.
    Black (0.0) means "carve to depth" → z = z_top - depth_mm.
    """
    img = load_heightfield(image_path)
    heights = img if white_is_high else (1.0 - img)
    surface_z = z_top - depth_mm * (1.0 - heights)
    h_px, w_px = img.shape
    pitch_w = width_mm / w_px
    pitch_h = height_mm / h_px
    pixel_pitch_mm = 0.5 * (pitch_w + pitch_h)
    return surface_z.astype(np.float32, copy=False), float(pixel_pitch_mm)


def xy_to_pixel(
    x_mm: float,
    y_mm: float,
    x_min: float,
    y_min: float,
    width_mm: float,
    height_mm: float,
    w_px: int,
    h_px: int,
) -> tuple[int, int]:
    """Return (row, col) into the pixel grid. Image row 0 is top-edge (y_max)."""
    u = (x_mm - x_min) / width_mm
    v = (y_mm - y_min) / height_mm
    col = min(max(round(u * (w_px - 1)), 0), w_px - 1)
    row = min(max(round((1.0 - v) * (h_px - 1)), 0), h_px - 1)
    return row, col


def sample_barrier_at(
    barrier: np.ndarray,
    x_mm: float,
    y_mm: float,
    x_min: float,
    y_min: float,
    width_mm: float,
    height_mm: float,
) -> float:
    h_px, w_px = barrier.shape
    row, col = xy_to_pixel(x_mm, y_mm, x_min, y_min, width_mm, height_mm, w_px, h_px)
    return float(barrier[row, col])


__all__ = ["load_surface", "sample_barrier_at", "xy_to_pixel"]
