from __future__ import annotations

from typing import TYPE_CHECKING

from domains.transforms import local_to_sheet_batch
from generators.core import (
    GeneratorResult,
    GeneratorSkipError,
    generate_shape_id,
    validate_domain_for_generation,
)
from generators.svg.params import SVGPathParams
from generators.svg.parser import (
    Polyline,
    parse_svg_path,
    polylines_bounds,
)
from layout_ast.layout import Feature, Geometry, Item, Placement

if TYPE_CHECKING:
    from domains import Domain


def svg_stamp_generator(
    domain: Domain,
    params: SVGPathParams,
    *,
    allow_empty: bool = False,
) -> GeneratorResult:
    if not validate_domain_for_generation(domain, allow_empty=allow_empty, generator_name="svg_stamp_generator"):
        return []

    polylines = parse_svg_path(params.svg_path, tolerance=params.tolerance)

    if not polylines:
        if allow_empty:
            return []
        raise GeneratorSkipError("svg_stamp_generator: SVG path produced no geometry")

    polylines = [p for p in polylines if len(p) >= 2]

    if not polylines:
        if allow_empty:
            return []
        raise GeneratorSkipError("svg_stamp_generator: SVG path produced no valid polylines")

    x_min, y_min, x_max, y_max = polylines_bounds(polylines)
    svg_width = x_max - x_min
    svg_height = y_max - y_min

    if svg_width < 1e-10 or svg_height < 1e-10:
        if allow_empty:
            return []
        raise GeneratorSkipError("svg_stamp_generator: SVG has degenerate dimensions")

    domain_bounds = domain.bounds

    transform = _calculate_transform(
        svg_bounds=(x_min, y_min, x_max, y_max),
        domain_bounds=domain_bounds,
        scale_mode=params.scale_mode,
        svg_unit_mm=params.svg_unit_mm,
        center=params.center,
        invert_y=params.invert_y,
    )

    transformed_polylines = _transform_polylines(polylines, transform)

    sheet_polylines = _to_sheet_coordinates(transformed_polylines, domain)

    items: GeneratorResult = []

    for i, polyline in enumerate(sheet_polylines):
        if len(polyline) < 2:
            continue

        is_closed = _is_closed_polyline(polyline)

        px_min = min(p[0] for p in polyline)
        px_max = max(p[0] for p in polyline)
        py_min = min(p[1] for p in polyline)
        py_max = max(p[1] for p in polyline)
        center_x = (px_min + px_max) / 2
        center_y = (py_min + py_max) / 2

        relative_points = [[p[0] - center_x, p[1] - center_y] for p in polyline]
        if (is_closed and params.feature_type == "pocket") or (is_closed and params.feature_type == "profile"):
            shape_type = "Polygon"
            geometry_data = {
                "points": relative_points,
            }
        else:
            shape_type = "Polyline"
            geometry_data = {
                "points": relative_points,
            }

        feature_side = None
        if params.feature_type == "profile":
            feature_side = "on"

        item = Item(
            kind="shape",
            type=shape_type,
            geometry=Geometry(data=geometry_data),
            placement=Placement(center_xy_mm=(center_x, center_y)),
            feature=Feature(
                type=params.feature_type,
                depth_mm=params.depth_mm,
                side=feature_side,
                is_through=params.is_through,
            ),
            shape_id=generate_shape_id("svg", i),
        )
        items.append(item)

    if not items and not allow_empty:
        raise GeneratorSkipError("svg_stamp_generator: No valid Items produced from SVG")

    return items


def _calculate_transform(
    svg_bounds: tuple[float, float, float, float],
    domain_bounds,
    scale_mode: str,
    svg_unit_mm: float,
    center: bool,
    invert_y: bool,
) -> dict:
    x_min, y_min, x_max, y_max = svg_bounds
    svg_width = x_max - x_min
    svg_height = y_max - y_min

    domain_width = domain_bounds.width
    domain_height = domain_bounds.height

    if scale_mode == "fit":
        scale = min(domain_width / svg_width, domain_height / svg_height)
        scale_x = scale
        scale_y = scale
    elif scale_mode == "fill":
        scale = max(domain_width / svg_width, domain_height / svg_height)
        scale_x = scale
        scale_y = scale
    else:
        scale_x = svg_unit_mm
        scale_y = svg_unit_mm

    if invert_y:
        scale_y = -scale_y

    if center:
        svg_cx = (x_min + x_max) / 2
        svg_cy = (y_min + y_max) / 2

        offset_x = -svg_cx * scale_x
        offset_y = -svg_cy * scale_y
    else:
        offset_x = -x_min * scale_x
        offset_y = -y_min * scale_y

    return {
        "scale_x": scale_x,
        "scale_y": scale_y,
        "offset_x": offset_x,
        "offset_y": offset_y,
    }


def _transform_polylines(
    polylines: list[Polyline],
    transform: dict,
) -> list[Polyline]:
    scale_x = transform["scale_x"]
    scale_y = transform["scale_y"]
    offset_x = transform["offset_x"]
    offset_y = transform["offset_y"]

    return [[(x * scale_x + offset_x, y * scale_y + offset_y) for x, y in polyline] for polyline in polylines]


def _to_sheet_coordinates(
    local_polylines: list[Polyline],
    domain: Domain,
) -> list[Polyline]:
    return [local_to_sheet_batch(polyline, domain) for polyline in local_polylines]


def _is_closed_polyline(polyline: Polyline, tolerance: float = 0.01) -> bool:
    if len(polyline) < 3:
        return False

    first = polyline[0]
    last = polyline[-1]

    dx = abs(first[0] - last[0])
    dy = abs(first[1] - last[1])

    return dx <= tolerance and dy <= tolerance


__all__ = [
    "svg_stamp_generator",
]
