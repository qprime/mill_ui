
from __future__ import annotations
from cam.shape import Shape2D
from cam.model.setup import Setup
from cam.native import core as native_core


def pocket_raster(
    shape: Shape2D,
    setup: Setup,
    *,
    depth: float,
    stepover: float,
    stepdown: float | None = None,
):
    return native_core.pocket_raster(
        shape,
        setup,
        depth_mm=float(depth),
        stepover_mm=float(stepover),
        stepdown_mm=None if stepdown is None else float(stepdown),
    )
