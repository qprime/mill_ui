
from __future__ import annotations

from typing import TYPE_CHECKING

from generators.base import (
    FlatPocketParams,
    GeneratorResult,
    generate_shape_id,
    validate_domain_for_generation,
)
from layout_ast.layout import Feature, Geometry, Item, Placement

if TYPE_CHECKING:
    from domains import Domain


def flat_pocket_generator(
    domain: Domain,
    params: FlatPocketParams,
    *,
    allow_empty: bool = False,
    shape_id_prefix: str = "pocket",
) -> GeneratorResult:

    params.validate()


    if params.allowance_mm > 0:
        inset_result = domain.inset(params.allowance_mm)
        if inset_result.is_empty:
            if allow_empty:
                return []
            raise ValueError(
                f"FlatPocketGenerator: allowance {params.allowance_mm}mm exceeds domain size. "
                f"Domain bounds: {domain.bounds.width}mm x {domain.bounds.height}mm"
            )

        effective_domain = inset_result.domains[0]
    else:
        effective_domain = domain


    if not validate_domain_for_generation(
        effective_domain,
        min_area_mm2=0.01,
        allow_empty=allow_empty,
        generator_name="FlatPocketGenerator",
    ):
        return []

    cx, cy = effective_domain.centroid

    polygon_points = [[pt[0] - cx, pt[1] - cy] for pt in effective_domain.outer_boundary]

    geometry_data = {
        "points": polygon_points,
    }

    if effective_domain.inner_boundaries:
        geometry_data["holes"] = [
            [[pt[0] - cx, pt[1] - cy] for pt in hole]
            for hole in effective_domain.inner_boundaries
        ]


    item = Item(
        kind="shape",
        type="Polygon",
        geometry=Geometry(data=geometry_data),
        placement=Placement(center_xy_mm=(cx, cy)),
        feature=Feature(
            type="pocket",
            depth=str(params.depth_mm),
            depth_mm=params.depth_mm,
        ),
        shape_id=generate_shape_id(shape_id_prefix, 0, "flat"),
    )

    return [item]


__all__ = ["flat_pocket_generator"]
