# path: skills/mill_ui/cam/ops/pocket.py
from __future__ import annotations
from skills.mill_ui.cam.shape import Shape2D
from skills.mill_ui.cam.model.setup import Setup
from skills.mill_ui.cam.native import core as native_core


def pocket_raster(
    shape: Shape2D,
    setup: Setup,
    *,
    depth: float,
    stepover: float,
    stepdown: float | None = None,
):
    """Raster pocket generation delegated to the native core."""
    return native_core.pocket_raster(
        shape,
        setup,
        depth_mm=float(depth),
        stepover_mm=float(stepover),
        stepdown_mm=None if stepdown is None else float(stepdown),
    )
