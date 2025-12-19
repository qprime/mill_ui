# path: skills/mill_ui/cam/ops/engrave.py
from cam.model.setup import Setup
from cam.path.toolpath import move_comment, move_set_rpm, move_set_feed, move_rapid, move_cut, move_retract

def engrave_lines(lines, setup: Setup, z: float = -0.3):
    moves = []
    moves.append(move_comment('engrave_lines'))
    moves.append(move_set_rpm(setup.tool.rpm))
    moves.append(move_set_feed(setup.tool.feed_xy))
    for poly in lines:
        if not poly:
            continue
        x0, y0 = poly[0]
        moves.append(move_rapid(x=x0, y=y0, z=setup.safe_z))
        moves.append(move_cut(z=z, feed=setup.tool.feed_z))   # plunge at Z feed
        moves.append(move_set_feed(setup.tool.feed_xy))       # restore XY feed
        for (x, y) in poly[1:]:
            moves.append(move_cut(x=x, y=y))
        moves.append(move_retract(setup.safe_z))
    return moves
