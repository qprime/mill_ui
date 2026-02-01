
from __future__ import annotations

from typing import TYPE_CHECKING

from generators.base import (
    ChamferParams,
    GeneratorResult,
    LoopSelection,
    generate_shape_id,
    validate_domain_for_generation,
)
from layout_ast.layout import Feature, Geometry, Item, Placement

if TYPE_CHECKING:
    from domains import Domain


def _extract_loops(
    domain: Domain,
    selection: LoopSelection,
) -> list[tuple[int, tuple[tuple[float, float], ...]]]:
    all_loops = [domain.outer_boundary] + list(domain.inner_boundaries)
    num_loops = len(all_loops)

    if selection == "outer_only":
        return [(0, domain.outer_boundary)]

    elif selection == "inner_only":
        return [
            (i + 1, inner)
            for i, inner in enumerate(domain.inner_boundaries)
        ]

    elif selection == "all_loops":
        return [(i, loop) for i, loop in enumerate(all_loops)]

    elif isinstance(selection, list):
        result = []
        for idx in selection:
            if idx < 0 or idx >= num_loops:
                raise ValueError(
                    f"ChamferGenerator: loop index {idx} out of range. "
                    f"Domain has {num_loops} loops (0=outer, 1-{num_loops-1}=inner)"
                )
            result.append((idx, all_loops[idx]))
        return result

    else:
        raise ValueError(f"ChamferGenerator: invalid loop_selection: {selection}")


def _loop_type_suffix(index: int) -> str:
    if index == 0:
        return "outer"
    return f"inner_{index}"


def chamfer_generator(
    domain: Domain,
    params: ChamferParams,
    *,
    allow_empty: bool = False,
    shape_id_prefix: str = "chamfer",
) -> GeneratorResult:

    params.validate()


    if not validate_domain_for_generation(
        domain,
        min_area_mm2=0.01,
        allow_empty=allow_empty,
        generator_name="ChamferGenerator",
    ):
        return []


    try:
        loops = _extract_loops(domain, params.loop_selection)
    except ValueError:
        if allow_empty:
            return []
        raise

    if not loops:
        if allow_empty:
            return []
        raise ValueError(
            f"ChamferGenerator: No loops match selection '{params.loop_selection}'"
        )

    items: list[Item] = []

    for loop_idx, boundary in loops:
        cx = sum(p[0] for p in boundary) / len(boundary)
        cy = sum(p[1] for p in boundary) / len(boundary)

        polygon_points = [[pt[0] - cx, pt[1] - cy] for pt in boundary]

        geometry_data = {
            "points": polygon_points,
        }


        feature_kwargs = {
            "type": "chamfer",
            "depth": str(params.depth_mm),
            "depth_mm": params.depth_mm,
            "chamfer_width_mm": params.width_mm,
            "chamfer_angle_deg": params.angle_degrees,
        }


        if loop_idx == 0:
            feature_kwargs["side"] = "outside"
        else:
            feature_kwargs["side"] = "inside"


        item = Item(
            kind="shape",
            type="Polygon",
            geometry=Geometry(data=geometry_data),
            placement=Placement(center_xy_mm=(cx, cy)),
            feature=Feature(**feature_kwargs),
            shape_id=generate_shape_id(
                shape_id_prefix,
                loop_idx,
                _loop_type_suffix(loop_idx),
            ),
        )

        items.append(item)

    return items


__all__ = ["chamfer_generator"]
