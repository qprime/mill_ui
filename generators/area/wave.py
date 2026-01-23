"""Wave pattern area generator.

A wave generator creates a sinusoidal pattern across the domain interior,
producing parallel grooves at the specified depth. The pattern consists of
multiple parallel polyline paths that approximate sine waves.

The wave pattern is computed in domain-local coordinates, ensuring consistent
output regardless of where the domain is placed on the sheet. The final
geometry is then transformed to sheet coordinates.

Usage:
    from domains import Domain
    from generators.area.wave import wave_generator
    from generators.base import WaveParams

    domain = Domain.from_rectangle(200, 100, center=(100, 50))
    params = WaveParams(
        amplitude_mm=10.0,
        wavelength_mm=30.0,
        depth_mm=3.0,
    )
    items = wave_generator(domain, params)

    # Items can then be added to a LayoutAST
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from domains.transforms import local_to_sheet_batch, sheet_to_local
from generators.base import (
    GeneratorResult,
    WaveParams,
    generate_shape_id,
    validate_domain_for_generation,
)
from layout_ast.layout import Feature, Geometry, Item, Placement

if TYPE_CHECKING:
    from domains import Domain


def _generate_wave_line(
    y_offset: float,
    x_min: float,
    x_max: float,
    amplitude: float,
    wavelength: float,
    phase: float,
    points_per_wavelength: int = 16,
) -> list[tuple[float, float]]:
    """Generate a single wave line as a polyline.

    Args:
        y_offset: Y position of the wave centerline in local coordinates
        x_min: Start X position
        x_max: End X position
        amplitude: Wave amplitude (peak height from centerline)
        wavelength: Distance between adjacent wave peaks
        phase: Phase offset in radians
        points_per_wavelength: Number of points to use per wavelength for smooth curves

    Returns:
        List of (x, y) points forming the wave polyline
    """
    points = []
    x_range = x_max - x_min

    if x_range <= 0:
        return points

    # Calculate number of points based on wavelength coverage
    num_wavelengths = x_range / wavelength
    num_points = max(int(num_wavelengths * points_per_wavelength), 2)

    # Ensure reasonable bounds on point count
    num_points = min(num_points, 1000)  # Cap at 1000 points per line

    for i in range(num_points + 1):
        t = i / num_points
        x = x_min + t * x_range

        # Calculate wave position: y = amplitude * sin(2*pi*x/wavelength + phase)
        wave_angle = (2 * math.pi * x / wavelength) + phase
        y = y_offset + amplitude * math.sin(wave_angle)

        points.append((x, y))

    return points


def _clip_wave_to_domain(
    wave_points: list[tuple[float, float]],
    domain: Domain,
) -> list[list[tuple[float, float]]]:
    """Clip a wave line to stay within the domain boundary.

    This is a simplified clipping that tests each segment of the wave
    against the domain polygon. Points outside are excluded, which may
    result in multiple disjoint segments.

    Args:
        wave_points: The wave polyline in sheet coordinates
        domain: The domain to clip against

    Returns:
        List of polyline segments, each segment is a list of points
    """
    if not wave_points:
        return []

    polygon = domain.polygon
    segments = []
    current_segment = []

    for point in wave_points:
        from shapely.geometry import Point as ShapelyPoint
        shapely_point = ShapelyPoint(point[0], point[1])

        if polygon.contains(shapely_point) or polygon.boundary.distance(shapely_point) < 0.01:
            current_segment.append(point)
        else:
            # Point is outside domain
            if len(current_segment) >= 2:
                segments.append(current_segment)
            current_segment = []

    # Don't forget the last segment
    if len(current_segment) >= 2:
        segments.append(current_segment)

    return segments


def wave_generator(
    domain: Domain,
    params: WaveParams,
    *,
    allow_empty: bool = False,
    shape_id_prefix: str = "wave",
) -> GeneratorResult:
    """Generate wave pattern items that fill the domain interior.

    Creates parallel sinusoidal grooves across the domain. The wave direction
    and phase can be controlled via parameters. Waves are clipped to stay
    within the domain boundary.

    The pattern is computed in domain-local coordinates (centered at domain
    centroid, aligned with domain rotation), then transformed to sheet
    coordinates for the output Items.

    Args:
        domain: The domain defining the pattern region
        params: Wave parameters (amplitude, wavelength, depth, direction, etc.)
        allow_empty: If True, return empty list instead of raising when
            the domain is too small for the wave parameters
        shape_id_prefix: Prefix for generated shape IDs

    Returns:
        List of Polygon Items with engrave features representing wave grooves,
        or empty list if allow_empty=True and generation cannot proceed

    Raises:
        ValueError: If params are invalid or domain too small (unless allow_empty)

    Example:
        >>> domain = Domain.from_rectangle(200, 100, center=(100, 50))
        >>> params = WaveParams(amplitude_mm=10.0, wavelength_mm=30.0, depth_mm=3.0)
        >>> items = wave_generator(domain, params)
        >>> len(items) > 0
        True
    """
    # Validate parameters
    params.validate()

    # Validate domain
    if not validate_domain_for_generation(
        domain,
        min_area_mm2=1.0,  # Need reasonable area for wave pattern
        allow_empty=allow_empty,
        generator_name="WaveGenerator",
    ):
        return []

    # Get domain bounds in sheet space
    bounds = domain.bounds

    # Check if domain is large enough for at least one wave
    min_dimension = min(bounds.width, bounds.height)
    if params.amplitude_mm * 2 > min_dimension:
        if allow_empty:
            return []
        raise ValueError(
            f"WaveGenerator: amplitude {params.amplitude_mm}mm exceeds half of minimum "
            f"domain dimension {min_dimension}mm. Maximum amplitude for this domain "
            f"is {min_dimension / 2}mm."
        )

    # Calculate wave spacing based on tool width
    # Waves are spaced by tool_width_mm to create continuous coverage
    wave_spacing = params.tool_width_mm

    # Determine number of wave lines needed to cover the domain
    # In local coordinates, waves run along X, stacked along Y
    local_bounds = _get_local_bounds(domain)
    local_y_min, local_y_max = local_bounds["y_min"], local_bounds["y_max"]
    local_x_min, local_x_max = local_bounds["x_min"], local_bounds["x_max"]

    domain_width = local_x_max - local_x_min
    if params.wave_count is not None and params.wave_count > 0:
        effective_wavelength = domain_width / params.wave_count
    else:
        effective_wavelength = params.wavelength_mm

    # Expand bounds slightly to ensure full coverage
    coverage_y_min = local_y_min - params.amplitude_mm
    coverage_y_max = local_y_max + params.amplitude_mm

    # Generate wave lines
    items: list[Item] = []
    item_index = 0

    y = coverage_y_min
    while y <= coverage_y_max:
        # Generate wave in local coordinates
        local_wave = _generate_wave_line(
            y_offset=y,
            x_min=local_x_min - effective_wavelength,  # Extend to ensure phase coverage
            x_max=local_x_max + effective_wavelength,
            amplitude=params.amplitude_mm,
            wavelength=effective_wavelength,
            phase=params.phase_rad,
        )

        if not local_wave:
            y += wave_spacing
            continue

        # Apply direction rotation if specified
        if params.direction_rad != 0:
            local_wave = _rotate_points(local_wave, params.direction_rad)

        # Transform to sheet coordinates
        sheet_wave = local_to_sheet_batch(local_wave, domain)

        # Clip to domain boundary
        clipped_segments = _clip_wave_to_domain(sheet_wave, domain)

        # Create an Item for each segment
        for segment in clipped_segments:
            if len(segment) < 2:
                continue

            # Compute center for placement
            cx = sum(p[0] for p in segment) / len(segment)
            cy = sum(p[1] for p in segment) / len(segment)

            # Convert absolute sheet coordinates to relative coordinates (centered on placement)
            relative_points = [[pt[0] - cx, pt[1] - cy] for pt in segment]

            geometry_data = {
                "points": relative_points,
                "is_open": True,  # Wave lines are open polylines
            }

            item = Item(
                kind="shape",
                type="Polyline",
                geometry=Geometry(data=geometry_data),
                placement=Placement(center_xy_mm=(cx, cy)),
                feature=Feature(
                    type="engrave",
                    depth=str(params.depth_mm),
                    depth_mm=params.depth_mm,
                ),
                shape_id=generate_shape_id(shape_id_prefix, item_index),
            )

            items.append(item)
            item_index += 1

        y += wave_spacing

    if not items and not allow_empty:
        raise ValueError(
            f"WaveGenerator: Could not generate any wave lines for domain. "
            f"Domain may be too small or wave parameters incompatible."
        )

    return items


def _get_local_bounds(domain: Domain) -> dict[str, float]:
    """Get domain bounds in domain-local coordinates.

    Transforms the domain's corner points to local coordinates and
    computes the axis-aligned bounding box.

    Args:
        domain: The domain to analyze

    Returns:
        Dict with x_min, x_max, y_min, y_max in local coordinates
    """
    # Transform outer boundary to local coordinates
    local_points = [
        sheet_to_local(pt, domain)
        for pt in domain.outer_boundary
    ]

    xs = [p[0] for p in local_points]
    ys = [p[1] for p in local_points]

    return {
        "x_min": min(xs),
        "x_max": max(xs),
        "y_min": min(ys),
        "y_max": max(ys),
    }


def _rotate_points(
    points: list[tuple[float, float]],
    angle_rad: float,
) -> list[tuple[float, float]]:
    """Rotate points around the origin by the specified angle.

    Args:
        points: List of (x, y) points
        angle_rad: Rotation angle in radians (counter-clockwise positive)

    Returns:
        List of rotated points
    """
    if angle_rad == 0:
        return points

    cos_a = math.cos(angle_rad)
    sin_a = math.sin(angle_rad)

    rotated = []
    for x, y in points:
        rx = x * cos_a - y * sin_a
        ry = x * sin_a + y * cos_a
        rotated.append((rx, ry))

    return rotated


__all__ = ["wave_generator"]
