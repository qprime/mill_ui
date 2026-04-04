from __future__ import annotations

from typing import TYPE_CHECKING

from generators.area.engrave_text import engrave_text_at_position
from generators.core import (
    GeneratorResult,
    GeneratorSkipError,
    generate_shape_id,
    validate_domain_for_generation,
)
from generators.params.area import RadialTickParams
from generators.radial_utils import generate_angular_positions, radial_point
from generators.utils import create_line_item
from layout_ast.layout import Item

if TYPE_CHECKING:
    from domains import Domain


def radial_tick_generator(
    domain: Domain,
    params: RadialTickParams,
    *,
    allow_empty: bool = False,
    shape_id_prefix: str = "radial_tick",
) -> GeneratorResult:
    if not validate_domain_for_generation(
        domain,
        min_area_mm2=1.0,
        allow_empty=allow_empty,
        generator_name="RadialTickGenerator",
    ):
        return []

    bounds = domain.bounds
    center = (bounds.x_min + bounds.width / 2, bounds.y_min + bounds.height / 2)
    outer_radius = params.radius_mm if params.radius_mm is not None else min(bounds.width, bounds.height) / 2

    major_tick = params.tick_length_mm if params.tick_length_mm is not None else outer_radius * 0.15
    minor_tick = params.minor_tick_length_mm if params.minor_tick_length_mm is not None else major_tick * 0.5

    positions = generate_angular_positions(
        rays=params.rays,
        minor_subdivisions=params.minor_subdivisions,
        start_deg=params.start_angle_deg,
        end_deg=params.end_angle_deg,
    )

    items: list[Item] = []
    major_index = 0

    for angle_deg, is_major in positions:
        tick_len = major_tick if is_major else minor_tick

        if params.inward:
            r_start = outer_radius
            r_end = outer_radius - tick_len
        else:
            r_start = outer_radius - tick_len
            r_end = outer_radius

        start = radial_point(center, r_start, angle_deg)
        end = radial_point(center, r_end, angle_deg)

        item = create_line_item(
            start=start,
            end=end,
            depth_mm=params.depth_mm,
            shape_id=generate_shape_id(shape_id_prefix, len(items)),
        )
        items.append(item)

        if is_major and (params.labels or params.label_list):
            label_text = None
            if params.label_list and major_index < len(params.label_list):
                label_text = params.label_list[major_index]
            elif params.labels:
                label_text = str(major_index)

            if label_text:
                label_radius = outer_radius - tick_len - params.label_height_mm * 1.2
                if params.inward:
                    label_radius = outer_radius + params.label_height_mm * 1.2

                label_pos = radial_point(center, label_radius, angle_deg)

                label_items = engrave_text_at_position(
                    text=label_text,
                    position=label_pos,
                    height_mm=params.label_height_mm,
                    depth_mm=params.depth_mm,
                    alignment="center",
                    vertical_alignment="center",
                    shape_id_prefix=generate_shape_id(shape_id_prefix, major_index, "label"),
                )
                items.extend(label_items)

            major_index += 1

    if not items and not allow_empty:
        raise GeneratorSkipError(
            f"RadialTickGenerator: No ticks generated. "
            f"Domain: {bounds.width:.1f}x{bounds.height:.1f}mm, rays: {params.rays}"
        )

    return items


__all__ = ["radial_tick_generator"]
