# path: cam_generator/gcode_writer.py
# desc: Write GRBL-style G-code from moves with compact formatting
# api: write_gcode
# tags: gcode,io

from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

__all__ = ["write_gcode"]


def _fmt(v: float) -> str:
    s = f"{v:.3f}"
    s = s.rstrip("0").rstrip(".")
    return s if s else "0"


def _header(safe_z: float, spindle_rpm: int, wait_s: float) -> List[str]:
    lines = ["G21", "G90", "G94", "G17", f"G0 Z{_fmt(safe_z)}"]
    if spindle_rpm > 0:
        lines.append(f"M3 S{int(spindle_rpm)}")
    if wait_s > 0.0:
        lines.append(f"G4 P{_fmt(wait_s)}")
    return lines


def write_gcode(path: Path,
                moves: Iterable[Dict[str, float]],
                machine: Dict[str, object],
                stock: Dict[str, float],
                *,
                pass_cfg: Dict[str, object] | None = None) -> None:
    """
    Minimal, side-effect-free G-code writer.
    - Ignores unknown fields in moves.
    - Writes only changes (modal & coordinate de-dup).
    - Always starts and ends at safe Z.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    safe_z = float(stock["safe_z_mm"])
    offsets = machine.get("work_offset_mm", {}) if isinstance(machine, dict) else {}
    offset_x = float(offsets.get("x", 0.0) or 0.0)
    offset_y = float(offsets.get("y", 0.0) or 0.0)
    offset_z = float(offsets.get("z", 0.0) or 0.0)
    safe_z += offset_z

    wait_s = 5.0
    spindle_rpm = 0
    if isinstance(machine, dict):
        try:
            wait_s = float(machine.get("spindle_wait_s", wait_s))
        except Exception:
            wait_s = 5.0
        try:
            spindle_rpm = int(float(machine.get("spindle_rpm", spindle_rpm)))
        except Exception:
            spindle_rpm = 0

    if pass_cfg:
        try:
            spindle_rpm = int(float(pass_cfg.get("spindle_rpm", spindle_rpm)))
        except Exception:
            pass

    move_list = list(moves)

    processed: List[Tuple[int, Optional[float], Optional[float], Optional[float], Optional[int]]] = []
    min_x: Optional[float] = None
    min_y: Optional[float] = None

    for m in move_list:
        mode = int(m["mode"])
        x = float(m.get("x")) + offset_x if "x" in m else None
        y = float(m.get("y")) + offset_y if "y" in m else None
        z = float(m.get("z")) + offset_z if "z" in m else None
        f = int(m.get("f")) if "f" in m else None
        processed.append((mode, x, y, z, f))
        if x is not None:
            min_x = x if min_x is None else min(min_x, x)
        if y is not None:
            min_y = y if min_y is None else min(min_y, y)

    shift_x = 0.0
    if min_x is not None and min_x < offset_x:
        shift_x = offset_x - min_x

    shift_y = 0.0
    if min_y is not None and min_y < offset_y:
        shift_y = offset_y - min_y

    lines: List[str] = _header(safe_z, spindle_rpm, wait_s)

    last_mode = None
    last_x = last_y = last_z = None
    last_f = None

    for mode, x, y, z, f in processed:
        x_out = None if x is None else x + shift_x
        y_out = None if y is None else y + shift_y
        z_out = None if z is None else z

        parts: List[str] = []

        if mode != last_mode:
            parts.append("G0" if mode == 0 else "G1")
            last_mode = mode

        if x_out is not None and (last_x is None or abs(x_out - last_x) > 1e-9):
            parts.append(f"X{_fmt(x_out)}"); last_x = x_out
        if y_out is not None and (last_y is None or abs(y_out - last_y) > 1e-9):
            parts.append(f"Y{_fmt(y_out)}"); last_y = y_out
        if z_out is not None and (last_z is None or abs(z_out - last_z) > 1e-9):
            parts.append(f"Z{_fmt(z_out)}"); last_z = z_out

        if mode == 1 and f is not None and (last_f is None or f != last_f):
            parts.append(f"F{f}")
            last_f = f

        if not parts:
            parts.append(f"Z{_fmt(last_z if last_z is not None else safe_z)}")

        lines.append(" ".join(parts))

    if last_z is None or abs(last_z - safe_z) > 1e-9:
        lines.append(f"G0 Z{_fmt(safe_z)}")

    origin_x = _fmt(offset_x + shift_x)
    origin_y = _fmt(offset_y + shift_y)
    lines.append(f"G0 X{origin_x} Y{origin_y}")
    lines.append(f"G0 Z{_fmt(safe_z)}")

    if spindle_rpm > 0:
        lines.append("M5")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
