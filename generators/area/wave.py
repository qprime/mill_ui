from __future__ import annotations

import math
from typing import TYPE_CHECKING

from domains.transforms import local_to_sheet_batch
from generators.core import (
    GeneratorResult,
    GeneratorSkipError,
    generate_shape_id,
    validate_domain_for_generation,
)
from generators.params.loop import WaveParams
from generators.utils import clip_polylines_to_domain, get_local_bounds, polyline_engrave_item, rotate_points
from layout_ast.layout import Item

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
    points: list[tuple[float, float]] = []
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


def wave_generator(
    domain: Domain,
    params: WaveParams,
    *,
    allow_empty: bool = False,
    shape_id_prefix: str = "wave",
) -> GeneratorResult:
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
        raise GeneratorSkipError(
            f"WaveGenerator: amplitude {params.amplitude_mm}mm exceeds half of minimum "
            f"domain dimension {min_dimension}mm. Maximum amplitude for this domain "
            f"is {min_dimension / 2}mm."
        )

    wave_spacing = params.tool_width_mm

    local_bounds = get_local_bounds(domain)
    local_y_min, local_y_max = local_bounds.y_min, local_bounds.y_max
    local_x_min, local_x_max = local_bounds.x_min, local_bounds.x_max

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
            local_wave = rotate_points(local_wave, params.direction_rad)

        sheet_wave = local_to_sheet_batch(local_wave, domain)

        clipped_segments = clip_polylines_to_domain([sheet_wave], domain, min_length_mm=params.tool_width_mm)

        for segment in clipped_segments:
            items.append(
                polyline_engrave_item(segment, params.depth_mm, generate_shape_id(shape_id_prefix, item_index))
            )
            item_index += 1

        y += wave_spacing

    if not items and not allow_empty:
        raise GeneratorSkipError(
            "WaveGenerator: Could not generate any wave lines for domain. "
            "Domain may be too small or wave parameters incompatible."
        )

    return items


__all__ = ["wave_generator"]
