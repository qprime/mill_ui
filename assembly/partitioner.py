from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from assembly.panel import PanelSpec

_PANEL_ID_SEP = "::"


@dataclass(frozen=True)
class PartitionResult:
    sheets: tuple[tuple[PanelSpec, ...], ...]
    unplaceable: tuple[PanelSpec, ...]


def encode_panel_id(index: int, name: str) -> str:
    return f"{index}{_PANEL_ID_SEP}{name}"


def decode_panel_id(encoded: str) -> tuple[int, str]:
    sep_pos = encoded.index(_PANEL_ID_SEP)
    return int(encoded[:sep_pos]), encoded[sep_pos + len(_PANEL_ID_SEP) :]


def partition_panels(
    panels: list[PanelSpec],
    usable_width_mm: float,
    usable_height_mm: float,
    gap_mm: float = 10.0,
    edge_clearance_mm: float = 0.0,
) -> PartitionResult:
    from nesting.sheet_packer import pack_sheets
    from nesting.types import PartSpec, SheetSpec

    part_specs: list[PartSpec] = []
    panel_by_id: dict[int, PanelSpec] = {}

    for idx, panel in enumerate(panels):
        encoded = encode_panel_id(idx, panel.name)
        ps = PartSpec(
            name=encoded,
            width_mm=panel.width_mm + gap_mm,
            height_mm=panel.height_mm + gap_mm,
            quantity=1,
            allow_rotation=False,
        )
        part_specs.append(ps)
        panel_by_id[id(ps)] = panel

    sheet_spec = SheetSpec(
        width_mm=usable_width_mm,
        height_mm=usable_height_mm,
        thickness_mm=1.0,
        margin_mm=edge_clearance_mm,
        kerf_mm=0.0,
    )

    result = pack_sheets(part_specs, sheet_spec)

    sheets: list[tuple[PanelSpec, ...]] = []
    for sheet_layout in result.sheets:
        group: list[PanelSpec] = []
        for nested_part in sheet_layout.placements:
            original = panel_by_id[id(nested_part.part_spec)]
            group.append(original)
        sheets.append(tuple(group))

    unplaceable: list[PanelSpec] = []
    for unplaced in result.unplaced_parts:
        found = panel_by_id.get(id(unplaced))
        if found is not None:
            unplaceable.append(found)
        else:
            idx, _name = decode_panel_id(unplaced.name)
            unplaceable.append(panels[idx])

    return PartitionResult(
        sheets=tuple(sheets),
        unplaceable=tuple(unplaceable),
    )
