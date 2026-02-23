from __future__ import annotations

import math

from HersheyFonts import HersheyFonts

from generators.core import (
    GeneratorResult,
    generate_shape_id,
)
from generators.utils import create_line_item
from layout_ast.layout import Item

HERSHEY_CAP_LINE = -12
HERSHEY_BASE_LINE = 9
HERSHEY_HEIGHT = HERSHEY_BASE_LINE - HERSHEY_CAP_LINE


def _get_font_instance(font_name: str) -> HersheyFonts:
    hf = HersheyFonts()
    try:
        hf.load_default_font(font_name)
    except Exception:
        hf.load_default_font("rowmans")
    return hf


def _get_text_lines(
    text: str,
    height_mm: float,
    font_name: str,
    spacing_factor: float = 1.0,
) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    hf = _get_font_instance(font_name)

    scale = height_mm / HERSHEY_HEIGHT
    hf.render_options["scalex"] = scale
    hf.render_options["scaley"] = scale
    hf.render_options["spacing"] = int((spacing_factor - 1.0) * 5)

    raw_lines = list(hf.lines_for_text(text))
    return [((x1, -y1), (x2, -y2)) for (x1, y1), (x2, y2) in raw_lines]


def _get_text_bounds(
    lines: list[tuple[tuple[float, float], tuple[float, float]]]
) -> tuple[float, float, float, float]:
    if not lines:
        return (0.0, 0.0, 0.0, 0.0)

    all_x = []
    all_y = []
    for (x1, y1), (x2, y2) in lines:
        all_x.extend([x1, x2])
        all_y.extend([y1, y2])

    return (min(all_x), min(all_y), max(all_x), max(all_y))


def _transform_lines(
    lines: list[tuple[tuple[float, float], tuple[float, float]]],
    offset_x: float,
    offset_y: float,
    rotation_rad: float = 0.0,
) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    if rotation_rad == 0.0:
        return [
            ((x1 + offset_x, y1 + offset_y), (x2 + offset_x, y2 + offset_y))
            for (x1, y1), (x2, y2) in lines
        ]

    cos_r = math.cos(rotation_rad)
    sin_r = math.sin(rotation_rad)

    transformed = []
    for (x1, y1), (x2, y2) in lines:
        rx1 = x1 * cos_r - y1 * sin_r + offset_x
        ry1 = x1 * sin_r + y1 * cos_r + offset_y
        rx2 = x2 * cos_r - y2 * sin_r + offset_x
        ry2 = x2 * sin_r + y2 * cos_r + offset_y
        transformed.append(((rx1, ry1), (rx2, ry2)))

    return transformed


def engrave_text_at_position(
    text: str,
    position: tuple[float, float],
    height_mm: float,
    depth_mm: float,
    font: str = "rowmans",
    alignment: str = "left",
    vertical_alignment: str = "center",
    orientation: str = "horizontal",
    spacing_factor: float = 1.0,
    shape_id_prefix: str = "text",
) -> GeneratorResult:
    if not text:
        return []

    lines = _get_text_lines(text, height_mm, font, spacing_factor)
    if not lines:
        return []

    x_min, y_min, x_max, y_max = _get_text_bounds(lines)
    text_width = x_max - x_min
    text_height = y_max - y_min

    if alignment == "left":
        align_offset_x = -x_min
    elif alignment == "center":
        align_offset_x = -x_min - text_width / 2
    else:
        align_offset_x = -x_max

    if vertical_alignment == "top":
        align_offset_y = -y_max
    elif vertical_alignment == "center":
        align_offset_y = -y_min - text_height / 2
    else:
        align_offset_y = -y_min

    aligned = _transform_lines(
        lines,
        offset_x=align_offset_x,
        offset_y=align_offset_y,
        rotation_rad=0.0,
    )

    rotation_rad = -math.pi / 2 if orientation == "vertical" else 0.0

    final_lines = _transform_lines(
        aligned,
        offset_x=position[0],
        offset_y=position[1],
        rotation_rad=rotation_rad,
    )

    items: list[Item] = []
    for i, ((x1, y1), (x2, y2)) in enumerate(final_lines):
        item = create_line_item(
            start=(x1, y1),
            end=(x2, y2),
            depth_mm=depth_mm,
            shape_id=generate_shape_id(shape_id_prefix, i),
        )
        items.append(item)

    return items


def engrave_number_label(
    value: int,
    position: tuple[float, float],
    height_mm: float,
    depth_mm: float,
    alignment: str = "center",
    vertical_alignment: str = "center",
    orientation: str = "horizontal",
    shape_id_prefix: str = "label",
) -> GeneratorResult:
    return engrave_text_at_position(
        text=str(value),
        position=position,
        height_mm=height_mm,
        depth_mm=depth_mm,
        font="rowmans",
        alignment=alignment,
        vertical_alignment=vertical_alignment,
        orientation=orientation,
        spacing_factor=1.0,
        shape_id_prefix=shape_id_prefix,
    )


__all__ = [
    "engrave_text_at_position",
    "engrave_number_label",
]
