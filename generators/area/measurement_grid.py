from __future__ import annotations

from typing import TYPE_CHECKING

from generators.core import (
    GeneratorResult,
    validate_domain_for_generation,
)
from generators.measurement_helpers import (
    compute_label_offset,
    create_engraved_line,
    create_label_items,
    should_label,
    validate_items_generated,
)
from generators.params.area import MeasurementGridParams
from generators.utils import get_local_bounds, is_major_tick
from layout_ast.layout import Item

if TYPE_CHECKING:
    from domains import Domain


def measurement_grid_generator(
    domain: Domain,
    params: MeasurementGridParams,
    *,
    allow_empty: bool = False,
    shape_id_prefix: str = "measurement_grid",
) -> GeneratorResult:
    if not validate_domain_for_generation(
        domain,
        min_area_mm2=1.0,
        allow_empty=allow_empty,
        generator_name="MeasurementGridGenerator",
    ):
        return []

    local_bounds = get_local_bounds(domain)
    local_x_min = local_bounds["x_min"]
    local_x_max = local_bounds["x_max"]
    local_y_min = local_bounds["y_min"]
    local_y_max = local_bounds["y_max"]

    minor_spacing = params.get_minor_spacing()
    major_spacing = params.get_major_spacing()
    minor_length = params.minor_length_mm
    major_length = params.major_length_mm

    items: list[Item] = []
    item_index = 0

    x_origin = local_x_min
    y_origin = local_y_min

    label_offset = compute_label_offset(major_length, params.label_height_mm, params.label_offset_mm)
    label_index = 0

    label_spacing = int(major_spacing) * params.label_interval

    x = x_origin
    first_x_major = True
    while x <= local_x_max + 0.001:
        is_major = is_major_tick(x, x_origin, major_spacing)
        if is_major or params.minor_ticks:
            tick_length = major_length if is_major else minor_length

            new_items = create_engraved_line(
                (x, local_y_min),
                (x, local_y_min + tick_length),
                "bottom",
                domain,
                params.depth_mm,
                shape_id_prefix,
                item_index,
            )
            items.extend(new_items)
            item_index += len(new_items)

            new_items = create_engraved_line(
                (x, local_y_max),
                (x, local_y_max - tick_length),
                "top",
                domain,
                params.depth_mm,
                shape_id_prefix,
                item_index,
            )
            items.extend(new_items)
            item_index += len(new_items)

        if is_major:
            value = round(x - x_origin)
            skip_corner = first_x_major and value == 0
            if (
                value >= 0
                and not skip_corner
                and params.labels
                and should_label(value, params.label_start, label_spacing)
            ):
                new_items = create_label_items(
                    (x, local_y_min - label_offset),
                    value,
                    "horizontal",
                    domain,
                    params.depth_mm,
                    params.label_height_mm,
                    shape_id_prefix,
                    label_index,
                )
                items.extend(new_items)
                label_index += 1

                new_items = create_label_items(
                    (x, local_y_max + label_offset),
                    value,
                    "horizontal",
                    domain,
                    params.depth_mm,
                    params.label_height_mm,
                    shape_id_prefix,
                    label_index,
                )
                items.extend(new_items)
                label_index += 1
            first_x_major = False

        x += minor_spacing

    y = y_origin
    first_y_major = True
    while y <= local_y_max + 0.001:
        is_major = is_major_tick(y, y_origin, major_spacing)
        if is_major or params.minor_ticks:
            tick_length = major_length if is_major else minor_length

            new_items = create_engraved_line(
                (local_x_min, y),
                (local_x_min + tick_length, y),
                "left",
                domain,
                params.depth_mm,
                shape_id_prefix,
                item_index,
            )
            items.extend(new_items)
            item_index += len(new_items)

            new_items = create_engraved_line(
                (local_x_max, y),
                (local_x_max - tick_length, y),
                "right",
                domain,
                params.depth_mm,
                shape_id_prefix,
                item_index,
            )
            items.extend(new_items)
            item_index += len(new_items)

        if is_major:
            value = round(y - y_origin)
            skip_corner = first_y_major and value == 0
            if (
                value >= 0
                and not skip_corner
                and params.labels
                and should_label(value, params.label_start, label_spacing)
            ):
                new_items = create_label_items(
                    (local_x_min - label_offset, y),
                    value,
                    "vertical",
                    domain,
                    params.depth_mm,
                    params.label_height_mm,
                    shape_id_prefix,
                    label_index,
                    "center",
                    "bottom",
                )
                items.extend(new_items)
                label_index += 1

                new_items = create_label_items(
                    (local_x_max + label_offset, y),
                    value,
                    "vertical",
                    domain,
                    params.depth_mm,
                    params.label_height_mm,
                    shape_id_prefix,
                    label_index,
                    "center",
                    "top",
                )
                items.extend(new_items)
                label_index += 1
            first_y_major = False

        y += minor_spacing

    validate_items_generated(items, allow_empty, "MeasurementGridGenerator")

    return items


__all__ = ["measurement_grid_generator"]
