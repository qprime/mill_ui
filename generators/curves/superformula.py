from __future__ import annotations

import math
from collections.abc import Callable
from typing import TYPE_CHECKING

from generators.core import (
    GeneratorResult,
    GeneratorSkipError,
    validate_domain_for_generation,
)
from generators.curves.emit import curve_items
from generators.curves.sampler import PointBudgetError
from generators.params.area import SuperformulaCurveParams
from generators.utils import get_local_bounds

if TYPE_CHECKING:
    from domains import Domain
    from domains.domain import Point2D

SCALE_GRID_PER_LOBE = 256
PEAK_REFINE_ITERATIONS = 50
_GOLDEN_RATIO_CONJUGATE = (math.sqrt(5) - 1) / 2


def _log_radius(phi: float, params: SuperformulaCurveParams) -> float:
    angle = params.m * phi / 4
    terms = [
        exponent * math.log(abs(base) / scale)
        for base, scale, exponent in (
            (math.cos(angle), params.a, params.n2),
            (math.sin(angle), params.b, params.n3),
        )
        if base != 0.0
    ]
    peak = max(terms)
    log_sum = peak + math.log(sum(math.exp(term - peak) for term in terms))
    return -log_sum / params.n1


def _golden_section_max(fn: Callable[[float], float], low: float, high: float) -> float:
    inner_low = high - _GOLDEN_RATIO_CONJUGATE * (high - low)
    inner_high = low + _GOLDEN_RATIO_CONJUGATE * (high - low)
    value_low = fn(inner_low)
    value_high = fn(inner_high)
    for _ in range(PEAK_REFINE_ITERATIONS):
        if value_low > value_high:
            high, inner_high, value_high = inner_high, inner_low, value_low
            inner_low = high - _GOLDEN_RATIO_CONJUGATE * (high - low)
            value_low = fn(inner_low)
        else:
            low, inner_low, value_low = inner_low, inner_high, value_high
            inner_high = low + _GOLDEN_RATIO_CONJUGATE * (high - low)
            value_high = fn(inner_high)
    return max(value_low, value_high)


def superformula_curve_generator(
    domain: Domain,
    params: SuperformulaCurveParams,
    *,
    allow_empty: bool = False,
    shape_id_prefix: str = "superformula",
) -> GeneratorResult:
    if not validate_domain_for_generation(
        domain,
        min_area_mm2=1.0,
        allow_empty=allow_empty,
        generator_name="SuperformulaCurveGenerator",
    ):
        return []

    local_bounds = get_local_bounds(domain)
    size = params.size_mm if params.size_mm is not None else 0.9 * min(local_bounds.width, local_bounds.height)
    radius = size / 2
    turns = 2 if params.m % 2 and (params.a != params.b or params.n2 != params.n3) else 1
    grid_step = 2 * math.pi / (SCALE_GRID_PER_LOBE * params.m)

    def log_radius(phi: float) -> float:
        return _log_radius(phi, params)

    peak = max(range(SCALE_GRID_PER_LOBE * params.m * turns), key=lambda i: log_radius(i * grid_step))
    log_radius_max = max(
        log_radius(peak * grid_step),
        _golden_section_max(log_radius, (peak - 1) * grid_step, (peak + 1) * grid_step),
    )

    def superformula(t: float) -> Point2D:
        r = radius * math.exp(log_radius(t) - log_radius_max)
        return (r * math.cos(t), r * math.sin(t))

    try:
        items = curve_items(
            domain,
            superformula,
            2 * math.pi * turns,
            initial_segments=32 * params.m * turns,
            tolerance_mm=params.tolerance_mm,
            rotation_deg=params.rotation_deg,
            min_length_mm=params.min_length_mm,
            depth_mm=params.depth_mm,
            shape_id_prefix=shape_id_prefix,
        )
    except PointBudgetError as e:
        raise ValueError(
            f"SuperformulaCurveGenerator: {params.m} lobes exceed the sampler's point budget at tolerance "
            f"{params.tolerance_mm}mm; lower m or raise tolerance"
        ) from e

    if not items and not allow_empty:
        raise GeneratorSkipError(
            f"SuperformulaCurveGenerator: curve of size {size:.1f}mm lies entirely outside domain "
            f"{local_bounds.width:.1f}mm x {local_bounds.height:.1f}mm"
        )

    return items


__all__ = ["superformula_curve_generator"]
