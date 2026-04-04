from __future__ import annotations

import math
from dataclasses import replace

from domains import Domain
from generators.core import (
    GeneratorResult,
    GeneratorSkipError,
    generate_shape_id,
    validate_domain_for_generation,
)
from generators.params.area import RadialSvgParams
from generators.radial_utils import generate_angular_positions, radial_point
from generators.svg.params import SVGPathParams
from generators.svg.stamp import svg_stamp_generator
from layout_ast.layout import Geometry, Item, Placement


def _rotate_geometry_points(
    points: list[list[float]],
    angle_rad: float,
) -> list[list[float]]:
    cos_a = math.cos(angle_rad)
    sin_a = math.sin(angle_rad)
    return [[p[0] * cos_a - p[1] * sin_a, p[0] * sin_a + p[1] * cos_a] for p in points]


def _rotate_and_translate_item(
    item: Item,
    angle_rad: float,
    offset: tuple[float, float],
    shape_id: str,
) -> Item:
    assert item.geometry is not None
    assert item.placement is not None
    data = dict(item.geometry.data)

    if "points" in data:
        data["points"] = _rotate_geometry_points(data["points"], angle_rad)
    elif "start" in data and "end" in data:
        rotated = _rotate_geometry_points([data["start"], data["end"]], angle_rad)
        data["start"] = rotated[0]
        data["end"] = rotated[1]

    cx, cy = item.placement.center_xy_mm
    cos_a = math.cos(angle_rad)
    sin_a = math.sin(angle_rad)
    new_cx = cx * cos_a - cy * sin_a + offset[0]
    new_cy = cx * sin_a + cy * cos_a + offset[1]

    return replace(
        item,
        geometry=Geometry(data=data),
        placement=Placement(center_xy_mm=(new_cx, new_cy)),
        shape_id=shape_id,
    )


def radial_svg_generator(
    domain: Domain,
    params: RadialSvgParams,
    *,
    allow_empty: bool = False,
    shape_id_prefix: str = "radial_svg",
    source_dir: str | None = None,
) -> GeneratorResult:
    if not validate_domain_for_generation(
        domain,
        min_area_mm2=1.0,
        allow_empty=allow_empty,
        generator_name="RadialSvgGenerator",
    ):
        return []

    bounds = domain.bounds
    center = (bounds.x_min + bounds.width / 2, bounds.y_min + bounds.height / 2)
    radius = params.radius_mm if params.radius_mm is not None else min(bounds.width, bounds.height) / 2 * 0.6

    stamp_size = params.stamp_size_mm if params.stamp_size_mm is not None else min(bounds.width, bounds.height) / 6

    svg_path_data = params.svg_path
    if svg_path_data.lower().endswith(".svg") and source_dir:
        import os

        from generators.svg.parser import extract_path_data

        file_path = os.path.join(source_dir, svg_path_data)
        svg_path_data = extract_path_data(file_path)

    ref_domain = Domain.from_rectangle(
        width_mm=stamp_size,
        height_mm=stamp_size,
        center=(0.0, 0.0),
    )

    svg_params = SVGPathParams(
        svg_path=svg_path_data,
        depth_mm=params.depth_mm,
        feature_type=params.feature_type,
        scale_mode=params.scale_mode,
        svg_unit_mm=params.svg_unit_mm,
    )

    try:
        ref_items = svg_stamp_generator(ref_domain, svg_params, allow_empty=True)
    except GeneratorSkipError:
        if allow_empty:
            return []
        raise

    if not ref_items:
        if allow_empty:
            return []
        raise GeneratorSkipError("RadialSvgGenerator: SVG produced no geometry")

    positions = generate_angular_positions(
        rays=params.rays,
        minor_subdivisions=0,
        start_deg=params.start_angle_deg,
        end_deg=params.end_angle_deg,
    )

    items: list[Item] = []

    for ray_idx, (angle_deg, _) in enumerate(positions):
        pos = radial_point(center, radius, angle_deg)

        rotation_rad = math.radians(angle_deg) if params.rotate_element else 0.0

        for item_idx, ref_item in enumerate(ref_items):
            sid = generate_shape_id(shape_id_prefix, ray_idx * len(ref_items) + item_idx)
            translated = _rotate_and_translate_item(ref_item, rotation_rad, pos, sid)
            items.append(translated)

    if not items and not allow_empty:
        raise GeneratorSkipError(
            f"RadialSvgGenerator: No items generated. "
            f"Domain: {bounds.width:.1f}x{bounds.height:.1f}mm, rays: {params.rays}"
        )

    return items


__all__ = ["radial_svg_generator"]
