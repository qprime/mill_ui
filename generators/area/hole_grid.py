from __future__ import annotations

import math
from typing import TYPE_CHECKING

from shapely.geometry import Point

from domains.transforms import local_to_sheet, sheet_to_local
from generators.base import (
    GeneratorResult,
    HoleGridParams,
    generate_shape_id,
    validate_domain_for_generation,
)
from layout_ast.layout import Feature, Geometry, Item, Placement

if TYPE_CHECKING:
    from domains import Domain


def hole_grid_generator(
    domain: Domain,
    params: HoleGridParams,
    *,
    allow_empty: bool = False,
    shape_id_prefix: str = "hole",
) -> GeneratorResult:
    params.validate()

    effective_domain = domain
    if params.inset_mm > 0:
        inset_result = domain.inset(params.inset_mm)
        if not inset_result.domains:
            if allow_empty:
                return []
            raise ValueError(
                f"HoleGridGenerator: Domain too small for inset of {params.inset_mm}mm"
            )
        effective_domain = inset_result.domains[0]

    if not validate_domain_for_generation(
        effective_domain,
        min_area_mm2=math.pi * (params.diameter_mm / 2) ** 2,
        allow_empty=allow_empty,
        generator_name="HoleGridGenerator",
    ):
        return []

    hole_radius = params.diameter_mm / 2
    local_bounds = _get_local_bounds(effective_domain)

    if params.pattern == "hexagonal":
        row_spacing = params.spacing_mm * math.sqrt(3) / 2
    else:
        row_spacing = params.spacing_mm

    grid_points = _generate_grid_points(
        local_bounds,
        params.spacing_mm,
        row_spacing,
        params.pattern,
        params.align,
    )

    items: list[Item] = []
    item_index = 0

    for local_x, local_y in grid_points:
        sheet_point = local_to_sheet((local_x, local_y), effective_domain)

        if _hole_fits_in_domain(sheet_point, hole_radius, effective_domain):
            item = _create_hole_item(
                center=sheet_point,
                diameter_mm=params.diameter_mm,
                depth=params.depth_mm,
                shape_id=generate_shape_id(shape_id_prefix, item_index),
            )
            items.append(item)
            item_index += 1

    if not items and not allow_empty:
        raise ValueError(
            f"HoleGridGenerator: Could not fit any holes in domain. "
            f"Domain may be too small for diameter={params.diameter_mm}mm, "
            f"spacing={params.spacing_mm}mm"
        )

    return items


def _get_local_bounds(domain: Domain) -> dict[str, float]:
    local_points = [
        sheet_to_local(pt, domain)
        for pt in domain.outer_boundary
    ]

    xs = [p[0] for p in local_points]
    ys = [p[1] for p in local_points]

    return {
        "x_min": min(xs),
        "x_max": max(xs),
        "y_min": min(ys),
        "y_max": max(ys),
    }


def _generate_grid_points(
    bounds: dict[str, float],
    col_spacing: float,
    row_spacing: float,
    pattern: str,
    align: str,
) -> list[tuple[float, float]]:
    x_min, x_max = bounds["x_min"], bounds["x_max"]
    y_min, y_max = bounds["y_min"], bounds["y_max"]

    width = x_max - x_min
    height = y_max - y_min

    if align == "center":
        num_cols = int(width // col_spacing) + 1
        num_rows = int(height // row_spacing) + 1

        grid_width = (num_cols - 1) * col_spacing
        grid_height = (num_rows - 1) * row_spacing

        x_start = -grid_width / 2
        y_start = -grid_height / 2
    else:
        x_start = x_min
        y_start = y_min

    points = []
    row = 0
    y = y_start

    while y <= y_max + row_spacing:
        if pattern in ("hexagonal", "offset") and row % 2 == 1:
            row_x_offset = col_spacing / 2
        else:
            row_x_offset = 0

        x = x_start + row_x_offset
        while x <= x_max + col_spacing:
            points.append((x, y))
            x += col_spacing

        y += row_spacing
        row += 1

    return points


def _hole_fits_in_domain(
    center: tuple[float, float],
    radius: float,
    domain: Domain,
) -> bool:
    hole_circle = Point(center).buffer(radius, resolution=16)
    return domain.polygon.contains(hole_circle)


def _create_hole_item(
    center: tuple[float, float],
    diameter_mm: float,
    depth: str | float,
    shape_id: str,
) -> Item:
    if depth == "through":
        depth_str = "through"
        depth_mm_val = None
    else:
        depth_str = str(depth)
        depth_mm_val = float(depth)

    geometry_data = {
        "diameter_mm": diameter_mm,
    }

    return Item(
        kind="shape",
        type="Circle",
        geometry=Geometry(data=geometry_data),
        placement=Placement(center_xy_mm=center),
        feature=Feature(
            type="hole",
            depth=depth_str,
            depth_mm=depth_mm_val,
        ),
        shape_id=shape_id,
    )


__all__ = ["hole_grid_generator"]
