
from __future__ import annotations

import math

from domains.domain import Point2D


def flatten_cubic_bezier(
    p0: Point2D,
    p1: Point2D,
    p2: Point2D,
    p3: Point2D,
    tolerance: float = 0.1,
) -> list[Point2D]:
    if tolerance <= 0:
        raise ValueError(f"Tolerance must be positive, got {tolerance}")

    result: list[Point2D] = []
    _flatten_cubic_recursive(p0, p1, p2, p3, tolerance, result)
    return result


def _flatten_cubic_recursive(
    p0: Point2D,
    p1: Point2D,
    p2: Point2D,
    p3: Point2D,
    tolerance: float,
    result: list[Point2D],
    depth: int = 0,
) -> None:

    max_depth = 20
    if depth > max_depth:
        result.append(p3)
        return


    if _is_cubic_flat(p0, p1, p2, p3, tolerance):
        result.append(p3)
        return


    q0 = _midpoint(p0, p1)
    q1 = _midpoint(p1, p2)
    q2 = _midpoint(p2, p3)


    r0 = _midpoint(q0, q1)
    r1 = _midpoint(q1, q2)


    s = _midpoint(r0, r1)


    _flatten_cubic_recursive(p0, q0, r0, s, tolerance, result, depth + 1)
    _flatten_cubic_recursive(s, r1, q2, p3, tolerance, result, depth + 1)


def _is_cubic_flat(
    p0: Point2D,
    p1: Point2D,
    p2: Point2D,
    p3: Point2D,
    tolerance: float,
) -> bool:

    dx = p3[0] - p0[0]
    dy = p3[1] - p0[1]


    chord_len_sq = dx * dx + dy * dy

    if chord_len_sq < 1e-12:


        d1 = _distance_sq(p0, p1)
        d2 = _distance_sq(p0, p2)
        return d1 < tolerance * tolerance and d2 < tolerance * tolerance


    d1 = abs((p1[0] - p0[0]) * dy - (p1[1] - p0[1]) * dx)


    d2 = abs((p2[0] - p0[0]) * dy - (p2[1] - p0[1]) * dx)


    max_dist = max(d1, d2) / math.sqrt(chord_len_sq)

    return max_dist <= tolerance


def flatten_quadratic_bezier(
    p0: Point2D,
    p1: Point2D,
    p2: Point2D,
    tolerance: float = 0.1,
) -> list[Point2D]:
    if tolerance <= 0:
        raise ValueError(f"Tolerance must be positive, got {tolerance}")

    result: list[Point2D] = []
    _flatten_quadratic_recursive(p0, p1, p2, tolerance, result)
    return result


def _flatten_quadratic_recursive(
    p0: Point2D,
    p1: Point2D,
    p2: Point2D,
    tolerance: float,
    result: list[Point2D],
    depth: int = 0,
) -> None:
    max_depth = 20
    if depth > max_depth:
        result.append(p2)
        return


    if _is_quadratic_flat(p0, p1, p2, tolerance):
        result.append(p2)
        return


    q0 = _midpoint(p0, p1)
    q1 = _midpoint(p1, p2)
    r = _midpoint(q0, q1)


    _flatten_quadratic_recursive(p0, q0, r, tolerance, result, depth + 1)
    _flatten_quadratic_recursive(r, q1, p2, tolerance, result, depth + 1)


def _is_quadratic_flat(
    p0: Point2D,
    p1: Point2D,
    p2: Point2D,
    tolerance: float,
) -> bool:

    dx = p2[0] - p0[0]
    dy = p2[1] - p0[1]

    chord_len_sq = dx * dx + dy * dy

    if chord_len_sq < 1e-12:

        return _distance_sq(p0, p1) < tolerance * tolerance


    d = abs((p1[0] - p0[0]) * dy - (p1[1] - p0[1]) * dx) / math.sqrt(chord_len_sq)

    return d <= tolerance


