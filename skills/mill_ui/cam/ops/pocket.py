# path: skills/mill_ui/cam/ops/pocket.py
from skills.mill_ui.cad.shape import Shape2D
from skills.mill_ui.cam.model.setup import Setup
from skills.mill_ui.cam.path.toolpath import move_comment, move_set_rpm, move_set_feed, move_rapid, move_cut, move_retract

def pocket_raster(shape: Shape2D, setup: Setup, depth: float, stepover: float):
    b = shape.bounds()
    moves = []
    moves.append(move_comment('pocket_raster'))
    moves.append(move_set_rpm(setup.tool.rpm))
    moves.append(move_set_feed(setup.tool.feed_xy))
    y = b.miny
    direction = 1
    z = -abs(depth)
    while y <= b.maxy:
        x_start = b.minx if direction == 1 else b.maxx
        x_end   = b.maxx if direction == 1 else b.minx
        moves.append(move_rapid(x=x_start, y=y, z=setup.safe_z))
        moves.append(move_cut(z=z, feed=setup.tool.feed_z))   # plunge at Z feed
        moves.append(move_set_feed(setup.tool.feed_xy))       # restore XY feed
        moves.append(move_cut(x=x_end, y=y))
        moves.append(move_retract(setup.safe_z))
        y += stepover
        direction *= -1
    return moves
