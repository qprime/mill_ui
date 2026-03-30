from __future__ import annotations

from typing import TYPE_CHECKING, Any

from generators.core import (
    GeneratorResult,
    GeneratorSkipError,
    generate_shape_id,
    validate_domain_for_generation,
)
from generators.params.area import RaisedPanelParams
from layout_ast.layout import Feature, Geometry, Item, Placement

if TYPE_CHECKING:
    from domains import Domain


def raised_panel_generator(
    domain: Domain,
    params: RaisedPanelParams,
    *,
    allow_empty: bool = False,
    shape_id_prefix: str = "raised_panel",
) -> GeneratorResult:
    if not validate_domain_for_generation(
        domain,
        min_area_mm2=1.0,
        allow_empty=allow_empty,
        generator_name="RaisedPanelGenerator",
    ):
        return []

    field_result = domain.inset(params.border_width_mm)

    if field_result.is_empty:
        if allow_empty:
            return []
        raise GeneratorSkipError(
            f"RaisedPanelGenerator: border_width {params.border_width_mm}mm exceeds "
            f"half of domain minimum dimension. Domain bounds: "
            f"{domain.bounds.width}mm x {domain.bounds.height}mm"
        )

    if len(field_result.domains) != 1:
        raise ValueError(
            f"RaisedPanelGenerator: inset produced {len(field_result.domains)} disjoint regions, "
            f"expected exactly 1. Domain may have complex geometry."
        )
    field_domain = field_result.domains[0]

    items: list[Item] = []

    bcx, bcy = domain.centroid

    border_points = [[pt[0] - bcx, pt[1] - bcy] for pt in domain.outer_boundary]
    field_hole = [[pt[0] - bcx, pt[1] - bcy] for pt in field_domain.outer_boundary]

    holes = [field_hole]
    if domain.inner_boundaries:
        for inner in domain.inner_boundaries:
            holes.append([[pt[0] - bcx, pt[1] - bcy] for pt in inner])

    border_geometry_data = {
        "points": border_points,
        "holes": holes,
    }

    border_item = Item(
        kind="shape",
        type="Polygon",
        geometry=Geometry(data=border_geometry_data),
        placement=Placement(center_xy_mm=(bcx, bcy)),
        feature=Feature(
            type="bevel",
            depth_mm=params.border_depth_mm,
            bevel_width_mm=params.border_width_mm,
            bevel_angle_deg=params.angle_degrees,
            bevel_inner_depth_mm=params.field_depth_mm,
        ),
        shape_id=generate_shape_id(shape_id_prefix, 0, "border"),
    )
    items.append(border_item)

    fcx, fcy = field_domain.centroid

    field_points = [[pt[0] - fcx, pt[1] - fcy] for pt in field_domain.outer_boundary]

    field_geometry_data: dict[str, Any] = {
        "points": field_points,
    }

    if field_domain.inner_boundaries:
        field_geometry_data["holes"] = [
            [[pt[0] - fcx, pt[1] - fcy] for pt in hole] for hole in field_domain.inner_boundaries
        ]

    field_item = Item(
        kind="shape",
        type="Polygon",
        geometry=Geometry(data=field_geometry_data),
        placement=Placement(center_xy_mm=(fcx, fcy)),
        feature=Feature(
            type="pocket",
            depth_mm=params.field_depth_mm,
        ),
        shape_id=generate_shape_id(shape_id_prefix, 1, "field"),
    )
    items.append(field_item)

    return items


__all__ = ["raised_panel_generator"]