def flatten_arc(
    p0: Point2D,
    rx: float,
    ry: float,
    x_axis_rotation: float,
    large_arc: bool,
    sweep: bool,
    p1: Point2D,
    tolerance: float = 0.1,
) -> list[Point2D]:
    if tolerance <= 0:
        raise ValueError(f"Tolerance must be positive, got {tolerance}")


    if rx <= 0 or ry <= 0:

        return [p1]

    if _distance_sq(p0, p1) < 1e-12:

        return []


    center_params = _arc_endpoint_to_center(
        p0, rx, ry, x_axis_rotation, large_arc, sweep, p1
    )

    if center_params is None:

        return [p1]

    cx, cy, rx_adj, ry_adj, theta1, dtheta = center_params


    avg_radius = (rx_adj + ry_adj) / 2


    if avg_radius > tolerance:
        segment_angle = 2 * math.acos(max(-1, min(1, 1 - tolerance / avg_radius)))
    else:
        segment_angle = math.pi / 2

    num_segments = max(1, int(math.ceil(abs(dtheta) / segment_angle)))


    result: list[Point2D] = []
    cos_phi = math.cos(x_axis_rotation)
    sin_phi = math.sin(x_axis_rotation)

    for i in range(1, num_segments + 1):
        t = i / num_segments
        theta = theta1 + t * dtheta


        cos_t = math.cos(theta)
        sin_t = math.sin(theta)


        x = rx_adj * cos_t
        y = ry_adj * sin_t


        px = cx + x * cos_phi - y * sin_phi
        py = cy + x * sin_phi + y * cos_phi

        result.append((px, py))


    if result:
        result[-1] = p1

    return result


def _arc_endpoint_to_center(
    p0: Point2D,
    rx: float,
    ry: float,
    phi: float,
    large_arc: bool,
    sweep: bool,
    p1: Point2D,
) -> tuple[float, float, float, float, float, float] | None:
    x1, y1 = p0
    x2, y2 = p1

    cos_phi = math.cos(phi)
    sin_phi = math.sin(phi)


    dx = (x1 - x2) / 2
    dy = (y1 - y2) / 2
    x1p = cos_phi * dx + sin_phi * dy
    y1p = -sin_phi * dx + cos_phi * dy


    lambda_sq = (x1p * x1p) / (rx * rx) + (y1p * y1p) / (ry * ry)
    if lambda_sq > 1:
        scale = math.sqrt(lambda_sq)
        rx = rx * scale
        ry = ry * scale


    rx_sq = rx * rx
    ry_sq = ry * ry
    x1p_sq = x1p * x1p
    y1p_sq = y1p * y1p


    num = rx_sq * ry_sq - rx_sq * y1p_sq - ry_sq * x1p_sq
    denom = rx_sq * y1p_sq + ry_sq * x1p_sq

    if denom < 1e-12 or num < 0:

        return None

    factor = math.sqrt(num / denom)
    if large_arc == sweep:
        factor = -factor

    cxp = factor * rx * y1p / ry
    cyp = -factor * ry * x1p / rx


    mx = (x1 + x2) / 2
    my = (y1 + y2) / 2
    cx = cos_phi * cxp - sin_phi * cyp + mx
    cy = sin_phi * cxp + cos_phi * cyp + my


    def angle(ux: float, uy: float, vx: float, vy: float) -> float:
        n = math.sqrt(ux * ux + uy * uy) * math.sqrt(vx * vx + vy * vy)
        if n < 1e-12:
            return 0
        c = (ux * vx + uy * vy) / n
        c = max(-1, min(1, c))
        sign = 1 if ux * vy - uy * vx >= 0 else -1
        return sign * math.acos(c)

    theta1 = angle(1, 0, (x1p - cxp) / rx, (y1p - cyp) / ry)
    dtheta = angle(
        (x1p - cxp) / rx, (y1p - cyp) / ry,
        (-x1p - cxp) / rx, (-y1p - cyp) / ry
    )


    if not sweep and dtheta > 0:
        dtheta -= 2 * math.pi
    elif sweep and dtheta < 0:
        dtheta += 2 * math.pi

    return (cx, cy, rx, ry, theta1, dtheta)


def _midpoint(p1: Point2D, p2: Point2D) -> Point2D:
    return ((p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2)


def _distance_sq(p1: Point2D, p2: Point2D) -> float:
    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    return dx * dx + dy * dy


def _distance(p1: Point2D, p2: Point2D) -> float:
    return math.sqrt(_distance_sq(p1, p2))


__all__ = [
    "flatten_cubic_bezier",
    "flatten_quadratic_bezier",
    "flatten_arc",
]
