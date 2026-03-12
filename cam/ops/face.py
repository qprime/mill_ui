from cam.model.setup import Setup
from cam.moves import Move
from cam.path.toolpath import move_comment, move_cut, move_dwell, move_rapid, move_retract, move_set_feed, move_set_rpm


def face_zigzag(
    width: float,
    height: float,
    setup: Setup,
    step: float = 10.0,
    depth_mm: float = 0.5,
    direction: str = "x",
    cool_every: int = 0,
    cool_dwell_s: float = 0.0,
) -> list[Move]:
    moves: list[Move] = []
    moves.append(move_comment("face_zigzag"))
    moves.append(move_set_rpm(setup.tool.rpm))
    moves.append(move_set_feed(setup.tool.feed_xy))

    if direction == "y":
        step_limit = width
        row_length = height
    else:
        step_limit = height
        row_length = width

    pos = 0.0
    sign = 1
    row_count = 0
    while pos <= step_limit:
        a0, a1 = (0.0, row_length) if sign == 1 else (row_length, 0.0)

        if direction == "y":
            moves.append(move_rapid(x=pos, y=a0, z=setup.safe_z))
            moves.append(move_cut(z=-abs(depth_mm), feed=setup.tool.feed_z))
            moves.append(move_set_feed(setup.tool.feed_xy))
            moves.append(move_cut(x=pos, y=a1))
        else:
            moves.append(move_rapid(x=a0, y=pos, z=setup.safe_z))
            moves.append(move_cut(z=-abs(depth_mm), feed=setup.tool.feed_z))
            moves.append(move_set_feed(setup.tool.feed_xy))
            moves.append(move_cut(x=a1, y=pos))

        moves.append(move_retract(setup.safe_z))
        row_count += 1
        pos += step
        sign *= -1

        if cool_every > 0 and cool_dwell_s > 0.0 and row_count % cool_every == 0 and pos <= step_limit:
            moves.append(move_dwell(cool_dwell_s))

    return moves
