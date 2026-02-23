
from __future__ import annotations

from typing import TYPE_CHECKING

from generators.core import (
    GeneratorResult,
    generate_shape_id,
    validate_domain_for_generation,
)
from generators.params.loop import BeadParams
from generators.utils import extract_loops, loop_type_suffix
from layout_ast.layout import Feature, Geometry, Item, Placement

if TYPE_CHECKING:
    from domains import Domain


def _offset_boundary(
    boundary: tuple[tuple[float, float], ...],
    offset: float,
    is_outer: bool,
) -> tuple[tuple[float, float], ...] | None:
    if offset == 0:
        return boundary

    from shapely.geometry import Polygon
    from shapely.ops import orient


    poly = Polygon(boundary)


    buffer_distance = -offset if is_outer else offset

    result = poly.buffer(buffer_distance, join_style=2)

    if result.is_empty or result.area < 0.01:
        return None


    result = orient(result, sign=1.0)


    if result.geom_type == "Polygon":
        coords = list(result.exterior.coords)[:-1]
        return tuple((float(x), float(y)) for x, y in coords)


    if result.geom_type == "MultiPolygon":
        largest = max(result.geoms, key=lambda g: g.area)
        coords = list(largest.exterior.coords)[:-1]
        return tuple((float(x), float(y)) for x, y in coords)

    return None


def bead_generator(
    domain: Domain,
    params: BeadParams,
    *,
    allow_empty: bool = False,
    shape_id_prefix: str = "bead",
) -> GeneratorResult:

    params.validate()


    if not validate_domain_for_generation(
        domain,
        min_area_mm2=0.01,
        allow_empty=allow_empty,
        generator_name="BeadGenerator",
    ):
        return []


    try:
        loops = extract_loops(domain, params.loop_selection, "BeadGenerator")
    except ValueError:
        if allow_empty:
            return []
        raise

    if not loops:
        if allow_empty:
            return []
        raise ValueError(
            f"BeadGenerator: No loops match selection '{params.loop_selection}'"
        )

    items: list[Item] = []

    for loop_idx, boundary in loops:
        is_outer = (loop_idx == 0)


        offset_boundary = _offset_boundary(
            boundary,
            params.offset_mm,
            is_outer,
        )

        if offset_boundary is None:
            if allow_empty:
                continue
            raise ValueError(
                f"BeadGenerator: offset {params.offset_mm}mm collapses loop {loop_idx}. "
                f"Use a smaller offset value."
            )

        cx = sum(p[0] for p in offset_boundary) / len(offset_boundary)
        cy = sum(p[1] for p in offset_boundary) / len(offset_boundary)

        polygon_points = [[pt[0] - cx, pt[1] - cy] for pt in offset_boundary]

        geometry_data = {
            "points": polygon_points,
            "width_mm": params.width_mm,
        }


        item = Item(
            kind="shape",
            type="Polygon",
            geometry=Geometry(data=geometry_data),
            placement=Placement(center_xy_mm=(cx, cy)),
            feature=Feature(
                type="engrave",
                depth_mm=params.depth_mm,
            ),
            shape_id=generate_shape_id(
                shape_id_prefix,
                loop_idx,
                loop_type_suffix(loop_idx),
            ),
        )

        items.append(item)

    if not items and not allow_empty:
        raise ValueError(
            f"BeadGenerator: Could not generate any bead items. "
            f"Check offset parameter and domain size."
        )

    return items


__all__ = ["bead_generator"]
