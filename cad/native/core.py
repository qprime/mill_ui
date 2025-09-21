"""Python shims for the native CAD exporter."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

try:  # pragma: no cover - optional import failure handled gracefully
    from . import _cad_native  # type: ignore[attr-defined]
except Exception:  # pragma: no cover - module not built
    _cad_native = None  # type: ignore[assignment]


@dataclass(frozen=True)
class Solid:
    kind: str
    shape: str
    width_mm: float
    height_mm: float
    thickness_mm: float
    center_xy_mm: Tuple[float, float]
    id: Optional[str] = None


@dataclass(frozen=True)
class Pocket:
    shape: str
    depth_mm: float
    center_xy_mm: Tuple[float, float]
    width_mm: float = 0.0
    height_mm: float = 0.0
    diameter_mm: float = 0.0
    id: Optional[str] = None


@dataclass(frozen=True)
class Model:
    sheet: Solid
    parts: List[Solid]
    pockets: List[Pocket]
    kerf_mm: float


def is_native_available() -> bool:
    return _cad_native is not None


def _require_native() -> None:
    if _cad_native is None:  # pragma: no cover - defensive guard
        raise RuntimeError(
            "skills.mill_ui.cad.native._cad_native is not available. Build the project with a "
            "native toolchain so the CAD exporter can run."
        )


def build_model(sheet: Dict[str, float],
                shapes: Sequence[Dict[str, object]],
                *,
                kerf_mm: Optional[float] = None,
                include_floating_parts: bool = True) -> Model:
    """Return a lightweight summary of the sheet, floating parts, and pockets."""

    _require_native()
    raw = _cad_native.build_model(sheet, list(shapes), float(kerf_mm or 0.0), bool(include_floating_parts))

    sheet_data = raw.get("sheet", {})
    center_xy = tuple(sheet_data.get("center_xy_mm", (0.0, 0.0)))
    sheet_solid = Solid(
        kind=str(sheet_data.get("kind", "sheet")),
        shape=str(sheet_data.get("shape", "rect")),
        width_mm=float(sheet_data.get("width_mm", 0.0)),
        height_mm=float(sheet_data.get("height_mm", 0.0)),
        thickness_mm=float(sheet_data.get("thickness_mm", 0.0)),
        center_xy_mm=(float(center_xy[0]), float(center_xy[1])),
        id=sheet_data.get("id"),
    )

    parts: List[Solid] = []
    for item in raw.get("parts", []):
        center_xy = tuple(item.get("center_xy_mm", (0.0, 0.0)))
        parts.append(
            Solid(
                kind=str(item.get("kind", "part")),
                shape=str(item.get("shape", "rect")),
                width_mm=float(item.get("width_mm", 0.0)),
                height_mm=float(item.get("height_mm", 0.0)),
                thickness_mm=float(item.get("thickness_mm", 0.0)),
                center_xy_mm=(float(center_xy[0]), float(center_xy[1])),
                id=item.get("id"),
            )
        )

    pockets: List[Pocket] = []
    for item in raw.get("pockets", []):
        center_xy = tuple(item.get("center_xy_mm", (0.0, 0.0)))
        pockets.append(
            Pocket(
                shape=str(item.get("shape", "rect")),
                depth_mm=float(item.get("depth_mm", 0.0)),
                center_xy_mm=(float(center_xy[0]), float(center_xy[1])),
                width_mm=float(item.get("width_mm", 0.0)),
                height_mm=float(item.get("height_mm", 0.0)),
                diameter_mm=float(item.get("diameter_mm", 0.0)),
                id=item.get("id"),
            )
        )

    return Model(sheet=sheet_solid, parts=parts, pockets=pockets, kerf_mm=float(raw.get("kerf_mm", 0.0)))


def export_stl(sheet: Dict[str, float],
               shapes: Sequence[Dict[str, object]],
               output_path: Path,
               *,
               kerf_mm: Optional[float] = None,
               include_sheet: bool = False,
               include_floating_parts: bool = True,
               mesh_tolerance_mm: float = 0.3,
               angular_tolerance_deg: float = 5.0) -> List[Path]:
    """Generate STL meshes via the native exporter and return written paths."""

    _require_native()
    # angular_tolerance kept for API compatibility (not used by native exporter yet)
    _ = angular_tolerance_deg

    written = _cad_native.export_stl(
        sheet,
        list(shapes),
        str(output_path),
        float(kerf_mm or 0.0),
        bool(include_sheet),
        bool(include_floating_parts),
        float(mesh_tolerance_mm),
    )
    return [Path(path) for path in written]


def export_step(sheet: Dict[str, float],
                shapes: Sequence[Dict[str, object]],
                output_path: Path,
                *,
                kerf_mm: Optional[float] = None,
                include_floating_parts: bool = True) -> None:
    """Emit a STEP file containing the sheet and optional floating parts."""

    _require_native()
    _cad_native.export_step(
        sheet,
        list(shapes),
        str(output_path),
        float(kerf_mm or 0.0),
        bool(include_floating_parts),
    )
