from __future__ import annotations

import math
from fractions import Fraction
from typing import TYPE_CHECKING

from generators.core import (
    GeneratorResult,
    GeneratorSkipError,
    validate_domain_for_generation,
)
from generators.curves.emit import curve_items
from generators.curves.sampler import PointBudgetError
from generators.params.area import SpirographCurveParams

if TYPE_CHECKING:
    from domains import Domain
    from domains.domain import Point2D

MAX_AUTO_TURNS = 60
RATIO_MAX_DENOMINATOR = 1000


def closing_turns(fixed_radius_mm: float, rolling_radius_mm: float) -> int:
    return Fraction(fixed_radius_mm / rolling_radius_mm).limit_denominator(RATIO_MAX_DENOMINATOR).denominator


def spirograph_curve_generator(
    domain: Domain,
    params: SpirographCurveParams,
    *,
    allow_empty: bool = False,
    shape_id_prefix: str = "spirograph",
) -> GeneratorResult:
    if not validate_domain_for_generation(
        domain,
        min_area_mm2=1.0,
        allow_empty=allow_empty,
        generator_name="SpirographCurveGenerator",
    ):
        return []

    fixed = params.fixed_radius_mm
    rolling = params.rolling_radius_mm
    pen = params.pen_offset_mm
    sign = 1.0 if params.mode == "outside" else -1.0
    base = fixed + sign * rolling
    ratio = base / rolling
    outer = base + pen
    scale = params.size_mm / (2 * outer) if params.size_mm is not None else 1.0

    turns = params.revolutions
    if turns is None:
        turns = closing_turns(fixed, rolling)
        if turns > MAX_AUTO_TURNS:
            raise ValueError(
                f"SpirographCurveGenerator: fixed_radius {fixed}mm and rolling_radius {rolling}mm "
                f"need {turns} revolutions to close, above the automatic limit of {MAX_AUTO_TURNS}; "
                "set revolutions explicitly"
            )

    def trochoid(t: float) -> Point2D:
        x = base * math.cos(t) - sign * pen * math.cos(ratio * t)
        y = base * math.sin(t) - pen * math.sin(ratio * t)
        return (scale * x, scale * y)

    try:
        items = curve_items(
            domain,
            trochoid,
            2 * math.pi * turns,
            initial_segments=32 * turns * max(1, math.ceil(abs(ratio) + 1)),
            tolerance_mm=params.tolerance_mm,
            rotation_deg=params.rotation_deg,
            min_length_mm=params.min_length_mm,
            depth_mm=params.depth_mm,
            shape_id_prefix=shape_id_prefix,
        )
    except PointBudgetError as e:
        raise ValueError(
            f"SpirographCurveGenerator: {turns} revolutions exceed the sampler's point budget at tolerance "
            f"{params.tolerance_mm}mm; lower revolutions or raise tolerance"
        ) from e

    if not items and not allow_empty:
        raise GeneratorSkipError(
            f"SpirographCurveGenerator: figure of outer diameter {2 * scale * outer:.1f}mm lies entirely outside domain"
        )

    return items


__all__ = ["MAX_AUTO_TURNS", "RATIO_MAX_DENOMINATOR", "spirograph_curve_generator"]
