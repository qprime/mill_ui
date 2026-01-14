"""High-level API for sheet nesting.

This module provides the main entry point for nesting operations.
"""

from __future__ import annotations

from typing import Any

from .types import PartSpec, SheetSpec, NestingResult
from .sheet_packer import pack_sheets, PackingAlgorithm, DEFAULT_ALGORITHM
from .layout_generator import nesting_result_to_asts, nesting_result_to_pml
from .validation import validate_nesting_result

_VALID_OUTPUT_FORMATS = ("ast", "pml")
_VALID_ALGORITHMS = ("guillotine", "maxrects")


def _parts_from_dicts(parts: list[dict[str, Any]]) -> list[PartSpec]:
    """Convert list of part dicts to PartSpec objects.

    Args:
        parts: List of part specification dicts

    Returns:
        List of PartSpec objects
    """
    return [
        PartSpec(
            name=p["name"],
            width_mm=float(p["width_mm"]),
            height_mm=float(p["height_mm"]),
            quantity=int(p.get("quantity", 1)),
            template=p.get("template"),
            template_params=p.get("template_params"),
            allow_rotation=p.get("allow_rotation", True),
        )
        for p in parts
    ]


def nest_parts(
    parts: list[dict[str, Any]],
    sheet_width_mm: float,
    sheet_height_mm: float,
    sheet_thickness_mm: float,
    margin_mm: float = 10.0,
    kerf_mm: float | None = None,
    gap_margin_mm: float = 0.0,
    max_sheets: int | None = None,
    validate: bool = True,
    algorithm: str = "maxrects",
) -> dict[str, Any]:
    """Main API for nesting parts onto sheets.

    Args:
        parts: List of part specifications as dicts:
            {
                "name": str,           # Required
                "width_mm": float,     # Required
                "height_mm": float,    # Required
                "quantity": int,       # Default: 1
                "template": str,       # Optional (e.g., "Shaker")
                "template_params": dict, # Optional
                "allow_rotation": bool, # Default: True
            }
        sheet_width_mm: Stock sheet width
        sheet_height_mm: Stock sheet height
        sheet_thickness_mm: Material thickness
        margin_mm: No-cut zone on edges (default: 10mm)
        kerf_mm: Cutter kerf width (default: 6.35mm with warning)
        gap_margin_mm: Extra margin beyond kerf (default: 0)
        max_sheets: Maximum sheets to use (None = unlimited)
        validate: Whether to validate result (default: True)
        algorithm: Packing algorithm - "maxrects" (default, better) or "guillotine"

    Returns:
        Dict with:
        {
            "sheets": [...],           # List of sheet layouts
            "total_sheets": int,
            "total_parts": int,
            "utilization": float,      # 0.0-1.0
            "unplaced": [...],         # Parts that couldn't fit
            "validation": {...} | None, # Validation result if validate=True
            "algorithm": str,          # Algorithm used
        }

    Raises:
        ValueError: If algorithm is not valid
    """
    if algorithm not in _VALID_ALGORITHMS:
        raise ValueError(
            f"Invalid algorithm '{algorithm}'. "
            f"Must be one of: {', '.join(_VALID_ALGORITHMS)}"
        )

    part_specs = _parts_from_dicts(parts)

    # Create sheet spec
    sheet_spec = SheetSpec(
        width_mm=sheet_width_mm,
        height_mm=sheet_height_mm,
        thickness_mm=sheet_thickness_mm,
        margin_mm=margin_mm,
        kerf_mm=kerf_mm,
        gap_margin_mm=gap_margin_mm,
    )

    # Pack sheets
    result = pack_sheets(part_specs, sheet_spec, max_sheets=max_sheets, algorithm=algorithm)

    # Build response
    response = {
        "sheets": [sheet.to_dict() for sheet in result.sheets],
        "total_sheets": result.total_sheets,
        "total_parts": result.total_parts,
        "utilization": result.overall_utilization,
        "utilization_percent": result.overall_utilization_percent,
        "unplaced": [p.to_dict() for p in result.unplaced_parts],
        "validation": None,
        "algorithm": algorithm,
    }

    # Optionally validate
    if validate:
        val_result = validate_nesting_result(result)
        response["validation"] = {
            "is_valid": val_result.is_valid,
            "errors": val_result.errors,
            "warnings": val_result.warnings,
        }

    return response


def nest_and_generate(
    parts: list[dict[str, Any]],
    sheet_width_mm: float,
    sheet_height_mm: float,
    sheet_thickness_mm: float,
    margin_mm: float = 10.0,
    kerf_mm: float | None = None,
    gap_margin_mm: float = 0.0,
    output_format: str = "ast",
    algorithm: str = "maxrects",
) -> dict[str, Any]:
    """Nest parts and generate output ready for CAM.

    Args:
        parts: Part specifications (see nest_parts)
        sheet_width_mm: Stock sheet width
        sheet_height_mm: Stock sheet height
        sheet_thickness_mm: Material thickness
        margin_mm: No-cut zone on edges
        kerf_mm: Cutter kerf width (default: 6.35mm with warning)
        gap_margin_mm: Extra margin beyond kerf (default: 0)
        output_format: "ast" for LayoutAST, "pml" for PML strings
        algorithm: Packing algorithm - "maxrects" (default, better) or "guillotine"

    Returns:
        Dict with nesting info plus generated output

    Raises:
        ValueError: If output_format or algorithm is not valid
    """
    if output_format not in _VALID_OUTPUT_FORMATS:
        raise ValueError(
            f"Invalid output_format '{output_format}'. "
            f"Must be one of: {', '.join(_VALID_OUTPUT_FORMATS)}"
        )

    if algorithm not in _VALID_ALGORITHMS:
        raise ValueError(
            f"Invalid algorithm '{algorithm}'. "
            f"Must be one of: {', '.join(_VALID_ALGORITHMS)}"
        )

    part_specs = _parts_from_dicts(parts)

    sheet_spec = SheetSpec(
        width_mm=sheet_width_mm,
        height_mm=sheet_height_mm,
        thickness_mm=sheet_thickness_mm,
        margin_mm=margin_mm,
        kerf_mm=kerf_mm,
        gap_margin_mm=gap_margin_mm,
    )

    # Pack
    result = pack_sheets(part_specs, sheet_spec, algorithm=algorithm)

    # Generate output
    if output_format == "pml":
        output = nesting_result_to_pml(result)
    else:
        output = nesting_result_to_asts(result)

    return {
        "nesting_result": result,
        "output": output,
        "output_format": output_format,
        "total_sheets": result.total_sheets,
        "utilization": result.overall_utilization,
        "algorithm": algorithm,
    }


__all__ = ["nest_parts", "nest_and_generate"]
