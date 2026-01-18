"""Curve flattening algorithms for converting SVG curves to polylines.

This module provides functions to approximate curves (Beziers, arcs) as
sequences of line segments. The tolerance parameter controls approximation
quality—smaller values produce more accurate but denser polylines.

The flattening algorithms use adaptive subdivision to concentrate points
where curvature is high while using fewer points on straighter sections.
"""

from __future__ import annotations

import math
from typing import Iterator

# Type alias for 2D points
Point2D = tuple[float, float]


def flatten_cubic_bezier(
    p0: Point2D,
    p1: Point2D,
    p2: Point2D,
    p3: Point2D,
    tolerance: float = 0.1,
) -> list[Point2D]:
    """Flatten a cubic Bezier curve to a polyline.

    Uses adaptive subdivision based on flatness testing. The curve is
    recursively subdivided until each segment is within the tolerance
    of a straight line.

    Args:
        p0: Start point
        p1: First control point
        p2: Second control point
        p3: End point
        tolerance: Maximum allowed deviation from the true curve (mm)

    Returns:
        List of points approximating the curve (excludes p0, includes p3)
    """
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
    """Recursively flatten a cubic Bezier using de Casteljau subdivision."""
    # Limit recursion depth to prevent stack overflow on degenerate curves
    max_depth = 20
    if depth > max_depth:
        result.append(p3)
        return

    # Check if the curve is flat enough
    if _is_cubic_flat(p0, p1, p2, p3, tolerance):
        result.append(p3)
        return

    # Subdivide at t=0.5 using de Casteljau's algorithm
    # Level 1
    q0 = _midpoint(p0, p1)
    q1 = _midpoint(p1, p2)
    q2 = _midpoint(p2, p3)

    # Level 2
    r0 = _midpoint(q0, q1)
    r1 = _midpoint(q1, q2)

    # Level 3 - the split point
    s = _midpoint(r0, r1)

    # Recursively flatten the two halves
    _flatten_cubic_recursive(p0, q0, r0, s, tolerance, result, depth + 1)
    _flatten_cubic_recursive(s, r1, q2, p3, tolerance, result, depth + 1)


def _is_cubic_flat(
    p0: Point2D,
    p1: Point2D,
    p2: Point2D,
    p3: Point2D,
    tolerance: float,
) -> bool:
    """Check if a cubic Bezier is flat enough to approximate as a line.

    Uses the distance from control points to the chord (line from p0 to p3)
    as the flatness measure.
    """
    # Vector from p0 to p3
    dx = p3[0] - p0[0]
    dy = p3[1] - p0[1]

    # Length squared of the chord
    chord_len_sq = dx * dx + dy * dy

    if chord_len_sq < 1e-12:
        # Degenerate case: start and end are the same
        # Check if control points are also close
        d1 = _distance_sq(p0, p1)
        d2 = _distance_sq(p0, p2)
        return d1 < tolerance * tolerance and d2 < tolerance * tolerance

    # Distance from p1 to chord
    d1 = abs((p1[0] - p0[0]) * dy - (p1[1] - p0[1]) * dx)

    # Distance from p2 to chord
    d2 = abs((p2[0] - p0[0]) * dy - (p2[1] - p0[1]) * dx)

    # Maximum distance normalized by chord length
    max_dist = max(d1, d2) / math.sqrt(chord_len_sq)

    return max_dist <= tolerance


def flatten_quadratic_bezier(
    p0: Point2D,
    p1: Point2D,
    p2: Point2D,
    tolerance: float = 0.1,
) -> list[Point2D]:
    """Flatten a quadratic Bezier curve to a polyline.

    Args:
        p0: Start point
        p1: Control point
        p2: End point
        tolerance: Maximum allowed deviation from the true curve (mm)

    Returns:
        List of points approximating the curve (excludes p0, includes p2)
    """
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
    """Recursively flatten a quadratic Bezier using de Casteljau subdivision."""
    max_depth = 20
    if depth > max_depth:
        result.append(p2)
        return

    # Check if the curve is flat enough
    if _is_quadratic_flat(p0, p1, p2, tolerance):
        result.append(p2)
        return

    # Subdivide at t=0.5
    q0 = _midpoint(p0, p1)
    q1 = _midpoint(p1, p2)
    r = _midpoint(q0, q1)

    # Recursively flatten the two halves
    _flatten_quadratic_recursive(p0, q0, r, tolerance, result, depth + 1)
    _flatten_quadratic_recursive(r, q1, p2, tolerance, result, depth + 1)


