from __future__ import annotations

import numpy as np

from cam.planner.passes.relief import ToolSpec, compute_barriers, compute_envelope


def _flat_surface(shape: tuple[int, int], z: float) -> np.ndarray:
    return np.full(shape, z, dtype=np.float32)


def _step_surface(shape: tuple[int, int], low: float, high: float) -> np.ndarray:
    arr = np.full(shape, low, dtype=np.float32)
    arr[:, shape[1] // 2 :] = high
    return arr


def test_barrier_flat_surface_is_at_surface_plus_skin():
    surface = _flat_surface((32, 32), z=0.0)
    tools = [ToolSpec(name="d6", diameter_mm=6.0), ToolSpec(name="d3", diameter_mm=3.0)]
    barriers = compute_barriers(surface, tools, pixel_pitch_mm=0.5, skin_mm=0.3)

    for name in ("d3", "d6"):
        np.testing.assert_allclose(barriers[name], 0.3, atol=1e-5)


def test_barrier_coarse_ge_fine_pointwise():
    surface = _step_surface((64, 64), low=-5.0, high=0.0)
    tools = [ToolSpec(name="d6", diameter_mm=6.0), ToolSpec(name="d3", diameter_mm=3.0)]
    barriers = compute_barriers(surface, tools, pixel_pitch_mm=0.5, skin_mm=0.3)

    assert np.all(barriers["d6"] >= barriers["d3"] - 1e-5)


def test_barrier_above_surface_plus_skin_everywhere():
    rng = np.random.default_rng(42)
    surface = rng.uniform(-5.0, 0.0, size=(48, 48)).astype(np.float32)
    tools = [ToolSpec(name="d6", diameter_mm=6.0)]
    barriers = compute_barriers(surface, tools, pixel_pitch_mm=0.5, skin_mm=0.3)

    assert np.all(barriers["d6"] >= surface + 0.3 - 1e-5)


def test_envelope_non_decreasing_vs_surface():
    surface = _step_surface((32, 32), low=-5.0, high=0.0)
    env = compute_envelope(surface, diameter_mm=6.0, pixel_pitch_mm=0.5)

    assert np.all(env >= surface - 1e-5)


def test_barrier_deterministic():
    surface = _step_surface((32, 32), low=-5.0, high=0.0)
    tools = [ToolSpec(name="d6", diameter_mm=6.0), ToolSpec(name="d3", diameter_mm=3.0)]
    b1 = compute_barriers(surface, tools, pixel_pitch_mm=0.5, skin_mm=0.3)
    b2 = compute_barriers(surface, tools, pixel_pitch_mm=0.5, skin_mm=0.3)

    for name in ("d3", "d6"):
        np.testing.assert_array_equal(b1[name], b2[name])
