from __future__ import annotations

import math
from typing import TYPE_CHECKING

from generators.core import (
    GeneratorResult,
    GeneratorSkipError,
    validate_domain_for_generation,
)
from generators.curves.emit import curve_items
from generators.params.area import LissajousCurveParams
from generators.utils import get_local_bounds

if TYPE_CHECKING:
    from domains import Domain
    from domains.domain import Point2D


def _first_set(*values: float | None, default: float) -> float:
    for value in values:
        if value is not None:
            return value
    return default


def lissajous_curve_generator(
    domain: Domain,
    params: LissajousCurveParams,
    *,
    allow_empty: bool = False,
    shape_id_prefix: str = "lissajous",
) -> GeneratorResult:
    if not validate_domain_for_generation(
        domain,
        min_area_mm2=1.0,
        allow_empty=allow_empty,
        generator_name="LissajousCurveGenerator",
    ):
        return []

    local_bounds = get_local_bounds(domain)
    width = _first_set(params.width_mm, params.size_mm, default=0.9 * local_bounds.width)
    height = _first_set(params.height_mm, params.size_mm, default=0.9 * local_bounds.height)
    common = math.gcd(params.frequency_x, params.frequency_y)
    fx = params.frequency_x // common
    fy = params.frequency_y // common
    phase = math.radians(params.phase_deg)
    half_width = width / 2
    half_height = height / 2

    def lissajous(t: float) -> Point2D:
        return (half_width * math.sin(fx * t + phase), half_height * math.sin(fy * t))

    items = curve_items(
        domain,
        lissajous,
        2 * math.pi,
        initial_segments=32 * max(fx, fy),
        tolerance_mm=params.tolerance_mm,
        rotation_deg=params.rotation_deg,
        min_length_mm=params.min_length_mm,
        depth_mm=params.depth_mm,
        shape_id_prefix=shape_id_prefix,
    )

    if not items and not allow_empty:
        raise GeneratorSkipError(
            f"LissajousCurveGenerator: {width:.1f}mm x {height:.1f}mm figure lies entirely outside domain "
            f"{local_bounds.width:.1f}mm x {local_bounds.height:.1f}mm"
        )

    return items


__all__ = ["lissajous_curve_generator"]
