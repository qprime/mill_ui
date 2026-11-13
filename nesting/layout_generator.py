from __future__ import annotations

from dataclasses import replace

from layout_ast.layout import LayoutAST, Sheet
from pml.lifter import lift_layout_ast
from pml.yaml_formatter import format_pml_yaml

from .template_expander import placement_to_items
from .types import NestingResult, SheetLayout


def sheet_layout_to_ast(sheet_layout: SheetLayout) -> LayoutAST:
    sheet_spec = sheet_layout.sheet_spec

    sheet = Sheet(
        width_mm=sheet_spec.width_mm,
        height_mm=sheet_spec.height_mm,
        thickness_mm=sheet_spec.thickness_mm,
        margin_mm=sheet_spec.margin_mm,
    )

    all_items = []
    for placement in sheet_layout.placements:
        items = placement_to_items(placement, sheet_spec.thickness_mm)
        for item in items:
            if item.placement is None:
                raise ValueError(f"Nested item {item.shape_id} is missing its placement")
            x, y = item.placement.center_xy_mm
            working_placement = replace(
                item.placement, center_xy_mm=(x - sheet_spec.margin_mm, y - sheet_spec.margin_mm)
            )
            all_items.append(replace(item, placement=working_placement))

    return LayoutAST(
        sheet=sheet,
        items=tuple(all_items),
        kerf_width_mm=sheet_spec.kerf_mm,
    )


def nesting_result_to_asts(result: NestingResult) -> list[LayoutAST]:
    return [sheet_layout_to_ast(sheet) for sheet in result.sheets]


def sheet_layout_to_pml(sheet_layout: SheetLayout) -> str:
    ast = sheet_layout_to_ast(sheet_layout)
    return format_pml_yaml(lift_layout_ast(ast))


def nesting_result_to_pml(result: NestingResult) -> list[str]:
    return [sheet_layout_to_pml(sheet) for sheet in result.sheets]


__all__ = [
    "nesting_result_to_asts",
    "nesting_result_to_pml",
    "sheet_layout_to_ast",
    "sheet_layout_to_pml",
]
