from itertools import accumulate, pairwise
from math import dist, isfinite

from cam.model.setup import Setup
from cam.moves import Move
from cam.path.toolpath import move_comment, move_cut, move_rapid, move_retract, move_set_feed, move_set_rpm

_MIN_RAMP_PATH_LENGTH_MM = 0.01


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


def _ramped_path_moves(poly: list[tuple[float, float]], z: float, ramp_mm: float) -> list[Move]:
    segments = [(start, end, dist(start, end)) for start, end in pairwise(poly)]
    distances = list(accumulate((length for _, _, length in segments), initial=0.0))
    total_length = distances[-1]
    if total_length < _MIN_RAMP_PATH_LENGTH_MM:
        return []
    ramp = min(ramp_mm, total_length / 2)
    boundaries = sorted({ramp, total_length - ramp})
    moves: list[Move] = []
    previous_z = 0.0
    for (start, end, length), distance, end_distance in zip(segments, distances[:-1], distances[1:], strict=True):
        if length == 0:
            continue
        stops = [boundary for boundary in boundaries if distance < boundary < end_distance]
        stops.append(end_distance)
        for stop in stops:
            if stop == end_distance:
                x, y = end
            else:
                fraction = (stop - distance) / length
                x = start[0] + (end[0] - start[0]) * fraction
                y = start[1] + (end[1] - start[1]) * fraction
            cut_z = z * min(stop / ramp, (total_length - stop) / ramp, 1.0) if stop < total_length else 0.0
            moves.append(move_cut(x=x, y=y, z=cut_z if cut_z != previous_z else None))
            previous_z = cut_z
    return moves


def engrave_lines_ramped(
    lines: list[list[tuple[float, float]]],
    setup: Setup,
    z: float = -0.3,
    ramp_mm: float = 10.0,
) -> list[Move]:
    if not isfinite(ramp_mm) or ramp_mm < 0:
        raise ValueError(f"engrave_lines_ramped: ramp_mm must be finite and non-negative, got {ramp_mm}")
    if ramp_mm == 0:
        return engrave_lines(lines, setup, z=z)
    moves: list[Move] = []
    moves.append(move_comment("fluting_lines"))
    moves.append(move_set_rpm(setup.tool.rpm))
    moves.append(move_set_feed(setup.tool.feed_xy))

    for poly in lines:
        path_moves = _ramped_path_moves(poly, z, ramp_mm)
        if not path_moves:
            continue

        x0, y0 = poly[0]
        moves.append(move_rapid(x=x0, y=y0, z=setup.safe_z))
        moves.append(move_cut(z=0.0, feed=setup.tool.feed_z))
        moves.append(move_set_feed(setup.tool.feed_xy))
        moves.extend(path_moves)
        moves.append(move_retract(setup.safe_z))

    return moves
