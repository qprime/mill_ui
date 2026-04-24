from __future__ import annotations

import math

import numpy as np
import pytest

from cam.planner.passes.relief.kernels import (
    compute_center_z_ball,
    dilate_with_additive_kernel,
    spherical_cap_kernel,
)


def test_spherical_cap_kernel_values_match_closed_form():
    radius_mm = 3.0
    pitch_mm = 0.5
    kernel = spherical_cap_kernel(radius_mm, pitch_mm)
    r_px = kernel.shape[0] // 2
    for i in range(kernel.shape[0]):
        for j in range(kernel.shape[1]):
            dx_mm = (j - r_px) * pitch_mm
            dy_mm = (i - r_px) * pitch_mm
            d2 = dx_mm * dx_mm + dy_mm * dy_mm
            if d2 <= radius_mm * radius_mm:
                expected = math.sqrt(radius_mm * radius_mm - d2)
                assert kernel[i, j] == pytest.approx(expected, abs=1e-5)
            else:
                assert kernel[i, j] == -np.inf


def test_spherical_cap_kernel_center_equals_radius():
    kernel = spherical_cap_kernel(2.5, 0.25)
    r_px = kernel.shape[0] // 2
    assert kernel[r_px, r_px] == pytest.approx(2.5, abs=1e-5)


def test_spherical_cap_kernel_outside_disk_is_neg_inf():
    kernel = spherical_cap_kernel(1.0, 0.5)
    corner = kernel[0, 0]
    assert corner == -np.inf


def test_spherical_cap_kernel_is_cached():
    k1 = spherical_cap_kernel(3.0, 0.5)
    k2 = spherical_cap_kernel(3.0, 0.5)
    assert k1 is k2


def test_spherical_cap_kernel_rejects_nonpositive():
    with pytest.raises(ValueError, match="radius_mm"):
        spherical_cap_kernel(0.0, 0.5)
    with pytest.raises(ValueError, match="pixel_pitch_mm"):
        spherical_cap_kernel(1.0, 0.0)


def test_dilation_of_flat_surface_equals_surface_plus_radius():
    radius_mm = 2.0
    pitch_mm = 0.5
    flat = np.full((12, 12), 5.0, dtype=np.float32)
    kernel = spherical_cap_kernel(radius_mm, pitch_mm)
    out = dilate_with_additive_kernel(flat, kernel)
    r_px = kernel.shape[0] // 2
    interior = out[r_px:-r_px, r_px:-r_px]
    assert np.allclose(interior, 5.0 + radius_mm, atol=1e-4)


def test_compute_center_z_ball_never_gouges_random_surface():
    rng = np.random.default_rng(0)
    surface = rng.uniform(-4.0, 0.0, size=(24, 24)).astype(np.float32)
    radius_mm = 1.5
    pitch_mm = 0.5
    center_z = compute_center_z_ball(surface, pitch_mm, radius_mm)
    kernel = spherical_cap_kernel(radius_mm, pitch_mm)
    r_px = kernel.shape[0] // 2
    for i in range(r_px, surface.shape[0] - r_px):
        for j in range(r_px, surface.shape[1] - r_px):
            z_center = center_z[i, j]
            for di in range(-r_px, r_px + 1):
                for dj in range(-r_px, r_px + 1):
                    kz = kernel[r_px + di, r_px + dj]
                    if not np.isfinite(kz):
                        continue
                    assert z_center + 1e-4 >= surface[i + di, j + dj] + kz


def test_dilation_rejects_nonsquare_kernel():
    flat = np.zeros((5, 5), dtype=np.float32)
    bad = np.zeros((3, 5), dtype=np.float32)
    with pytest.raises(ValueError, match="square"):
        dilate_with_additive_kernel(flat, bad)


def test_dilation_rejects_even_kernel():
    flat = np.zeros((5, 5), dtype=np.float32)
    bad = np.zeros((4, 4), dtype=np.float32)
    with pytest.raises(ValueError, match="odd"):
        dilate_with_additive_kernel(flat, bad)
