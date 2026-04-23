from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

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
from cam.native import core as native_core

if TYPE_CHECKING:
    from cam.model.machine import Machine

DEFAULT_HEADER = ["(begin)", "G90", "G21", "G17", "G94"]
DEFAULT_FOOTER = ["M5", "M2", "(end)"]
DEFAULT_PARK_Z_MM = 100.0


def _move_to_dict(
    m: Move,
    margin_mm: float = 0.0,
    sheet_height: float | None = None,
    y_origin: str = "back",
) -> dict[str, Any]:
    if isinstance(m, CommentMove):
        return {"kind": "comment", "text": m.text}
    if isinstance(m, SetRpmMove):
        return {"kind": "set_rpm", "rpm": m.rpm}
    if isinstance(m, SetFeedMove):
        return {"kind": "set_feed", "feed": m.feed}
    if isinstance(m, RapidMove):
        x = None if m.x is None else m.x + margin_mm
        if m.y is None:
            y = None
        else:
            shifted = m.y + margin_mm
            y = sheet_height - shifted if y_origin == "front" and sheet_height is not None else shifted
        return {"kind": "rapid", "x": x, "y": y, "z": m.z}
    if isinstance(m, CutMove):
        x = None if m.x is None else m.x + margin_mm
        if m.y is None:
            y = None
        else:
            shifted = m.y + margin_mm
            y = sheet_height - shifted if y_origin == "front" and sheet_height is not None else shifted
        return {"kind": "cut", "x": x, "y": y, "z": m.z, "feed": m.feed}
    if isinstance(m, RetractMove):
        return {"kind": "retract", "z": m.z}
    if isinstance(m, DwellMove):
        return {"kind": "dwell", "seconds": m.seconds}
    raise ValueError(f"Unknown move type: {type(m)}")


def _extract_and_strip_first_rpm(moves: list[Move]) -> tuple[float | None, list[Move]]:
    first_rpm = None
    result: list[Move] = []
    for move in moves:
        if first_rpm is None and isinstance(move, SetRpmMove):
            first_rpm = move.rpm
        else:
            result.append(move)
    return first_rpm, result


def write_gcode(
    moves: Sequence[Move],
    *,
    unit: str = "mm",
    prec: int = 3,
    safe_z: float = 5.0,
    header=None,
    footer=None,
    machine: Machine | None = None,
    sheet_height: float | None = None,
    y_origin: str = "back",
    margin_mm: float = 0.0,
    park_z_mm: float | None = None,
):
    if unit not in ("mm", "inch"):
        raise ValueError("unit must be 'mm' or 'inch'")
    if y_origin not in ("front", "back"):
        raise ValueError("y_origin must be 'front' or 'back'")
    if y_origin == "front" and sheet_height is None:
        raise ValueError("sheet_height is required when y_origin='front'")

    effective_header = header
    effective_moves: list[Move] = list(moves)

    if machine is not None and header is None:
        first_rpm, effective_moves = _extract_and_strip_first_rpm(effective_moves)
        effective_header = machine.build_header(
            unit=unit,
            safe_z=safe_z,
            prec=prec,
            first_rpm=first_rpm,
        )

    park_z = park_z_mm if park_z_mm is not None else DEFAULT_PARK_Z_MM
    park_footer = [
        f"G0 Z{park_z:.{prec}f}",
        f"G0 X{0.0:.{prec}f} Y{0.0:.{prec}f}",
    ] + (footer or DEFAULT_FOOTER)

    move_dicts = [
        _move_to_dict(m, margin_mm=margin_mm, sheet_height=sheet_height, y_origin=y_origin) for m in effective_moves
    ]

    return native_core.post_gcode(
        move_dicts,
        unit=unit,
        prec=prec,
        safe_z=safe_z,
        header=None if effective_header is None else effective_header,
        footer=park_footer,
    )
