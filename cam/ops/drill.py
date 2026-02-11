from cam.model.setup import Setup
from cam.native import core as native_core


def drill_peck(points, setup: Setup, depth_mm: float, peck: float = 3.0):
    return native_core.drill_peck(
        list(points),
        setup,
        depth_mm=float(depth_mm),
        peck_mm=float(peck),
    )
