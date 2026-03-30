from __future__ import annotations

from typing import TYPE_CHECKING, cast

from shapely.geometry import Polygon

from generators.core import (
    GeneratorResult,
    GeneratorSkipError,
    generate_shape_id,
    validate_domain_for_generation,
)
from generators.params.area import ConcentricBorderParams
from generators.utils import iter_polygons, shapely_to_item

if TYPE_CHECKING:
    from domains import Domain


def concentric_border_generator(
    domain: Domain,
    params: ConcentricBorderParams,
    *,
    allow_empty: bool = False,
    shape_id_prefix: str = "border",
) -> GeneratorResult:

    params.validate()

    if not validate_domain_for_generation(
        domain,
        min_area_mm2=1.0,
        allow_empty=allow_empty,
        generator_name="ConcentricBorderGenerator",
    ):
        return []

    items = []
    ring_idx = 0

    for inset in params.insets_mm:
        outer_result = domain.inset(inset)
        if outer_result.is_empty:
            if allow_empty:
                continue
            raise GeneratorSkipError(
                f"ConcentricBorderGenerator: inset {inset}mm exceeds domain size. "
                f"Domain bounds: {domain.bounds.width:.1f}mm x {domain.bounds.height:.1f}mm"
            )

        inner_inset = inset + params.groove_width_mm
        inner_result = domain.inset(inner_inset)

        for outer_domain in outer_result:
            if inner_result.is_empty:
                continue

            ring_polygon = outer_domain.polygon
            for inner_domain in inner_result:
                ring_polygon = cast(Polygon, ring_polygon.difference(inner_domain.polygon))

            for poly in iter_polygons(ring_polygon):
                if poly.area < 0.01:
                    continue

                item = shapely_to_item(
                    poly,
                    feature_type="pocket",
                    depth_mm=params.depth_mm,
                    shape_id=generate_shape_id(shape_id_prefix, ring_idx),
                )
                items.append(item)
                ring_idx += 1

    if not items and not allow_empty:
        raise GeneratorSkipError(
            f"ConcentricBorderGenerator: No borders fit within domain. "
            f"Domain bounds: {domain.bounds.width:.1f}mm x {domain.bounds.height:.1f}mm, "
            f"smallest inset: {min(params.insets_mm)}mm"
        )

    return items


__all__ = ["concentric_border_generator"]