def _is_quadratic_flat(
    p0: Point2D,
    p1: Point2D,
    p2: Point2D,
    tolerance: float,
) -> bool:
    """Check if a quadratic Bezier is flat enough to approximate as a line."""
    # Vector from p0 to p2
    dx = p2[0] - p0[0]
    dy = p2[1] - p0[1]

    chord_len_sq = dx * dx + dy * dy

    if chord_len_sq < 1e-12:
        # Degenerate case
        return _distance_sq(p0, p1) < tolerance * tolerance

    # Distance from p1 to chord
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
    """Flatten an elliptical arc to a polyline.

    Implements the SVG arc parameterization: endpoint parameterization
    converted to center parameterization, then sampled adaptively.

    Args:
        p0: Start point
        rx: X-axis radius
        ry: Y-axis radius
        x_axis_rotation: Rotation of ellipse X-axis in radians
        large_arc: If True, choose the larger arc
        sweep: If True, draw arc in positive angle direction
        p1: End point
        tolerance: Maximum allowed deviation from the true arc (mm)

    Returns:
        List of points approximating the arc (excludes p0, includes p1)
    """
    if tolerance <= 0:
        raise ValueError(f"Tolerance must be positive, got {tolerance}")

    # Handle degenerate cases
    if rx <= 0 or ry <= 0:
        # Zero radius means straight line
        return [p1]

    if _distance_sq(p0, p1) < 1e-12:
        # Start and end are the same point
        return []

    # Convert endpoint parameterization to center parameterization
    center_params = _arc_endpoint_to_center(
        p0, rx, ry, x_axis_rotation, large_arc, sweep, p1
    )

    if center_params is None:
        # Degenerate arc, return straight line
        return [p1]

    cx, cy, rx_adj, ry_adj, theta1, dtheta = center_params

    # Calculate number of segments based on arc length and tolerance
    # Use approximation: arc_length ≈ avg_radius * |dtheta|
    avg_radius = (rx_adj + ry_adj) / 2
    arc_length = avg_radius * abs(dtheta)

    # Segments needed for given tolerance (from circle approximation)
    # For a circular arc, error ≈ r * (1 - cos(segment_angle/2))
    # Solving for segment_angle when error = tolerance:
    # segment_angle ≈ 2 * acos(1 - tolerance/r)
    if avg_radius > tolerance:
        segment_angle = 2 * math.acos(max(-1, min(1, 1 - tolerance / avg_radius)))
    else:
        segment_angle = math.pi / 2  # Fallback for very small arcs

    num_segments = max(1, int(math.ceil(abs(dtheta) / segment_angle)))

    # Generate points along the arc
    result: list[Point2D] = []
    cos_phi = math.cos(x_axis_rotation)
    sin_phi = math.sin(x_axis_rotation)

    for i in range(1, num_segments + 1):
        t = i / num_segments
        theta = theta1 + t * dtheta

        # Point on unit circle
        cos_t = math.cos(theta)
        sin_t = math.sin(theta)

        # Scale by radii
        x = rx_adj * cos_t
        y = ry_adj * sin_t

        # Rotate by ellipse rotation and translate to center
        px = cx + x * cos_phi - y * sin_phi
        py = cy + x * sin_phi + y * cos_phi

        result.append((px, py))

    # Ensure the last point is exactly p1 (avoid floating point drift)
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
    """Convert SVG arc endpoint parameterization to center parameterization.

    Based on SVG specification Appendix F.6.5.

    Returns:
        Tuple of (cx, cy, rx, ry, theta1, dtheta) or None if degenerate
    """
    x1, y1 = p0
    x2, y2 = p1

    cos_phi = math.cos(phi)
    sin_phi = math.sin(phi)

    # Compute (x1', y1') - transformed to ellipse coordinate system
    dx = (x1 - x2) / 2
    dy = (y1 - y2) / 2
    x1p = cos_phi * dx + sin_phi * dy
    y1p = -sin_phi * dx + cos_phi * dy

    # Ensure radii are large enough
    # Scale radii if necessary (SVG spec F.6.6.2)
    lambda_sq = (x1p * x1p) / (rx * rx) + (y1p * y1p) / (ry * ry)
    if lambda_sq > 1:
        scale = math.sqrt(lambda_sq)
        rx = rx * scale
        ry = ry * scale

    # Compute (cx', cy')
    rx_sq = rx * rx
    ry_sq = ry * ry
    x1p_sq = x1p * x1p
    y1p_sq = y1p * y1p

    # Numerator for center computation
    num = rx_sq * ry_sq - rx_sq * y1p_sq - ry_sq * x1p_sq
    denom = rx_sq * y1p_sq + ry_sq * x1p_sq

    if denom < 1e-12 or num < 0:
        # Degenerate case
        return None

    factor = math.sqrt(num / denom)
    if large_arc == sweep:
        factor = -factor

    cxp = factor * rx * y1p / ry
    cyp = -factor * ry * x1p / rx

    # Compute (cx, cy) from (cx', cy')
    mx = (x1 + x2) / 2
    my = (y1 + y2) / 2
    cx = cos_phi * cxp - sin_phi * cyp + mx
    cy = sin_phi * cxp + cos_phi * cyp + my

    # Compute theta1 and dtheta
    def angle(ux: float, uy: float, vx: float, vy: float) -> float:
        n = math.sqrt(ux * ux + uy * uy) * math.sqrt(vx * vx + vy * vy)
        if n < 1e-12:
            return 0
        c = (ux * vx + uy * vy) / n
        c = max(-1, min(1, c))  # Clamp for numerical stability
        sign = 1 if ux * vy - uy * vx >= 0 else -1
        return sign * math.acos(c)

    theta1 = angle(1, 0, (x1p - cxp) / rx, (y1p - cyp) / ry)
    dtheta = angle(
        (x1p - cxp) / rx, (y1p - cyp) / ry,
        (-x1p - cxp) / rx, (-y1p - cyp) / ry
    )

    # Adjust dtheta based on sweep flag
    if not sweep and dtheta > 0:
        dtheta -= 2 * math.pi
    elif sweep and dtheta < 0:
        dtheta += 2 * math.pi

    return (cx, cy, rx, ry, theta1, dtheta)


# =============================================================================
# Helper Functions
# =============================================================================

def _midpoint(p1: Point2D, p2: Point2D) -> Point2D:
    """Compute the midpoint between two points."""
    return ((p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2)


def _distance_sq(p1: Point2D, p2: Point2D) -> float:
    """Compute the squared distance between two points."""
    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    return dx * dx + dy * dy


def _distance(p1: Point2D, p2: Point2D) -> float:
    """Compute the distance between two points."""
    return math.sqrt(_distance_sq(p1, p2))


__all__ = [
    "flatten_cubic_bezier",
    "flatten_quadratic_bezier",
    "flatten_arc",
]
