"""Generate LayoutAST from nesting results.

This module converts SheetLayout into LayoutAST ready for the CAM pipeline.
"""

from __future__ import annotations

from layout_ast.layout import LayoutAST, Sheet

from .types import SheetLayout, NestingResult
from .template_expander import placement_to_items


def sheet_layout_to_ast(sheet_layout: SheetLayout) -> LayoutAST:
    """Convert a SheetLayout to LayoutAST.

    Expands all placements to Items using template expansion,
    positions them on the sheet, and returns a valid LayoutAST.

    Args:
        sheet_layout: Sheet layout with placements

    Returns:
        LayoutAST ready for CAM pipeline
    """
    sheet_spec = sheet_layout.sheet_spec

    # Create Sheet from SheetSpec
    sheet = Sheet(
        width_mm=sheet_spec.width_mm,
        height_mm=sheet_spec.height_mm,
        thickness_mm=sheet_spec.thickness_mm,
    )

    # Expand all placements to Items
    all_items = []
    for placement in sheet_layout.placements:
        items = placement_to_items(placement, sheet_spec.thickness_mm)
        all_items.extend(items)

    return LayoutAST(
        sheet=sheet,
        items=tuple(all_items),
        kerf_width_mm=sheet_spec.kerf_mm,
    )


def nesting_result_to_asts(result: NestingResult) -> list[LayoutAST]:
    """Convert complete NestingResult to list of LayoutASTs.

    Args:
        result: Nesting result with multiple sheets

    Returns:
        List of LayoutASTs, one per sheet
    """
    return [sheet_layout_to_ast(sheet) for sheet in result.sheets]


def sheet_layout_to_pml(sheet_layout: SheetLayout) -> str:
    """Generate debug PML sketch from a SheetLayout.

    This outputs simple rect profiles for each placement's bounding box.
    It does NOT expand templates - use sheet_layout_to_ast() for faithful
    template expansion, then convert that AST to PML if needed.

    Args:
        sheet_layout: Sheet layout

    Returns:
        PML source string (debug sketch only)
    """
    lines = []
    spec = sheet_layout.sheet_spec

    # Sheet declaration
    lines.append(f"sheet {spec.width_mm}mm {spec.height_mm}mm {spec.thickness_mm}mm")
    lines.append("")
    lines.append(f"# Sheet {sheet_layout.sheet_index + 1}")
    lines.append(f"# Utilization: {sheet_layout.utilization_percent:.1f}%")
    lines.append(f"# Parts: {sheet_layout.part_count}")
    lines.append("")

    # Generate rect statements for each placement (bounding box only)
    for placement in sheet_layout.placements:
        part = placement.part_spec
        w = part.height_mm if placement.rotated else part.width_mm
        h = part.width_mm if placement.rotated else part.height_mm

        name = f"{part.name}_{placement.instance_id}"
        rotation_note = " (rotated)" if placement.rotated else ""

        lines.append(f"# {name}{rotation_note}")
        lines.append(
            f"rect {name} at {placement.x_mm}mm,{placement.y_mm}mm "
            f"size {w}mm,{h}mm profile through outside"
        )
        lines.append("")

    return "\n".join(lines)


def nesting_result_to_pml(result: NestingResult) -> list[str]:
    """Generate PML sources for all sheets.

    Args:
        result: Nesting result

    Returns:
        List of PML source strings, one per sheet
    """
    return [sheet_layout_to_pml(sheet) for sheet in result.sheets]


__all__ = [
    "sheet_layout_to_ast",
    "nesting_result_to_asts",
    "sheet_layout_to_pml",
    "nesting_result_to_pml",
]
