from __future__ import annotations

import math
from dataclasses import replace
from typing import TYPE_CHECKING

from generators.core import (
    GeneratorResult,
    GeneratorSkipError,
    generate_shape_id,
    validate_domain_for_generation,
)
from generators.curves.emit import curve_items
from generators.curves.sampler import POINT_BUDGET, PointBudgetError
from generators.params.area import SpirographCurveParams, SpirographLayerParams
from generators.utils import get_local_bounds, polyline_length

if TYPE_CHECKING:
    from collections.abc import Callable

    from domains import Domain
    from domains.domain import Point2D
    from layout_ast.layout import Item

SEGMENTS_PER_TURN = 32


def _ring_radius(layer: SpirographLayerParams) -> float:
    ratio = layer.step / layer.points
    return 1 - ratio if layer.mode == "inside" else 1 + ratio


def _pen_radius(layer: SpirographLayerParams, pen: float) -> float:
    return pen * layer.step / layer.points


def _pen_frequency(layer: SpirographLayerParams) -> float:
    offset = -layer.step if layer.mode == "inside" else layer.step
    return (layer.points + offset) / layer.step


def _pen_segments(layer: SpirographLayerParams) -> int:
    return SEGMENTS_PER_TURN * layer.step * max(1, math.ceil(_pen_frequency(layer) + 1))


def _layer_name(layer: SpirographLayerParams, index: int) -> str:
    return f"points {layer.points} and step {layer.step} in layer {index}"


def _trochoid(layer: SpirographLayerParams, pen: float, scale: float) -> Callable[[float], Point2D]:
    ring = _ring_radius(layer)
    arm = _pen_radius(layer, pen)
    frequency = _pen_frequency(layer)
    sign = -1.0 if layer.mode == "inside" else 1.0

    def trochoid(t: float) -> Point2D:
        x = ring * math.cos(t) - sign * arm * math.cos(frequency * t)
        y = ring * math.sin(t) - arm * math.sin(frequency * t)
        return (scale * x, scale * y)

    return trochoid


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

    local_bounds = get_local_bounds(domain)
    size = params.size_mm if params.size_mm is not None else 0.9 * min(local_bounds.width, local_bounds.height)
    strands = [
        (index, layer, strand, pen)
        for index, layer in enumerate(params.layers)
        for strand, pen in enumerate(layer.pens)
    ]
    outer = max(_ring_radius(layer) + _pen_radius(layer, pen) for _, layer, _, pen in strands)
    scale = size / (2 * outer)

    for index, layer in enumerate(params.layers):
        segments = _pen_segments(layer)
        if any(pen > 0 for pen in layer.pens) and segments >= POINT_BUDGET:
            raise ValueError(
                f"SpirographCurveGenerator: {_layer_name(layer, index)} need {segments} starting segments, "
                f"at or above the sampler's point budget of {POINT_BUDGET}; lower points or step"
            )

    items: list[Item] = []
    for index, layer, strand, pen in strands:
        if pen > 0:
            t_end, segments = 2 * math.pi * layer.step, _pen_segments(layer)
        else:
            t_end, segments = 2 * math.pi, SEGMENTS_PER_TURN
        try:
            items.extend(
                curve_items(
                    domain,
                    _trochoid(layer, pen, scale),
                    t_end,
                    initial_segments=segments,
                    tolerance_mm=params.tolerance_mm,
                    rotation_deg=params.rotation_deg + layer.rotation_deg + strand * layer.rotation_step_deg,
                    min_length_mm=params.min_length_mm,
                    depth_mm=layer.depth_mm or params.depth_mm,
                    shape_id_prefix=shape_id_prefix,
                )
            )
        except PointBudgetError as e:
            raise ValueError(
                f"SpirographCurveGenerator: {_layer_name(layer, index)} exceed the sampler's point budget at "
                f"tolerance {params.tolerance_mm}mm; lower points or step or raise tolerance"
            ) from e

    items = [replace(item, shape_id=generate_shape_id(shape_id_prefix, number)) for number, item in enumerate(items)]

    total = sum(polyline_length(item.geometry.data["points"]) for item in items if item.geometry is not None)
    if total > params.max_cut_length_mm:
        raise ValueError(
            f"SpirographCurveGenerator: stack engraves {total / 1000:.1f} m, above max_cut_length "
            f"{params.max_cut_length_mm / 1000:.1f} m; lower the strand count or raise max_cut_length"
        )

    if not items and not allow_empty:
        raise GeneratorSkipError(
            f"SpirographCurveGenerator: stack of outer diameter {size:.1f}mm lies entirely outside domain "
            f"{local_bounds.width:.1f}mm x {local_bounds.height:.1f}mm"
        )

    return items


__all__ = ["spirograph_curve_generator"]
