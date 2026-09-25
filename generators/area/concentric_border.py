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
from generators.utils import iter_polygons, polyline_engrave_item, shapely_to_item

if TYPE_CHECKING:
    from domains import Domain
    from domains.domain import MultiDomain
    from layout_ast.layout import Item

_MIN_AREA_MM2 = 1.0


def _pocket_rings(
    domain: Domain,
    outer_result: MultiDomain,
    inset: float,
    params: ConcentricBorderParams,
    shape_id_prefix: str,
    first_idx: int,
) -> list[Item]:
    groove_width_mm = cast(float, params.groove_width_mm)
    inner_result = domain.inset(inset + groove_width_mm, join_style=params.join_style)
    if inner_result.is_empty:
        return []

    items: list[Item] = []
    for outer_domain in outer_result:
        ring_polygon = outer_domain.polygon
        for inner_domain in inner_result:
            ring_polygon = cast(Polygon, ring_polygon.difference(inner_domain.polygon))

        for poly in iter_polygons(ring_polygon):
            if poly.area < 0.01:
                continue
            items.append(
                shapely_to_item(
                    poly,
                    feature_type="pocket",
                    depth_mm=params.depth_mm,
                    shape_id=generate_shape_id(shape_id_prefix, first_idx + len(items)),
                )
            )
    return items


def _engrave_rings(
    outer_result: MultiDomain,
    depth_mm: float,
    shape_id_prefix: str,
    first_idx: int,
) -> list[Item]:
    items: list[Item] = []
    for ring_domain in outer_result:
        if ring_domain.area_mm2 < _MIN_AREA_MM2:
            continue
        for loop in (ring_domain.outer_boundary, *ring_domain.inner_boundaries):
            items.append(
                polyline_engrave_item(
                    [*loop, loop[0]],
                    depth_mm,
                    generate_shape_id(shape_id_prefix, first_idx + len(items)),
                )
            )
    return items


def concentric_border_generator(
    domain: Domain,
    params: ConcentricBorderParams,
    *,
    allow_empty: bool = False,
    shape_id_prefix: str = "border",
) -> GeneratorResult:
    if not validate_domain_for_generation(
        domain,
        min_area_mm2=_MIN_AREA_MM2,
        allow_empty=allow_empty,
        generator_name="ConcentricBorderGenerator",
    ):
        return []

    items: list[Item] = []

    for inset in params.insets_mm:
        outer_result = domain.inset(inset, join_style=params.join_style)
        if outer_result.is_empty:
            if allow_empty:
                continue
            raise GeneratorSkipError(
                f"ConcentricBorderGenerator: inset {inset}mm exceeds domain size. "
                f"Domain bounds: {domain.bounds.width:.1f}mm x {domain.bounds.height:.1f}mm"
            )

        if params.mode == "engrave":
            items.extend(_engrave_rings(outer_result, params.depth_mm, shape_id_prefix, len(items)))
        else:
            items.extend(_pocket_rings(domain, outer_result, inset, params, shape_id_prefix, len(items)))

    if not items and not allow_empty:
        raise GeneratorSkipError(
            f"ConcentricBorderGenerator: No borders fit within domain. "
            f"Domain bounds: {domain.bounds.width:.1f}mm x {domain.bounds.height:.1f}mm, "
            f"smallest inset: {min(params.insets_mm)}mm"
        )

    return items


__all__ = ["concentric_border_generator"]
