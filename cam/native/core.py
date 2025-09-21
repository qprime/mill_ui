"""Thin Python shims for the native CAM core.

The helpers defined here map the existing Python data structures into the POD
facade exposed by ``skills.mill_ui.cam.native._native``.  Public modules never
import the extension directly; they go through these wrappers so the native
engine remains the single source of truth for toolpath generation.
"""
from __future__ import annotations

from typing import Iterable, List, Optional, Sequence, Tuple

try:  # pragma: no cover - optional native module
    from . import _native  # type: ignore[attr-defined]
except Exception:  # pragma: no cover - surface a clear error when accessed
    _native = None  # type: ignore[assignment]


def is_native_available() -> bool:
    """Return True when the compiled pybind11 extension imported successfully."""
    return _native is not None


def _require_native() -> None:
    if _native is None:  # pragma: no cover - defensive guard
        raise RuntimeError(
            "skills.mill_ui.cam.native._native is not available. Install the project "
            "with a modern C++ toolchain so the native CAM core can be built."
        )


# ---------------------------------------------------------------------------
# Shared conversions
# ---------------------------------------------------------------------------

def _poly_from_shape(shape) -> List[Tuple[float, float]]:
    return [(float(pt.x), float(pt.y)) for pt in getattr(shape, "points", [])]


def _planar_face_dict(shape, depth_mm: float, safe_z_mm: float) -> dict:
    return {
        "z": 0.0,
        "depth": float(depth_mm),
        "safe_z": float(safe_z_mm),
        "outer": _poly_from_shape(shape),
        "holes": [],
    }


def _holes_from_points(points: Iterable[Tuple[float, float]], depth_mm: float, tool_diameter: float) -> List[dict]:
    holes = []
    for x, y in points:
        holes.append({
            "x": float(x),
            "y": float(y),
            "diameter": float(tool_diameter),
            "depth": float(depth_mm),
        })
    return holes


# ---------------------------------------------------------------------------
# Native-backed planners
# ---------------------------------------------------------------------------

def pocket_raster(shape, setup, *, depth_mm: float, stepover_mm: float, stepdown_mm: Optional[float]) -> List[dict]:
    _require_native()
    face = _planar_face_dict(shape, depth_mm, setup.safe_z)
    step_down_arg = None if stepdown_mm is None else float(stepdown_mm)
    return _native.plan_pocket(face, setup.tool, float(stepover_mm), step_down_arg)


def profile_outline(shape, setup, *, depth_mm: float, stepdown_mm: float) -> List[dict]:
    _require_native()
    boundary = _poly_from_shape(shape)
    return _native.plan_profile(boundary, setup.tool, float(depth_mm), float(stepdown_mm), float(setup.safe_z))


def drill_peck(points: Sequence[Tuple[float, float]], setup, *, depth_mm: float, peck_mm: float) -> List[dict]:
    _require_native()
    holes = _holes_from_points(points, depth_mm, setup.tool.diameter)
    return _native.plan_drill(holes, setup.tool, float(peck_mm), float(setup.safe_z))


def bore_helical(center_xy: Tuple[float, float], hole_d_mm: float, setup, *, depth_mm: float,
                 stepdown_mm: float) -> List[dict]:
    _require_native()
    hole = {
        "x": float(center_xy[0]),
        "y": float(center_xy[1]),
        "diameter": float(hole_d_mm),
        "depth": float(depth_mm),
    }
    return _native.plan_bore_helical(hole, setup.tool, float(stepdown_mm), float(setup.safe_z))


def post_gcode(moves: Sequence[dict], *, unit: str = "mm", prec: int = 3, safe_z: float = 5.0,
               header: Optional[Sequence[str]] = None, footer: Optional[Sequence[str]] = None) -> str:
    """Emit G-code via the native backend."""
    _require_native()
    cfg = {
        "unit": unit,
        "prec": int(prec),
        "safe_z": float(safe_z),
    }
    if header is not None:
        cfg["header"] = list(header)
    if footer is not None:
        cfg["footer"] = list(footer)
    return _native.post_gcode(list(moves), cfg)


# ---------------------------------------------------------------------------
# Passthrough helpers exposed for completeness (not yet wired internally)
# ---------------------------------------------------------------------------

def load_step(path: str):
    _require_native()
    return _native.load_step(str(path))


def make_setup(model, tol_mm: float = 0.01):
    _require_native()
    return _native.make_setup(model, float(tol_mm))


def detect_planar(model, setup, tol_mm: float = 0.01):
    _require_native()
    return _native.detect_planar(model, setup, float(tol_mm))


def detect_holes(model, setup, tol_mm: float = 0.01):
    _require_native()
    return _native.detect_holes(model, setup, float(tol_mm))


def offset_inset(polygon: Iterable[Iterable[float]], radius_mm: float):
    _require_native()
    pts = [[float(x), float(y)] for x, y in polygon]
    return _native.offset_inset(pts, float(radius_mm))


def offset_outset(polygon: Iterable[Iterable[float]], radius_mm: float):
    _require_native()
    pts = [[float(x), float(y)] for x, y in polygon]
    return _native.offset_outset(pts, float(radius_mm))


def create_stock(minx: float, miny: float, maxx: float, maxy: float, pitch_mm: float):
    _require_native()
    return _native.create_stock(float(minx), float(miny), float(maxx), float(maxy), float(pitch_mm))


def link_keepdown(paths, safe_z: float, min_clearance: float):
    _require_native()
    return _native.link_keepdown(paths, float(safe_z), float(min_clearance))


def fit_arcs(paths, tol_mm: float):
    _require_native()
    return _native.fit_arcs(paths, float(tol_mm))
