"""Coordinate transforms between domain-local and sheet-space coordinates.

This module provides functions to transform points between two coordinate frames:

1. **Sheet-space coordinates**: Origin at sheet corner, axes aligned with sheet edges.
   This is the global coordinate system used for LayoutAST Items.

2. **Domain-local coordinates**: Origin at domain's local_origin, X-axis rotated by
   local_rotation_rad from sheet X-axis. This is the coordinate system in which
   generators operate, ensuring pattern output is consistent regardless of where
   the domain is placed on the sheet.

Transform semantics:
- The local-to-sheet transform applies rotation first, then translation
- The sheet-to-local transform applies inverse translation first, then inverse rotation
- Round-trip transforms preserve coordinates within floating-point precision

Usage:
    from domains import Domain
    from domains.transforms import local_to_sheet, sheet_to_local

    domain = Domain.from_rectangle(100, 100, center=(200, 150), rotation_rad=0.5)

    # Transform a point from domain-local to sheet space
    sheet_point = local_to_sheet((10, 20), domain)

    # Transform back
    local_point = sheet_to_local(sheet_point, domain)
    # local_point ≈ (10, 20)

    # Batch transform
    sheet_points = local_to_sheet_batch([(0, 0), (10, 0), (0, 10)], domain)

See Also:
    - docs/domain_generator_design.md for coordinate transform contract
    - Section 4.3 for detailed transform specifications
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from domains.domain import Domain

# Type alias for points
Point2D = tuple[float, float]


def local_to_sheet(
    point: Point2D,
    domain: Domain,
) -> Point2D:
    """Transform a point from domain-local coordinates to sheet-space coordinates.

    The transform applies rotation first, then translation:
    1. Rotate by domain.local_rotation_rad (counter-clockwise positive)
    2. Translate by domain.local_origin

    Args:
        point: Point in domain-local coordinates (x, y)
        domain: The domain defining the local coordinate frame

    Returns:
        Point in sheet-space coordinates (x, y)

    Example:
        >>> domain = Domain.from_rectangle(100, 100, center=(200, 150))
        >>> local_to_sheet((0, 0), domain)
        (200.0, 150.0)  # Origin maps to domain center
        >>> local_to_sheet((50, 0), domain)
        (250.0, 150.0)  # 50mm right in local = 50mm right in sheet
    """
    lx, ly = point
    ox, oy = domain.local_origin
    rotation = domain.local_rotation_rad

    # Apply rotation (counter-clockwise positive)
    if rotation == 0.0:
        # Fast path for no rotation
        return (ox + lx, oy + ly)

    cos_r = math.cos(rotation)
    sin_r = math.sin(rotation)

    # Rotate first
    rx = lx * cos_r - ly * sin_r
    ry = lx * sin_r + ly * cos_r

    # Then translate
    return (ox + rx, oy + ry)


def sheet_to_local(
    point: Point2D,
    domain: Domain,
) -> Point2D:
    """Transform a point from sheet-space coordinates to domain-local coordinates.

    The transform applies inverse translation first, then inverse rotation:
    1. Translate by -domain.local_origin
    2. Rotate by -domain.local_rotation_rad

    This is the inverse of local_to_sheet().

    Args:
        point: Point in sheet-space coordinates (x, y)
        domain: The domain defining the local coordinate frame

    Returns:
        Point in domain-local coordinates (x, y)

    Example:
        >>> domain = Domain.from_rectangle(100, 100, center=(200, 150))
        >>> sheet_to_local((200, 150), domain)
        (0.0, 0.0)  # Domain center maps to local origin
        >>> sheet_to_local((250, 150), domain)
        (50.0, 0.0)  # 50mm right of center = (50, 0) in local
    """
    sx, sy = point
    ox, oy = domain.local_origin
    rotation = domain.local_rotation_rad

    # Translate first (inverse of the original translation)
    tx = sx - ox
    ty = sy - oy

    if rotation == 0.0:
        # Fast path for no rotation
        return (tx, ty)

    # Rotate by -rotation (inverse of original rotation)
    cos_r = math.cos(-rotation)
    sin_r = math.sin(-rotation)

    lx = tx * cos_r - ty * sin_r
    ly = tx * sin_r + ty * cos_r

    return (lx, ly)


def local_to_sheet_batch(
    points: list[Point2D] | tuple[Point2D, ...],
    domain: Domain,
) -> list[Point2D]:
    """Transform multiple points from domain-local to sheet-space coordinates.

    More efficient than calling local_to_sheet() repeatedly when transforming
    many points, as trigonometric functions are computed once.

    Args:
        points: List/tuple of points in domain-local coordinates
        domain: The domain defining the local coordinate frame

    Returns:
        List of points in sheet-space coordinates
    """
    if not points:
        return []

    ox, oy = domain.local_origin
    rotation = domain.local_rotation_rad

    if rotation == 0.0:
        # Fast path for no rotation
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
    points: list[Point2D] | tuple[Point2D, ...],
    domain: Domain,
) -> list[Point2D]:
    """Transform multiple points from sheet-space to domain-local coordinates.

    More efficient than calling sheet_to_local() repeatedly when transforming
    many points, as trigonometric functions are computed once.

    Args:
        points: List/tuple of points in sheet-space coordinates
        domain: The domain defining the local coordinate frame

    Returns:
        List of points in domain-local coordinates
    """
    if not points:
        return []

    ox, oy = domain.local_origin
    rotation = domain.local_rotation_rad

    if rotation == 0.0:
        # Fast path for no rotation
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
    """Transform a complete boundary (closed polygon) between coordinate systems.

    Convenience function for transforming domain boundaries.

    Args:
        boundary: Ordered list of points defining the boundary
        domain: The domain defining the local coordinate frame
        to_sheet: If True, transform local→sheet; if False, transform sheet→local

    Returns:
        Transformed boundary as tuple of points
    """
    if to_sheet:
        return tuple(local_to_sheet_batch(list(boundary), domain))
    else:
        return tuple(sheet_to_local_batch(list(boundary), domain))


def compose_transforms(
    point: Point2D,
    from_domain: Domain,
    to_domain: Domain,
) -> Point2D:
    """Transform a point from one domain's local coordinates to another's.

    This is equivalent to:
    1. Transform from from_domain's local space to sheet space
    2. Transform from sheet space to to_domain's local space

    Useful when copying or aligning patterns between domains.

    Args:
        point: Point in from_domain's local coordinates
        from_domain: Source domain's coordinate frame
        to_domain: Target domain's coordinate frame

    Returns:
        Point in to_domain's local coordinates
    """
    # Local -> Sheet -> Local
    sheet_point = local_to_sheet(point, from_domain)
    return sheet_to_local(sheet_point, to_domain)


def get_rotation_between(
    from_domain: Domain,
    to_domain: Domain,
) -> float:
    """Get the rotation difference between two domain coordinate frames.

    Returns the angle that would rotate from_domain's X-axis to align with
    to_domain's X-axis.

    Args:
        from_domain: Source domain
        to_domain: Target domain

    Returns:
        Rotation angle in radians (positive = counter-clockwise)
    """
    return to_domain.local_rotation_rad - from_domain.local_rotation_rad


def get_translation_between(
    from_domain: Domain,
    to_domain: Domain,
) -> Point2D:
    """Get the translation vector between two domain origins in sheet space.

    Returns the vector from from_domain's origin to to_domain's origin.

    Args:
        from_domain: Source domain
        to_domain: Target domain

    Returns:
        Translation vector (dx, dy) in sheet-space units
    """
    fx, fy = from_domain.local_origin
    tx, ty = to_domain.local_origin
    return (tx - fx, ty - fy)
