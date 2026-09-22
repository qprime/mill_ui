from __future__ import annotations

import math
from collections.abc import Sequence
from typing import TYPE_CHECKING

from domains import Domain
from domains.transforms import local_to_sheet_batch
from generators.core import (
    GeneratorResult,
    GeneratorSkipError,
    generate_shape_id,
    validate_domain_for_generation,
)
from generators.params.area import PhyllotaxisHoleParams, PhyllotaxisPocketParams, PhyllotaxisSvgParams
from generators.placement import item_inside_domain, place_item
from generators.radial_utils import spiral_positions
from generators.svg.params import SVGPathParams
from generators.svg.stamp import svg_stamp_generator
from generators.utils import create_hole_item
from layout_ast.layout import Feature, Geometry, Item, Placement

if TYPE_CHECKING:
    from domains.domain import Point2D

_ORIGIN: Point2D = (0.0, 0.0)


def _place_on_spiral(
    domain: Domain,
    reference: Sequence[Item],
    *,
    count: int,
    spacing_mm: float,
    angle_deg: float,
    rotate_element: bool,
    scale_with_radius: bool,
    size_mm: float,
    min_size_mm: float | None,
    shape_id_prefix: str,
) -> list[Item]:
    positions = spiral_positions(count, spacing_mm, angle_deg)
    sheet_points = local_to_sheet_batch([point for point, _ in positions], domain)

    items: list[Item] = []
    for index, (sheet_point, (_, theta)) in enumerate(zip(sheet_points, positions, strict=True)):
        scale = math.sqrt((index + 1) / count) if scale_with_radius else 1.0
        if min_size_mm is not None and size_mm * scale < min_size_mm:
            continue
        angle_rad = domain.local_rotation_rad + (theta if rotate_element else 0.0)
        placed = [
            place_item(
                ref_item,
                angle_rad=angle_rad,
                offset=sheet_point,
                shape_id=generate_shape_id(shape_id_prefix, len(items) + offset),
                scale=scale,
            )
            for offset, ref_item in enumerate(reference)
        ]
        if all(item_inside_domain(item, domain) for item in placed):
            items.extend(placed)
    return items


def _require_items(items: list[Item], allow_empty: bool, generator_name: str, domain: Domain, count: int) -> None:
    if not items and not allow_empty:
        bounds = domain.bounds
        raise GeneratorSkipError(
            f"{generator_name}: none of {count} motifs fit in domain {bounds.width:.1f}mm x {bounds.height:.1f}mm"
        )


def phyllotaxis_hole_generator(
    domain: Domain,
    params: PhyllotaxisHoleParams,
    *,
    allow_empty: bool = False,
    shape_id_prefix: str = "phyllotaxis_hole",
) -> GeneratorResult:
    if not validate_domain_for_generation(
        domain, min_area_mm2=1.0, allow_empty=allow_empty, generator_name="PhyllotaxisHoleGenerator"
    ):
        return []

    reference = create_hole_item(_ORIGIN, params.diameter_mm, params.depth_mm, shape_id_prefix)
    items = _place_on_spiral(
        domain,
        [reference],
        count=params.count,
        spacing_mm=params.spacing_mm,
        angle_deg=params.angle_deg,
        rotate_element=False,
        scale_with_radius=False,
        size_mm=params.diameter_mm,
        min_size_mm=None,
        shape_id_prefix=shape_id_prefix,
    )
    _require_items(items, allow_empty, "PhyllotaxisHoleGenerator", domain, params.count)
    return items


def phyllotaxis_pocket_generator(
    domain: Domain,
    params: PhyllotaxisPocketParams,
    *,
    allow_empty: bool = False,
    shape_id_prefix: str = "phyllotaxis_pocket",
) -> GeneratorResult:
    if not validate_domain_for_generation(
        domain, min_area_mm2=1.0, allow_empty=allow_empty, generator_name="PhyllotaxisPocketGenerator"
    ):
        return []

    reference = Item(
        kind="shape",
        type="Circle",
        geometry=Geometry(data={"diameter_mm": params.diameter_mm}),
        placement=Placement(center_xy_mm=_ORIGIN),
        feature=Feature(type="pocket", depth_mm=params.depth_mm),
        shape_id=shape_id_prefix,
    )
    items = _place_on_spiral(
        domain,
        [reference],
        count=params.count,
        spacing_mm=params.spacing_mm,
        angle_deg=params.angle_deg,
        rotate_element=False,
        scale_with_radius=params.scale_with_radius,
        size_mm=params.diameter_mm,
        min_size_mm=params.min_size_mm,
        shape_id_prefix=shape_id_prefix,
    )
    _require_items(items, allow_empty, "PhyllotaxisPocketGenerator", domain, params.count)
    return items


def phyllotaxis_svg_generator(
    domain: Domain,
    params: PhyllotaxisSvgParams,
    *,
    allow_empty: bool = False,
    shape_id_prefix: str = "phyllotaxis_svg",
) -> GeneratorResult:
    if not validate_domain_for_generation(
        domain, min_area_mm2=1.0, allow_empty=allow_empty, generator_name="PhyllotaxisSvgGenerator"
    ):
        return []

    ref_domain = Domain.from_rectangle(width_mm=params.size_mm, height_mm=params.size_mm, center=_ORIGIN)
    svg_params = SVGPathParams(
        svg_path=params.svg_path,
        depth_mm=params.depth_mm,
        feature_type=params.feature_type,
        scale_mode="fit",
    )
    reference = svg_stamp_generator(ref_domain, svg_params, allow_empty=allow_empty)
    if not reference:
        return []

    items = _place_on_spiral(
        domain,
        reference,
        count=params.count,
        spacing_mm=params.spacing_mm,
        angle_deg=params.angle_deg,
        rotate_element=params.rotate_element,
        scale_with_radius=params.scale_with_radius,
        size_mm=params.size_mm,
        min_size_mm=params.min_size_mm,
        shape_id_prefix=shape_id_prefix,
    )
    _require_items(items, allow_empty, "PhyllotaxisSvgGenerator", domain, params.count)
    return items


__all__ = ["phyllotaxis_hole_generator", "phyllotaxis_pocket_generator", "phyllotaxis_svg_generator"]
