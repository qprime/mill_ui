from cam.model.setup import Setup
from cam.moves import Move
from cam.path.toolpath import move_comment, move_cut, move_rapid, move_retract, move_set_feed, move_set_rpm


def face_zigzag(width: float, height: float, setup: Setup, step: float = 10.0, depth_mm: float = 0.5) -> list[Move]:
    moves: list[Move] = []
    moves.append(move_comment("face_zigzag"))
    moves.append(move_set_rpm(setup.tool.rpm))
    moves.append(move_set_feed(setup.tool.feed_xy))
    y = 0.0
    direction = 1
    while y <= height:
        x0, x1 = (0.0, width) if direction == 1 else (width, 0.0)
        moves.append(move_rapid(x=x0, y=y, z=setup.safe_z))
        moves.append(move_cut(z=-abs(depth_mm), feed=setup.tool.feed_z))
        moves.append(move_set_feed(setup.tool.feed_xy))
        moves.append(move_cut(x=x1, y=y))
        moves.append(move_retract(setup.safe_z))
        y += step
        direction *= -1
    return moves
