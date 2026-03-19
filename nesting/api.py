from __future__ import annotations

from typing import Any

from pml.nest_parser import HoldingSpec

from .layout_generator import nesting_result_to_asts, nesting_result_to_pml
from .sheet_packer import pack_sheets
from .types import PartSpec, SheetSpec
from .validation import validate_nesting_result

_VALID_OUTPUT_FORMATS = ("ast", "pml")
_VALID_ALGORITHMS = ("guillotine", "maxrects")


def _geometry_points_for_polygon(shape_params: dict[str, Any]) -> tuple[tuple[float, float], ...] | None:
    points = shape_params.get("points")
    if points is None:
        return None
    return tuple(tuple(pt) for pt in points)


def _holding_from_dict(raw: dict[str, Any] | None) -> HoldingSpec | None:
    if raw is None:
        return None
    return HoldingSpec.from_dict(raw)


def _parts_from_dicts(parts: list[dict[str, Any]]) -> list[PartSpec]:
    result = []
    for p in parts:
        shape = p.get("shape")
        shape_params = p.get("shape_params")
        geometry_points = None
        if shape == "Polygon" and shape_params:
            geometry_points = _geometry_points_for_polygon(shape_params)
        result.append(
            PartSpec(
                name=p["name"],
                width_mm=float(p["width_mm"]),
                height_mm=float(p["height_mm"]),
                quantity=int(p.get("quantity", 1)),
                template=p.get("template"),
                template_params=p.get("template_params"),
                allow_rotation=p.get("allow_rotation", True),
                geometry_points=geometry_points,
                shape=shape,
                shape_params=shape_params,
                holding=_holding_from_dict(p.get("holding")),
            )
        )
    return result


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
    if algorithm not in _VALID_ALGORITHMS:
        raise ValueError(f"Invalid algorithm '{algorithm}'. Must be one of: {', '.join(_VALID_ALGORITHMS)}")

    part_specs = _parts_from_dicts(parts)

    sheet_spec = SheetSpec(
        width_mm=sheet_width_mm,
        height_mm=sheet_height_mm,
        thickness_mm=sheet_thickness_mm,
        margin_mm=margin_mm,
        kerf_mm=kerf_mm,
        gap_margin_mm=gap_margin_mm,
    )

    result = pack_sheets(part_specs, sheet_spec, max_sheets=max_sheets, algorithm=algorithm)

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
    if output_format not in _VALID_OUTPUT_FORMATS:
        raise ValueError(f"Invalid output_format '{output_format}'. Must be one of: {', '.join(_VALID_OUTPUT_FORMATS)}")

    if algorithm not in _VALID_ALGORITHMS:
        raise ValueError(f"Invalid algorithm '{algorithm}'. Must be one of: {', '.join(_VALID_ALGORITHMS)}")

    part_specs = _parts_from_dicts(parts)

    sheet_spec = SheetSpec(
        width_mm=sheet_width_mm,
        height_mm=sheet_height_mm,
        thickness_mm=sheet_thickness_mm,
        margin_mm=margin_mm,
        kerf_mm=kerf_mm,
        gap_margin_mm=gap_margin_mm,
    )

    result = pack_sheets(part_specs, sheet_spec, algorithm=algorithm)

    output = nesting_result_to_pml(result) if output_format == "pml" else nesting_result_to_asts(result)

    return {
        "nesting_result": result,
        "output": output,
        "output_format": output_format,
        "total_sheets": result.total_sheets,
        "utilization": result.overall_utilization,
        "algorithm": algorithm,
    }


__all__ = ["nest_and_generate", "nest_parts"]
