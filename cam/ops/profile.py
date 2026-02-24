from cam.model.setup import Setup
from cam.moves import Move
from cam.native import core as native_core
from cam.shape import Shape2D


def profile_outline(shape: Shape2D, setup: Setup, depth_mm: float, step_down: float = 2.0) -> list[Move]:
    return native_core.profile_outline(
        shape,
        setup,
        depth_mm=float(depth_mm),
        stepdown_mm=float(step_down),
    )
