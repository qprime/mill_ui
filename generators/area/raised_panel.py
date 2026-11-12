from __future__ import annotations

from typing import TYPE_CHECKING

from generators.core import (
    GeneratorResult,
    generate_shape_id,
    require_single_inset_domain,
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

    spec = params.to_spec()
    field_result = domain.inset(spec.field_inset_mm)
    field = require_single_inset_domain(
        field_result,
        allow_empty=allow_empty,
        generator_name="RaisedPanelGenerator",
        empty_message=f"RaisedPanel: field inset {spec.field_inset_mm}mm leaves no field in {domain.bounds}",
    )
    if field is None:
        return []
    if domain.inner_boundaries:
        raise ValueError("RaisedPanel: domains with holes require an explicit profile layout")
    cx, cy = domain.centroid
    return [
        Item(
            kind="shape",
            type="Polygon",
            geometry=Geometry(data={"points": [[x - cx, y - cy] for x, y in domain.outer_boundary]}),
            placement=Placement(center_xy_mm=(cx, cy)),
            feature=Feature(type="raised_panel", depth_mm=spec.border_depth_mm, raised_panel=spec),
            shape_id=generate_shape_id(shape_id_prefix, 0, "panel"),
        )
    ]


__all__ = ["raised_panel_generator"]
