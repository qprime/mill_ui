from __future__ import annotations

from cam.model.setup import Setup
from cam.moves import Move
from cam.native import core as native_core
from cam.shape import Shape2D


def pocket_raster(
    shape: Shape2D,
    setup: Setup,
    *,
    depth_mm: float,
    stepover: float,
    stepdown: float | None = None,
    strategy: str = "spiral",
) -> list[Move]:
    return native_core.pocket_raster(
        shape,
        setup,
        depth_mm=float(depth_mm),
        stepover_mm=float(stepover),
        stepdown_mm=None if stepdown is None else float(stepdown),
        strategy=strategy,
    )
