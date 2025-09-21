from skills.mill_ui.cam.model.setup import Setup
from skills.mill_ui.cam.native import core as native_core


def drill_peck(points, setup: Setup, depth: float, peck: float = 3.0):
    return native_core.drill_peck(
        list(points),
        setup,
        depth_mm=float(depth),
        peck_mm=float(peck),
    )
