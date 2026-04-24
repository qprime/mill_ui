from __future__ import annotations

from typing import Any

from core.constants import FeatureType, ShapeType
from domains import Domain
from generators.core import (
    GeneratorResult,
    generate_shape_id,
    validate_domain_for_generation,
)
from generators.params.area import HeightfieldParams
from layout_ast.layout import Feature, Geometry, Item, Placement


def heightfield_generator(
    domain: Domain,
    params: HeightfieldParams,
    *,
    allow_empty: bool = False,
    shape_id_prefix: str = "heightfield",
) -> GeneratorResult:
    if not validate_domain_for_generation(
        domain,
        min_area_mm2=1.0,
        allow_empty=allow_empty,
        generator_name="HeightfieldGenerator",
    ):
        return []

    bounds = domain.bounds
    center = (bounds.x_min + bounds.width / 2.0, bounds.y_min + bounds.height / 2.0)

    geometry_data: dict[str, Any] = {
        "w_mm": params.width_mm,
        "h_mm": params.height_mm,
        "image_path": params.image_path,
        "white_is_high": params.white_is_high,
        "tools": [
            {
                "tool": t.tool,
                "role": t.role,
                "stepover_frac": t.stepover_frac,
                "stepdown_mm": t.stepdown_mm,
                "angle_deg": t.angle_deg,
            }
            for t in params.tools
        ],
    }

    item = Item(
        kind="shape",
        type=ShapeType.HEIGHTFIELD,
        geometry=Geometry(data=geometry_data),
        placement=Placement(center_xy_mm=center),
        feature=Feature(type=FeatureType.HEIGHTFIELD, depth_mm=params.depth_mm),
        shape_id=generate_shape_id(shape_id_prefix, 0),
    )
    return [item]


__all__ = ["heightfield_generator"]
