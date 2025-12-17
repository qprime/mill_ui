# path: skills/mill_ui/cam/ops/profile.py
from skills.mill_ui.cam.shape import Shape2D
from skills.mill_ui.cam.model.setup import Setup
from skills.mill_ui.cam.native import core as native_core


def profile_outline(shape: Shape2D, setup: Setup, depth: float, step_down: float = 2.0):
    return native_core.profile_outline(
        shape,
        setup,
        depth_mm=float(depth),
        stepdown_mm=float(step_down),
    )
