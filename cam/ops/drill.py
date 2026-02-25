from collections.abc import Sequence

from cam.model.setup import Setup
from cam.moves import Move
from cam.native import core as native_core


def drill_peck(points: Sequence[tuple[float, float]], setup: Setup, depth_mm: float, peck: float = 3.0) -> list[Move]:
    return native_core.drill_peck(
        list(points),
        setup,
        depth_mm=float(depth_mm),
        peck_mm=float(peck),
    )
