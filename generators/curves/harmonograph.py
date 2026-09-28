from __future__ import annotations

import math
from typing import TYPE_CHECKING

from generators.core import (
    GeneratorResult,
    GeneratorSkipError,
    validate_domain_for_generation,
)
from generators.curves.emit import curve_items
from generators.curves.sampler import POINT_BUDGET, PointBudgetError
from generators.params.area import HarmonographCurveParams, HarmonographPendulumParams

if TYPE_CHECKING:
    from domains import Domain
    from domains.domain import Point2D

PRESAMPLE_PER_OSCILLATION = 64
SEGMENTS_PER_OSCILLATION = 8

_Swing = tuple[float, float, float, float]


def _swings(pendulums: tuple[HarmonographPendulumParams, ...], axis: str) -> list[_Swing]:
    return [
        (p.amplitude_mm, 2 * math.pi * p.frequency, math.radians(p.phase_deg), p.damping)
        for p in pendulums
        if p.axis == axis
    ]


def _displacement(swings: list[_Swing], t: float) -> float:
    return sum(
        amplitude * math.sin(omega * t + phase) * math.exp(-damping * t) for amplitude, omega, phase, damping in swings
    )


def _budget_error(params: HarmonographCurveParams, frequency_max: float) -> ValueError:
    return ValueError(
        f"HarmonographCurveGenerator: {params.cycles} cycles at frequency {frequency_max} exceed the sampler's "
        f"point budget at tolerance {params.tolerance_mm}mm; lower cycles or raise tolerance"
    )


def harmonograph_curve_generator(
    domain: Domain,
    params: HarmonographCurveParams,
    *,
    allow_empty: bool = False,
    shape_id_prefix: str = "harmonograph",
) -> GeneratorResult:
    if not validate_domain_for_generation(
        domain,
        min_area_mm2=1.0,
        allow_empty=allow_empty,
        generator_name="HarmonographCurveGenerator",
    ):
        return []

    swings_x = _swings(params.pendulums, "x")
    swings_y = _swings(params.pendulums, "y")
    frequency_max = max(p.frequency for p in params.pendulums)
    oscillations = math.ceil(frequency_max * params.cycles)
    initial_segments = SEGMENTS_PER_OSCILLATION * oscillations
    if initial_segments >= POINT_BUDGET:
        raise _budget_error(params, frequency_max)

    scale = 1.0
    if params.size_mm is not None:
        count = PRESAMPLE_PER_OSCILLATION * oscillations
        times = [params.cycles * i / (count - 1) for i in range(count)]
        xs = [_displacement(swings_x, t) for t in times]
        ys = [_displacement(swings_y, t) for t in times]
        scale = params.size_mm / max(max(xs) - min(xs), max(ys) - min(ys))

    def harmonograph(t: float) -> Point2D:
        return (scale * _displacement(swings_x, t), scale * _displacement(swings_y, t))

    try:
        items = curve_items(
            domain,
            harmonograph,
            params.cycles,
            initial_segments=initial_segments,
            tolerance_mm=params.tolerance_mm,
            rotation_deg=params.rotation_deg,
            min_length_mm=params.min_length_mm,
            depth_mm=params.depth_mm,
            shape_id_prefix=shape_id_prefix,
        )
    except PointBudgetError as e:
        raise _budget_error(params, frequency_max) from e

    if not items and not allow_empty:
        raise GeneratorSkipError("HarmonographCurveGenerator: figure lies entirely outside domain")

    return items


__all__ = ["harmonograph_curve_generator"]
