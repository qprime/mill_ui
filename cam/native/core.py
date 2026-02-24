from __future__ import annotations

from collections.abc import Iterable, Sequence

from cam.moves import (
    CommentMove,
    CutMove,
    Move,
    RapidMove,
    RetractMove,
    SetFeedMove,
    SetRpmMove,
)

try:
    from . import _native
except Exception:
    _native = None


def _dict_to_move(d: dict) -> Move:
    kind = d.get("kind", "")
    if kind == "comment":
        return CommentMove(text=str(d.get("text") or ""))
    if kind == "set_rpm":
        return SetRpmMove(rpm=float(d.get("rpm") or 0.0))
    if kind == "set_feed":
        return SetFeedMove(feed=float(d.get("feed") or 0.0))
    if kind == "rapid":
        return RapidMove(
            x=None if d.get("x") is None else float(d["x"]),
            y=None if d.get("y") is None else float(d["y"]),
            z=None if d.get("z") is None else float(d["z"]),
        )
    if kind == "cut":
        return CutMove(
            x=None if d.get("x") is None else float(d["x"]),
            y=None if d.get("y") is None else float(d["y"]),
            z=None if d.get("z") is None else float(d["z"]),
            feed=None if d.get("feed") is None else float(d["feed"]),
        )
    if kind == "retract":
        return RetractMove(z=float(d.get("z") or 0.0))
    raise ValueError(f"Unknown move kind: {kind!r}")


def is_native_available() -> bool:
    return _native is not None


def _require_native() -> None:
    if _native is None:
        raise RuntimeError(
            "skills.mill_ui.cam.native._native is not available. Install the project "
            "with a modern C++ toolchain so the native CAM core can be built."
        )


def _poly_from_shape(shape) -> list[tuple[float, float]]:
    return [(float(pt.x), float(pt.y)) for pt in getattr(shape, "points", [])]


def _planar_face_dict(shape, depth_mm: float, safe_z_mm: float) -> dict:
    return {
        "z": 0.0,
        "depth": float(depth_mm),
        "safe_z": float(safe_z_mm),
        "outer": _poly_from_shape(shape),
        "holes": [],
    }


def _holes_from_points(points: Iterable[tuple[float, float]], depth_mm: float, tool_diameter: float) -> list[dict]:
    holes = []
    for x, y in points:
        holes.append(
            {
                "x": float(x),
                "y": float(y),
                "diameter": float(tool_diameter),
                "depth": float(depth_mm),
            }
        )
    return holes


def pocket_raster(shape, setup, *, depth_mm: float, stepover_mm: float, stepdown_mm: float | None) -> list[Move]:
    _require_native()
    face = _planar_face_dict(shape, depth_mm, setup.safe_z)
    step_down_arg = None if stepdown_mm is None else float(stepdown_mm)
    return [_dict_to_move(d) for d in _native.plan_pocket(face, setup.tool, float(stepover_mm), step_down_arg)]


def profile_outline(shape, setup, *, depth_mm: float, stepdown_mm: float) -> list[Move]:
    _require_native()
    boundary = _poly_from_shape(shape)
    return [
        _dict_to_move(d)
        for d in _native.plan_profile(boundary, setup.tool, float(depth_mm), float(stepdown_mm), float(setup.safe_z))
    ]


def drill_peck(points: Sequence[tuple[float, float]], setup, *, depth_mm: float, peck_mm: float) -> list[Move]:
    _require_native()
    holes = _holes_from_points(points, depth_mm, setup.tool.diameter)
    return [_dict_to_move(d) for d in _native.plan_drill(holes, setup.tool, float(peck_mm), float(setup.safe_z))]


def bore_helical(
    center_xy: tuple[float, float], hole_d_mm: float, setup, *, depth_mm: float, stepdown_mm: float
) -> list[Move]:
    _require_native()
    hole = {
        "x": float(center_xy[0]),
        "y": float(center_xy[1]),
        "diameter": float(hole_d_mm),
        "depth": float(depth_mm),
    }
    return [
        _dict_to_move(d) for d in _native.plan_bore_helical(hole, setup.tool, float(stepdown_mm), float(setup.safe_z))
    ]


def post_gcode(
    moves: Sequence[dict],
    *,
    unit: str = "mm",
    prec: int = 3,
    safe_z: float = 5.0,
    header: Sequence[str] | None = None,
    footer: Sequence[str] | None = None,
) -> str:
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


def mandelbrot_outline_fill(
    *,
    width_mm: float,
    height_mm: float,
    resolution_x: int,
    resolution_y: int,
    iterations: int = 100,
    escape_radius: float = 2.0,
    real_min: float = -2.0,
    real_max: float = 1.0,
    imag_min: float = -1.25,
    imag_max: float = 1.25,
):
    _require_native()
    return _native.mandelbrot_outline_fill(
        float(width_mm),
        float(height_mm),
        int(resolution_x),
        int(resolution_y),
        int(iterations),
        float(escape_radius),
        float(real_min),
        float(real_max),
        float(imag_min),
        float(imag_max),
    )
