from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from math import isfinite
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
    from config.machine_loader import MachineConfig

DEFAULT_HEADER = ["(begin)", "G90", "G21", "G17", "G94"]
DEFAULT_FOOTER = ["M5", "M2", "(end)"]
WORK_COORD_SYSTEMS = frozenset({"G54", "G55", "G56", "G57", "G58", "G59"})


class ParkingError(ValueError):
    pass


@dataclass(frozen=True)
class ParkingRequest:
    work_offset_mm: tuple[float, float, float] | None = None
    z_mm: float | None = None


def _program_exit(lines: Sequence[str]) -> tuple[float, float, float]:
    position: dict[str, float] = {}
    for line in reversed(lines):
        words = line.split()
        if not words or words[0] not in {"G0", "G1"}:
            continue
        for word in words[1:]:
            axis = word[0]
            if axis in "XYZ" and axis not in position:
                position[axis] = float(word[1:])
        if len(position) == 3:
            return position["X"], position["Y"], position["Z"]
    raise ParkingError("Parking requires a known program exit on X, Y and Z")


def _park_program(
    program: str,
    footer: Sequence[str],
    parking: ParkingRequest,
    machine_config: MachineConfig | None,
    *,
    safe_z: float,
    prec: int,
) -> str:
    if machine_config is None:
        raise ParkingError("Parking requires a selected machine profile with a signed XYZ envelope")
    offset = parking.work_offset_mm
    if offset is None or len(offset) != 3 or not all(isfinite(value) for value in offset):
        raise ParkingError(f"Parking requires --work-offset X Y Z with three finite values in mm, got {offset}")

    machine = machine_config.machine
    z_min, z_max = machine.envelope_z_min, machine.envelope_z_max
    if z_min is None or z_max is None:
        raise ParkingError(f"{machine.name}: parking requires signed envelope.z_min and envelope.z_max in mm")
    park_z = parking.z_mm if parking.z_mm is not None else machine_config.defaults.park_z_mm
    if park_z is None or not isfinite(park_z):
        raise ParkingError(
            f"{machine.name}: set a finite park height with defaults.park_z_mm or --park-z, got {park_z}"
        )

    park_word = f"{park_z:.{prec}f}"
    park_height = float(park_word)
    footer_text = "\n".join(footer) + "\n"
    if not program.endswith(footer_text):
        raise ParkingError("Parking requires a known program footer")
    body = program.removesuffix(footer_text)
    exit_position = _program_exit(body.splitlines())
    min_height = max(safe_z, exit_position[2])
    if park_height < min_height:
        raise ParkingError(
            f"{machine.name}: parking requires work Z >= {min_height:g} mm at the program exit, got {park_word} mm"
        )

    bounds = (
        ("X", machine.envelope_x_min, machine.envelope_x_max),
        ("Y", machine.envelope_y_min, machine.envelope_y_max),
        ("Z", z_min, z_max),
    )
    for label, point in (("return start", exit_position), ("target", (0.0, 0.0, park_height))):
        for (axis, low, high), work, origin in zip(bounds, point, offset, strict=True):
            resolved = work + origin
            if not (isfinite(low) and isfinite(high) and low <= resolved <= high):
                raise ParkingError(
                    f"{machine.name}: parking {label} work {axis}{work:g} resolves to machine {axis}{resolved:g} mm, "
                    f"outside envelope [{low:g}, {high:g}] mm"
                )

    zero = f"{0:.{prec}f}"
    return f"{body}G0 Z{park_word}\nG0 X{zero} Y{zero}\n{footer_text}"


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
    header: Sequence[str] | None = None,
    footer: Sequence[str] | None = None,
    machine: Machine | None = None,
    sheet_height: float | None = None,
    y_origin: str = "back",
    margin_mm: float = 0.0,
    parking: ParkingRequest | None = None,
    machine_config: MachineConfig | None = None,
) -> str:
    if unit not in ("mm", "inch"):
        raise ValueError("unit must be 'mm' or 'inch'")
    if y_origin not in ("front", "back"):
        raise ValueError("y_origin must be 'front' or 'back'")
    if y_origin == "front" and sheet_height is None:
        raise ValueError("sheet_height is required when y_origin='front'")

    effective_header = header
    if parking is not None:
        work_system = str(machine_config.controller.get("work_coord_system", "G54")) if machine_config else "G54"
        if (
            unit != "mm"
            or header is not None
            or work_system not in WORK_COORD_SYSTEMS
            or (machine is not None and (machine.work_coord_system != work_system or machine.preamble_codes))
        ):
            raise ParkingError(
                "Parking requires the standard absolute-millimeter header with the profile's G54 to G59 work system"
            )
        if machine is None:
            effective_header = [*DEFAULT_HEADER, work_system]
    effective_moves: list[Move] = list(moves)

    if machine is not None and header is None:
        first_rpm, effective_moves = _extract_and_strip_first_rpm(effective_moves)
        effective_header = machine.build_header(
            unit=unit,
            safe_z=safe_z,
            prec=prec,
            first_rpm=first_rpm,
        )

    effective_footer = footer or DEFAULT_FOOTER

    move_dicts = [
        _move_to_dict(m, margin_mm=margin_mm, sheet_height=sheet_height, y_origin=y_origin) for m in effective_moves
    ]

    program = native_core.post_gcode(
        move_dicts,
        unit=unit,
        prec=prec,
        safe_z=safe_z,
        header=None if effective_header is None else effective_header,
        footer=effective_footer,
    )
    if parking is None:
        return program
    return _park_program(program, effective_footer, parking, machine_config, safe_z=safe_z, prec=prec)
