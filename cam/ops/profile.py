# path: skills/mill_ui/cam/ops/profile.py
from skills.mill_ui.cad.shape import Shape2D
from skills.mill_ui.cam.model.setup import Setup
from skills.mill_ui.cam.path.toolpath import move_comment, move_set_rpm, move_set_feed, move_rapid, move_cut, move_retract

def profile_outline(shape: Shape2D, setup: Setup, depth: float, step_down: float = 2.0):
    moves = []
    moves.append(move_comment('profile_outline'))
    moves.append(move_set_rpm(setup.tool.rpm))
    moves.append(move_set_feed(setup.tool.feed_xy))
    z = 0.0
    target = -abs(depth)
    while z > target:
        z = max(z - step_down, target)
        p0 = shape.points[0]
        moves.append(move_rapid(x=p0.x, y=p0.y, z=setup.safe_z))
        moves.append(move_cut(z=z, feed=setup.tool.feed_z))   # plunge at Z feed
        moves.append(move_set_feed(setup.tool.feed_xy))       # restore XY feed
        for p in shape.points[1:]:
            moves.append(move_cut(x=p.x, y=p.y))
        moves.append(move_retract(setup.safe_z))
    return moves
