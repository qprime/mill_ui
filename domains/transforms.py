from __future__ import annotations

import math
from collections.abc import Sequence
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from domains.domain import Domain

from domains.domain import Point2D


def _origin(domain: Domain) -> Point2D:
    return domain.local_origin if domain.local_origin is not None else (0.0, 0.0)


def local_to_sheet(
    point: Point2D,
    domain: Domain,
) -> Point2D:
    lx, ly = point
    ox, oy = _origin(domain)
    rotation = domain.local_rotation_rad

    if rotation == 0.0:
        return (ox + lx, oy + ly)

    cos_r = math.cos(rotation)
    sin_r = math.sin(rotation)

    rx = lx * cos_r - ly * sin_r
    ry = lx * sin_r + ly * cos_r

    return (ox + rx, oy + ry)


def sheet_to_local(
    point: Point2D,
    domain: Domain,
) -> Point2D:
    sx, sy = point
    ox, oy = _origin(domain)
    rotation = domain.local_rotation_rad

    tx = sx - ox
    ty = sy - oy

    if rotation == 0.0:
        return (tx, ty)

    cos_r = math.cos(-rotation)
    sin_r = math.sin(-rotation)

    lx = tx * cos_r - ty * sin_r
    ly = tx * sin_r + ty * cos_r

    return (lx, ly)


def local_to_sheet_batch(
    points: Sequence[tuple[float, float]] | Sequence[tuple[int, int]],
    domain: Domain,
) -> list[Point2D]:
    if not points:
        return []

    ox, oy = _origin(domain)
    rotation = domain.local_rotation_rad

    if rotation == 0.0:
        return [(ox + lx, oy + ly) for lx, ly in points]

    cos_r = math.cos(rotation)
    sin_r = math.sin(rotation)

    result = []
    for lx, ly in points:
        rx = lx * cos_r - ly * sin_r
        ry = lx * sin_r + ly * cos_r
        result.append((ox + rx, oy + ry))

    return result


def sheet_to_local_batch(
    points: Sequence[tuple[float, float]] | Sequence[tuple[int, int]],
    domain: Domain,
) -> list[Point2D]:
    if not points:
        return []

    ox, oy = _origin(domain)
    rotation = domain.local_rotation_rad

    if rotation == 0.0:
        return [(sx - ox, sy - oy) for sx, sy in points]

    cos_r = math.cos(-rotation)
    sin_r = math.sin(-rotation)

    result = []
    for sx, sy in points:
        tx = sx - ox
        ty = sy - oy
        lx = tx * cos_r - ty * sin_r
        ly = tx * sin_r + ty * cos_r
        result.append((lx, ly))

    return result


def transform_boundary(
    boundary: tuple[Point2D, ...],
    domain: Domain,
    to_sheet: bool = True,
) -> tuple[Point2D, ...]:
    if to_sheet:
        return tuple(local_to_sheet_batch(list(boundary), domain))
    else:
        return tuple(sheet_to_local_batch(list(boundary), domain))


def compose_transforms(
    point: Point2D,
    from_domain: Domain,
    to_domain: Domain,
) -> Point2D:
    sheet_point = local_to_sheet(point, from_domain)
    return sheet_to_local(sheet_point, to_domain)


def get_rotation_between(
    from_domain: Domain,
    to_domain: Domain,
) -> float:
    return to_domain.local_rotation_rad - from_domain.local_rotation_rad


def get_translation_between(
    from_domain: Domain,
    to_domain: Domain,
) -> Point2D:
    fx, fy = _origin(from_domain)
    tx, ty = _origin(to_domain)
    return (tx - fx, ty - fy)
