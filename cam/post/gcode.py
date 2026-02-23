from __future__ import annotations

from typing import Any, TYPE_CHECKING

from cam.native import core as native_core

if TYPE_CHECKING:
    from cam.model.machine import Machine

DEFAULT_HEADER = ['(begin)', 'G90', 'G21', 'G17', 'G94']
DEFAULT_FOOTER = ['M5', 'M2', '(end)']


def _flip_y_in_moves(moves: list[dict[str, Any]], sheet_height: float) -> list[dict[str, Any]]:
    flipped = []
    for move in moves:
        if 'y' in move and move['y'] is not None:
            flipped_move = dict(move)
            flipped_move['y'] = sheet_height - move['y']
            flipped.append(flipped_move)
        else:
            flipped.append(move)
    return flipped


def _apply_margin_offset(moves: list[dict[str, Any]], margin_mm: float) -> list[dict[str, Any]]:
    if margin_mm == 0.0:
        return moves
    offset_moves = []
    for move in moves:
        offset_move = dict(move)
        if 'x' in offset_move and offset_move['x'] is not None:
            offset_move['x'] = move['x'] + margin_mm
        if 'y' in offset_move and offset_move['y'] is not None:
            offset_move['y'] = move['y'] + margin_mm
        offset_moves.append(offset_move)
    return offset_moves


def _extract_and_strip_first_rpm(moves: list[dict[str, Any]]) -> tuple[float | None, list[dict[str, Any]]]:
    first_rpm = None
    result = []
    for move in moves:
        if first_rpm is None and move.get('kind') == 'set_rpm':
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
    sheet_height: float | None = None,
    y_origin: str = 'back',
    margin_mm: float = 0.0,
):
    if unit not in ('mm', 'inch'):
        raise ValueError("unit must be 'mm' or 'inch'")
    if y_origin not in ('front', 'back'):
        raise ValueError("y_origin must be 'front' or 'back'")
    if y_origin == 'front' and sheet_height is None:
        raise ValueError("sheet_height is required when y_origin='front'")

    effective_header = header
    effective_moves = moves

    if margin_mm != 0.0:
        effective_moves = _apply_margin_offset(effective_moves, margin_mm)

    if y_origin == 'front' and sheet_height is not None:
        effective_moves = _flip_y_in_moves(effective_moves, sheet_height)

    if machine is not None and header is None:
        first_rpm, effective_moves = _extract_and_strip_first_rpm(effective_moves)
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
