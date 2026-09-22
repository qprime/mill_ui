from __future__ import annotations

import math
from typing import TYPE_CHECKING

from generators.core import (
    GeneratorResult,
    GeneratorSkipError,
    validate_domain_for_generation,
)
from generators.curves.emit import curve_items
from generators.params.area import RoseCurveParams
from generators.utils import get_local_bounds

if TYPE_CHECKING:
    from domains import Domain
    from domains.domain import Point2D


def rose_curve_generator(
    domain: Domain,
    params: RoseCurveParams,
    *,
    allow_empty: bool = False,
    shape_id_prefix: str = "rose",
) -> GeneratorResult:
    if not validate_domain_for_generation(
        domain,
        min_area_mm2=1.0,
        allow_empty=allow_empty,
        generator_name="RoseCurveGenerator",
    ):
        return []

    local_bounds = get_local_bounds(domain)
    size = params.size_mm if params.size_mm is not None else 0.9 * min(local_bounds.width, local_bounds.height)
    radius = size / 2
    k = params.lobes
    period = math.pi if k % 2 else 2 * math.pi

    def rose(t: float) -> Point2D:
        r = radius * math.cos(k * t)
        return (r * math.cos(t), r * math.sin(t))

    items = curve_items(
        domain,
        rose,
        period,
        initial_segments=32 * k,
        tolerance_mm=params.tolerance_mm,
        rotation_deg=params.rotation_deg,
        min_length_mm=params.min_length_mm,
        depth_mm=params.depth_mm,
        shape_id_prefix=shape_id_prefix,
    )

    if not items and not allow_empty:
        raise GeneratorSkipError(
            f"RoseCurveGenerator: curve of size {size:.1f}mm lies entirely outside domain "
            f"{local_bounds.width:.1f}mm x {local_bounds.height:.1f}mm"
        )

    return items


__all__ = ["rose_curve_generator"]
