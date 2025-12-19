"""STEP/STL export helpers built on the native CAD backend."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Tuple

import copy

from cad.native import core as native_core


@dataclass(frozen=True)
class SheetSpec:
    width_mm: float
    height_mm: float
    thickness_mm: float


def _sheet_to_dict(spec: SheetSpec) -> Dict[str, float]:
    return {
        "width_mm": float(spec.width_mm),
        "height_mm": float(spec.height_mm),
        "thickness_mm": float(spec.thickness_mm),
    }


def _center_shapes_on_sheet(sheet: SheetSpec, shapes: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Return deep-copied shapes shifted so the sheet centre maps to (0,0).

    Notes:
      - We must translate both placement centers AND embedded polyline geometry points
        to keep engraves aligned with pockets/profiles after recentring.
    """

    offset_x = float(sheet.width_mm) * 0.5
    offset_y = float(sheet.height_mm) * 0.5
    centered: List[Dict[str, Any]] = []

    for shape in shapes:
        item = copy.deepcopy(shape)

        # Shift placement center if present
        placement = item.get("placement")
        if isinstance(placement, Mapping):
            centre = placement.get("center_xy_mm")
            if isinstance(centre, (list, tuple)) and len(centre) == 2:
                new_centre = (float(centre[0]) - offset_x, float(centre[1]) - offset_y)
                updated = dict(placement)
                updated["center_xy_mm"] = new_centre
                item["placement"] = updated

        # Shift polyline geometry points as well so engraves remain aligned
        shape_type = str(item.get("type") or item.get("shape") or "").lower()
        if shape_type == "polyline":
            geom = item.get("geometry") or {}
            pts = geom.get("points")
            if isinstance(pts, list):
                shifted: List[Tuple[float, float]] = []
                for pt in pts:
                    if isinstance(pt, (list, tuple)) and len(pt) == 2:
                        shifted.append((float(pt[0]) - offset_x, float(pt[1]) - offset_y))
                if shifted:
                    new_geom = dict(geom)
                    new_geom["points"] = shifted
                    item["geometry"] = new_geom

        centered.append(item)

    return centered


def build_step_solids(
    sheet: SheetSpec,
    shapes: Iterable[Dict[str, Any]],
    *,
    kerf_mm: float | None = None,
    include_floating_parts: bool = True,
) -> Tuple[native_core.Solid, List[native_core.Solid]]:
    """Return the sheet solid and floating parts using the native exporter."""

    centered_shapes = _center_shapes_on_sheet(sheet, shapes)
    model = native_core.build_model(
        _sheet_to_dict(sheet),
        centered_shapes,
        kerf_mm=kerf_mm,
        include_floating_parts=include_floating_parts,
    )
    return model.sheet, list(model.parts)


def export_stl(
    sheet: SheetSpec,
    shapes: Iterable[Dict[str, Any]],
    output_path: Path,
    *,
    kerf_mm: float | None = None,
    include_sheet: bool = False,
    include_floating_parts: bool = True,
    mesh_tolerance_mm: float = 0.3,
    angular_tolerance_deg: float = 5.0,
) -> List[Path]:
    """Generate ASCII STL files via the native exporter."""

    centered_shapes = _center_shapes_on_sheet(sheet, shapes)
    return native_core.export_stl(
        _sheet_to_dict(sheet),
        centered_shapes,
        output_path,
        kerf_mm=kerf_mm,
        include_sheet=include_sheet,
        include_floating_parts=include_floating_parts,
        mesh_tolerance_mm=mesh_tolerance_mm,
        angular_tolerance_deg=angular_tolerance_deg,
    )


def export_step(
    sheet: SheetSpec,
    shapes: Iterable[Dict[str, Any]],
    output_path: Path,
    *,
    kerf_mm: float | None = None,
    include_floating_parts: bool = True,
) -> None:
    """Export a STEP-like manifest using the native exporter."""

    centered_shapes = _center_shapes_on_sheet(sheet, shapes)
    native_core.export_step(
        _sheet_to_dict(sheet),
        centered_shapes,
        output_path,
        kerf_mm=kerf_mm,
        include_floating_parts=include_floating_parts,
    )


__all__ = ["SheetSpec", "build_step_solids", "export_stl", "export_step"]
