
from __future__ import annotations

from typing import TYPE_CHECKING

from generators.base import (
    GeneratorResult,
    ProfileParams,
    generate_shape_id,
    validate_domain_for_generation,
)
from generators.utils import extract_loops, loop_type_suffix
from layout_ast.layout import Feature, Geometry, Item, Placement

if TYPE_CHECKING:
    from domains import Domain


def profile_generator(
    domain: Domain,
    params: ProfileParams,
    *,
    allow_empty: bool = False,
    shape_id_prefix: str = "profile",
    sheet_thickness_mm: float | None = None,
    label: str | None = None,
) -> GeneratorResult:

    params.validate()


    if not validate_domain_for_generation(
        domain,
        min_area_mm2=0.01,
        allow_empty=allow_empty,
        generator_name="ProfileGenerator",
    ):
        return []


    try:
        loops = extract_loops(domain, params.loop_selection, "ProfileGenerator")
    except ValueError:
        if allow_empty:
            return []
        raise

    if not loops:
        if allow_empty:
            return []
        raise ValueError(
            f"ProfileGenerator: No loops match selection '{params.loop_selection}'"
        )

    items: list[Item] = []

    for loop_idx, boundary in loops:
        cx = sum(p[0] for p in boundary) / len(boundary)
        cy = sum(p[1] for p in boundary) / len(boundary)

        polygon_points = [[pt[0] - cx, pt[1] - cy] for pt in boundary]

        geometry_data = {
            "points": polygon_points,
        }


        is_through = params.depth == "through"
        depth_mm = 0.0 if is_through else float(params.depth)

        feature_kwargs = {
            "type": "profile",
            "depth_mm": depth_mm,
            "side": params.side,
            "is_through": is_through,
        }


        if params.tab_count > 0:
            feature_kwargs["tab_count"] = params.tab_count
            feature_kwargs["tab_width_mm"] = params.tab_width_mm
            feature_kwargs["tab_height_mm"] = params.tab_height_mm


        item = Item(
            kind="shape",
            type="Polygon",
            geometry=Geometry(data=geometry_data),
            placement=Placement(center_xy_mm=(cx, cy)),
            feature=Feature(**feature_kwargs),
            shape_id=generate_shape_id(
                shape_id_prefix,
                loop_idx,
                loop_type_suffix(loop_idx),
            ),
            label=label,
        )

        items.append(item)

    return items


__all__ = ["profile_generator"]
