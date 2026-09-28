from __future__ import annotations

import math
from collections.abc import Callable

from domains.domain import Point2D

_MAX_SUBDIVISION_DEPTH = 16
POINT_BUDGET = 20000


class PointBudgetError(ValueError):
    pass


def sample_parametric(
    fn: Callable[[float], Point2D],
    t_start: float,
    t_end: float,
    *,
    tolerance_mm: float,
    initial_segments: int,
    max_points: int = POINT_BUDGET,
) -> list[Point2D]:
    if tolerance_mm <= 0:
        raise ValueError(f"sample_parametric: tolerance_mm must be positive, got {tolerance_mm}")
    if initial_segments < 1:
        raise ValueError(f"sample_parametric: initial_segments must be >= 1, got {initial_segments}")
    if t_end <= t_start:
        raise ValueError(f"sample_parametric: t_end ({t_end}) must exceed t_start ({t_start})")
    if max_points < 2:
        raise ValueError(f"sample_parametric: max_points must be >= 2, got {max_points}")

    points: list[Point2D] = [fn(t_start)]
    step = (t_end - t_start) / initial_segments
    for i in range(initial_segments):
        t0 = t_start + i * step
        t1 = t_end if i == initial_segments - 1 else t_start + (i + 1) * step
        _refine(fn, t0, points[-1], t1, fn(t1), tolerance_mm, max_points, points, 0)
    return points


def _refine(
    fn: Callable[[float], Point2D],
    t0: float,
    p0: Point2D,
    t1: float,
    p1: Point2D,
    tolerance_mm: float,
    max_points: int,
    points: list[Point2D],
    depth: int,
) -> None:
    tm = (t0 + t1) / 2
    pm = fn(tm)
    if depth < _MAX_SUBDIVISION_DEPTH and _chord_deviation(p0, pm, p1) > tolerance_mm:
        _refine(fn, t0, p0, tm, pm, tolerance_mm, max_points, points, depth + 1)
        _refine(fn, tm, pm, t1, p1, tolerance_mm, max_points, points, depth + 1)
        return
    if len(points) >= max_points:
        raise PointBudgetError(
            f"sample_parametric: point budget of {max_points} exceeded at tolerance {tolerance_mm}mm; "
            "raise the tolerance or lower the curve's frequency"
        )
    points.append(p1)


def _chord_deviation(p0: Point2D, pm: Point2D, p1: Point2D) -> float:
    dx = p1[0] - p0[0]
    dy = p1[1] - p0[1]
    chord_sq = dx * dx + dy * dy
    if chord_sq < 1e-18:
        return math.dist(p0, pm)
    return abs((pm[0] - p0[0]) * dy - (pm[1] - p0[1]) * dx) / math.sqrt(chord_sq)


__all__ = ["POINT_BUDGET", "PointBudgetError", "sample_parametric"]
