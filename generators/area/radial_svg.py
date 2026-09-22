from __future__ import annotations

import math

from domains import Domain
from generators.core import (
    GeneratorResult,
    GeneratorSkipError,
    generate_shape_id,
    validate_domain_for_generation,
)
from generators.params.area import RadialSvgParams
from generators.placement import place_item
from generators.radial_utils import generate_angular_positions, radial_point
from generators.svg.params import SVGPathParams
from generators.svg.stamp import svg_stamp_generator
from layout_ast.layout import Item


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
            translated = place_item(ref_item, angle_rad=rotation_rad, offset=pos, shape_id=sid)
            items.append(translated)

    if not items and not allow_empty:
        raise GeneratorSkipError(
            f"RadialSvgGenerator: No items generated. "
            f"Domain: {bounds.width:.1f}x{bounds.height:.1f}mm, rays: {params.rays}"
        )

    return items


__all__ = ["radial_svg_generator"]
