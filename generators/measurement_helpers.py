from __future__ import annotations

from typing import TYPE_CHECKING

from core.geometry import clip_line_to_domain
from domains.transforms import local_to_sheet_batch
from generators.area.engrave_text import engrave_number_label
from generators.core import generate_shape_id
from generators.utils import create_line_item
from layout_ast.layout import Item

if TYPE_CHECKING:
    from domains import Domain


def create_engraved_line(
    start_local: tuple[float, float],
    end_local: tuple[float, float],
    suffix: str,
    domain: Domain,
    depth_mm: float,
    shape_id_prefix: str,
    item_index: int,
) -> list[Item]:
    sheet_points = local_to_sheet_batch([start_local, end_local], domain)
    sheet_start, sheet_end = sheet_points[0], sheet_points[1]

    clipped = clip_line_to_domain(sheet_start, sheet_end, domain)

    items: list[Item] = []
    for seg_start, seg_end in clipped:
        item = create_line_item(
            start=seg_start,
            end=seg_end,
            depth_mm=depth_mm,
            shape_id=generate_shape_id(shape_id_prefix, item_index + len(items), suffix),
        )
        items.append(item)

    return items


def should_label(value: int, label_start: int, label_spacing: int) -> bool:
    if value < label_start:
        return False
    return (value - label_start) % label_spacing == 0


def create_label_items(
    local_pos: tuple[float, float],
    value: int,
    orientation: str,
    domain: Domain,
    depth_mm: float,
    label_height_mm: float,
    shape_id_prefix: str,
    label_index: int,
    alignment: str = "center",
    vertical_alignment: str = "center",
) -> list[Item]:
    sheet_pos = local_to_sheet_batch([local_pos], domain)[0]
    return engrave_number_label(
        value=value,
        position=sheet_pos,
        height_mm=label_height_mm,
        depth_mm=depth_mm,
        alignment=alignment,
        vertical_alignment=vertical_alignment,
        orientation=orientation,
        shape_id_prefix=f"{shape_id_prefix}_label_{label_index}",
    )


def compute_label_offset(
    major_length: float,
    label_height_mm: float,
    label_offset_mm: float | None,
) -> float:
    if label_offset_mm is not None:
        return label_offset_mm
    return major_length + label_height_mm * 0.8


def validate_items_generated(
    items: list[Item],
    allow_empty: bool,
    generator_name: str,
) -> None:
    if not items and not allow_empty:
        raise ValueError(
            f"{generator_name}: Could not generate any tick marks. Domain may be too small for the specified spacing."
        )


__all__ = [
    "compute_label_offset",
    "create_engraved_line",
    "create_label_items",
    "should_label",
    "validate_items_generated",
]
