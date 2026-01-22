from __future__ import annotations

from typing import TYPE_CHECKING

from cam.native import core as native_core

if TYPE_CHECKING:
    from cam.model.machine import Machine

DEFAULT_HEADER = ['(begin)', 'G90', 'G21', 'G17', 'G94']
DEFAULT_FOOTER = ['M5', 'M2', '(end)']


def _extract_and_strip_first_rpm(moves) -> tuple[float | None, list]:
    first_rpm = None
    result = []
    for move in moves:
        if first_rpm is None and isinstance(move, dict) and move.get('kind') == 'set_rpm':
            first_rpm = move.get('rpm')
        else:
            result.append(move)
    return first_rpm, result


def write_gcode(
    moves,
    *,
    unit: str = 'mm',
    prec: int = 3,
    safe_z: float = 5.0,
    header=None,
    footer=None,
    machine: Machine | None = None,
):
    if unit not in ('mm', 'inch'):
        raise ValueError("unit must be 'mm' or 'inch'")

    effective_header = header
    effective_moves = moves

    if machine is not None and header is None:
        first_rpm, effective_moves = _extract_and_strip_first_rpm(moves)
        effective_header = machine.build_header(
            unit=unit,
            safe_z=safe_z,
            prec=prec,
            first_rpm=first_rpm,
        )

    return native_core.post_gcode(
        effective_moves,
        unit=unit,
        prec=prec,
        safe_z=safe_z,
        header=None if effective_header is None else effective_header,
        footer=None if footer is None else footer,
    )
