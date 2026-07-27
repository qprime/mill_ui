from __future__ import annotations

from collections.abc import Iterable, Sequence

from cam.moves import (
    CommentMove,
    CutMove,
    DwellMove,
    Move,
    RapidMove,
    RetractMove,
    SetFeedMove,
    SetRpmMove,
)

try:
    from . import _native  # type: ignore[attr-defined]
except Exception:
    _native = None


def _dict_to_move(d: dict) -> Move:
    kind = d.get("kind", "")
    if kind == "comment":
        text = d.get("text")
        return CommentMove(text=str(text) if text is not None else "")
    if kind == "set_rpm":
        rpm = d.get("rpm")
        return SetRpmMove(rpm=float(rpm) if rpm is not None else 0.0)
    if kind == "set_feed":
        feed = d.get("feed")
        return SetFeedMove(feed=float(feed) if feed is not None else 0.0)
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
        z = d.get("z")
        return RetractMove(z=float(z) if z is not None else 0.0)
    if kind == "dwell":
        seconds = d.get("seconds")
        return DwellMove(seconds=float(seconds) if seconds is not None else 0.0)
    raise ValueError(f"Unknown move kind: {kind!r}")


def is_native_available() -> bool:
    return _native is not None


def _require_native() -> None:
    if _native is None:
        raise RuntimeError(
            "cam.native._native is not available. Build the native CAM core with a "
            "modern C++ toolchain (see cam/native/README.md) before using it."
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


def pocket_raster(
    shape, setup, *, depth_mm: float, stepover_mm: float, stepdown_mm: float | None, strategy: str = "spiral"
) -> list[Move]:
    _require_native()
    face = _planar_face_dict(shape, depth_mm, setup.safe_z)
    step_down_arg = None if stepdown_mm is None else float(stepdown_mm)
    ramp = float(setup.ramp_angle_deg)
    return [
        _dict_to_move(d)
        for d in _native.plan_pocket(
            face, setup.tool, float(stepover_mm), step_down_arg, ramp_angle_deg=ramp, strategy=strategy
        )
    ]


def profile_outline(shape, setup, *, depth_mm: float, stepdown_mm: float) -> list[Move]:
    _require_native()
    boundary = _poly_from_shape(shape)
    ramp = float(setup.ramp_angle_deg)
    return [
        _dict_to_move(d)
        for d in _native.plan_profile(
            boundary,
            setup.tool,
            float(depth_mm),
            float(stepdown_mm),
            float(setup.safe_z),
            ramp_angle_deg=ramp,
        )
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
    return str(_native.post_gcode(list(moves), cfg))
