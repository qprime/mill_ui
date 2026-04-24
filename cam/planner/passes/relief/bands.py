from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .envelopes import compute_envelope, gray_close


@dataclass(frozen=True)
class ToolSpec:
    name: str
    diameter_mm: float
    kind: str = "flat"


def _sort_fine_to_coarse(tools: list[ToolSpec]) -> list[ToolSpec]:
    return sorted(tools, key=lambda t: (t.diameter_mm, t.kind, t.name))


def compute_barriers(
    surface_mm: np.ndarray,
    tools: list[ToolSpec],
    pixel_pitch_mm: float,
    skin_mm: float = 0.3,
) -> dict[str, np.ndarray]:
    """
    Compute a non-decreasing "barrier" surface per tool, ordered fine→coarse.

    Barrier_i is the lowest Z a tool's center can occupy without gouging material
    a smaller tool is responsible for reaching, or the underlying surface.

    N_0 = S + skin
    N_i = max( close(N_{i-1}, k_i), envelope_i(S), S + skin, N_{i-1} )

    Invariant: N_coarse >= N_fine >= S + skin pointwise.
    """
    surface = surface_mm.astype(np.float32, copy=False)
    tools_f2c = _sort_fine_to_coarse(tools)
    barriers: dict[str, np.ndarray] = {}
    n_prev = surface + float(skin_mm)

    for tool in tools_f2c:
        r_px = max(1, round(0.8 * 0.5 * tool.diameter_mm / max(1e-9, pixel_pitch_mm)))
        k = 2 * r_px + 1
        closed = gray_close(n_prev, k)
        envelope = compute_envelope(surface, tool.diameter_mm, pixel_pitch_mm)
        n = np.maximum.reduce([n_prev, closed, envelope, surface + skin_mm]).astype(np.float32, copy=False)
        barriers[tool.name] = n
        n_prev = n

    return barriers


__all__ = ["ToolSpec", "compute_barriers"]
