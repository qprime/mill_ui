
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
    points = []
    x_range = x_max - x_min

    if x_range <= 0:
        return points


    num_wavelengths = x_range / wavelength
    num_points = max(int(num_wavelengths * points_per_wavelength), 2)


    num_points = min(num_points, 1000)

    for i in range(num_points + 1):
        t = i / num_points
        x = x_min + t * x_range


        wave_angle = (2 * math.pi * x / wavelength) + phase
        y = y_offset + amplitude * math.sin(wave_angle)

        points.append((x, y))

    return points


def _clip_wave_to_domain(
    wave_points: list[tuple[float, float]],
    domain: Domain,
) -> list[list[tuple[float, float]]]:
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

            if len(current_segment) >= 2:
                segments.append(current_segment)
            current_segment = []


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

    params.validate()


    if not validate_domain_for_generation(
        domain,
        min_area_mm2=1.0,
        allow_empty=allow_empty,
        generator_name="WaveGenerator",
    ):
        return []


    bounds = domain.bounds


    min_dimension = min(bounds.width, bounds.height)
    if params.amplitude_mm * 2 > min_dimension:
        if allow_empty:
            return []
        raise ValueError(
            f"WaveGenerator: amplitude {params.amplitude_mm}mm exceeds half of minimum "
            f"domain dimension {min_dimension}mm. Maximum amplitude for this domain "
            f"is {min_dimension / 2}mm."
        )


    wave_spacing = params.tool_width_mm


    local_bounds = _get_local_bounds(domain)
    local_y_min, local_y_max = local_bounds["y_min"], local_bounds["y_max"]
    local_x_min, local_x_max = local_bounds["x_min"], local_bounds["x_max"]

    domain_width = local_x_max - local_x_min
    if params.wave_count is not None and params.wave_count > 0:
        effective_wavelength = domain_width / params.wave_count
    else:
        effective_wavelength = params.wavelength_mm


    coverage_y_min = local_y_min - params.amplitude_mm
    coverage_y_max = local_y_max + params.amplitude_mm


    items: list[Item] = []
    item_index = 0

    y = coverage_y_min
    while y <= coverage_y_max:

        local_wave = _generate_wave_line(
            y_offset=y,
            x_min=local_x_min - effective_wavelength,
            x_max=local_x_max + effective_wavelength,
            amplitude=params.amplitude_mm,
            wavelength=effective_wavelength,
            phase=params.phase_rad,
        )

        if not local_wave:
            y += wave_spacing
            continue


        if params.direction_rad != 0:
            local_wave = _rotate_points(local_wave, params.direction_rad)


        sheet_wave = local_to_sheet_batch(local_wave, domain)


        clipped_segments = _clip_wave_to_domain(sheet_wave, domain)


        for segment in clipped_segments:
            if len(segment) < 2:
                continue


            cx = sum(p[0] for p in segment) / len(segment)
            cy = sum(p[1] for p in segment) / len(segment)


            relative_points = [[pt[0] - cx, pt[1] - cy] for pt in segment]

            geometry_data = {
                "points": relative_points,
                "is_open": True,
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
