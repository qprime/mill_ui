
from skills.mill_ui.cad.shape import Shape2D
from skills.mill_ui.cam.model.setup import Setup
from skills.mill_ui.cam.ops.pocket import pocket_raster
from skills.mill_ui.cam.ops.profile import profile_outline
def pocket_then_profile(shape:Shape2D, setup:Setup, depth:float, stepover:float):
    moves=[]; moves+=pocket_raster(shape, setup, depth=depth, stepover=stepover); moves+=profile_outline(shape, setup, depth=depth); return moves
