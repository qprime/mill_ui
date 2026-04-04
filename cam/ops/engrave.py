from math import sqrt

from cam.model.setup import Setup
from cam.moves import Move
from cam.path.toolpath import move_comment, move_cut, move_rapid, move_retract, move_set_feed, move_set_rpm


def engrave_lines(lines: list[list[tuple[float, float]]], setup: Setup, z: float = -0.3) -> list[Move]:
    moves: list[Move] = []
    moves.append(move_comment("engrave_lines"))
    moves.append(move_set_rpm(setup.tool.rpm))
    moves.append(move_set_feed(setup.tool.feed_xy))
    for poly in lines:
        if not poly:
            continue
        x0, y0 = poly[0]
        moves.append(move_rapid(x=x0, y=y0, z=setup.safe_z))
        moves.append(move_cut(z=z, feed=setup.tool.feed_z))
        moves.append(move_set_feed(setup.tool.feed_xy))
        for x, y in poly[1:]:
            moves.append(move_cut(x=x, y=y))
        moves.append(move_retract(setup.safe_z))
    return moves


def engrave_lines_ramped(
    lines: list[list[tuple[float, float]]],
    setup: Setup,
    z: float = -0.3,
    ramp_mm: float = 10.0,
) -> list[Move]:
    moves: list[Move] = []
    moves.append(move_comment("fluting_lines"))
    moves.append(move_set_rpm(setup.tool.rpm))
    moves.append(move_set_feed(setup.tool.feed_xy))

    for poly in lines:
        if not poly or len(poly) < 2:
            continue

        x0, y0 = poly[0]
        x1, y1 = poly[-1]

        line_length = sqrt((x1 - x0) ** 2 + (y1 - y0) ** 2)
        if line_length < 0.01:
            continue

        effective_ramp = min(ramp_mm, line_length / 2)

        dx = (x1 - x0) / line_length
        dy = (y1 - y0) / line_length

        moves.append(move_rapid(x=x0, y=y0, z=setup.safe_z))
        moves.append(move_cut(z=0.0, feed=setup.tool.feed_z))

        ramp_end_x = x0 + dx * effective_ramp
        ramp_end_y = y0 + dy * effective_ramp
        moves.append(move_set_feed(setup.tool.feed_xy))
        moves.append(move_cut(x=ramp_end_x, y=ramp_end_y, z=z))

        if line_length > 2 * effective_ramp + 0.01:
            ramp_exit_x = x1 - dx * effective_ramp
            ramp_exit_y = y1 - dy * effective_ramp
            moves.append(move_cut(x=ramp_exit_x, y=ramp_exit_y))

        moves.append(move_cut(x=x1, y=y1, z=0.0))

        moves.append(move_retract(setup.safe_z))

    return moves
