from __future__ import annotations

from typing import TYPE_CHECKING

from generators.area.engrave_text import engrave_text_at_position
from generators.core import (
    GeneratorResult,
    GeneratorSkipError,
    generate_shape_id,
    validate_domain_for_generation,
)
from generators.params.area import RadialLabelParams
from generators.radial_utils import generate_angular_positions, radial_point
from layout_ast.layout import Item

if TYPE_CHECKING:
    from domains import Domain


def radial_label_generator(
    domain: Domain,
    params: RadialLabelParams,
    *,
    allow_empty: bool = False,
    shape_id_prefix: str = "radial_label",
) -> GeneratorResult:
    if not validate_domain_for_generation(
        domain,
        min_area_mm2=1.0,
        allow_empty=allow_empty,
        generator_name="RadialLabelGenerator",
    ):
        return []

    bounds = domain.bounds
    center = (bounds.x_min + bounds.width / 2, bounds.y_min + bounds.height / 2)
    radius = params.radius_mm if params.radius_mm is not None else min(bounds.width, bounds.height) / 2 * 0.75

    positions = generate_angular_positions(
        rays=params.rays,
        minor_subdivisions=0,
        start_deg=params.start_angle_deg,
        end_deg=params.end_angle_deg,
    )

    items: list[Item] = []

    for i, (angle_deg, _) in enumerate(positions):
        text = params.values[i] if params.values and i < len(params.values) else str(i + 1)

        pos = radial_point(center, radius, angle_deg)

        label_items = engrave_text_at_position(
            text=text,
            position=pos,
            height_mm=params.label_height_mm,
            depth_mm=params.depth_mm,
            alignment="center",
            vertical_alignment="center",
            shape_id_prefix=generate_shape_id(shape_id_prefix, i),
        )
        items.extend(label_items)

    if not items and not allow_empty:
        raise GeneratorSkipError(
            f"RadialLabelGenerator: No labels generated. "
            f"Domain: {bounds.width:.1f}x{bounds.height:.1f}mm, rays: {params.rays}"
        )

    return items


__all__ = ["radial_label_generator"]
