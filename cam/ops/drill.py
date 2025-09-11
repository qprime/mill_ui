
from skills.mill_ui.cam.model.setup import Setup
from skills.mill_ui.cam.path.toolpath import move_comment, move_set_rpm, move_set_feed, move_rapid, move_cut, move_retract
def drill_peck(points, setup:Setup, depth:float, peck:float=3.0):
    moves=[]; moves.append(move_comment('drill_peck')); moves.append(move_set_rpm(setup.tool.rpm)); moves.append(move_set_feed(setup.tool.feed_z))
    for (x,y) in points:
        z=0.0; moves.append(move_rapid(x=x,y=y,z=setup.safe_z))
        while z>-abs(depth):
            z_next=max(z-peck,-abs(depth))
            moves.append(move_cut(z=z_next))
            moves.append(move_retract(setup.safe_z)); z=z_next
    return moves
