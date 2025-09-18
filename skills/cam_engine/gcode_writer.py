# path: cam_generator/gcode_writer.py
# desc: Write GRBL-style G-code from moves with compact formatting
# api: write_gcode
# tags: gcode,io

from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, List

__all__ = ["write_gcode"]

def _fmt(v: float) -> str:
    s = f"{v:.3f}"
    s = s.rstrip("0").rstrip(".")
    return s if s else "0"

def _header(machine: Dict[str, object], safe_z: float) -> List[str]:
    # G21 mm, G90 absolute, G94 feed per minute, G17 XY plane, retract to safe Z
    return ["G21", "G90", "G94", "G17", f"G0 Z{_fmt(safe_z)}"]

def write_gcode(path: Path,
                moves: Iterable[Dict[str, float]],
                machine: Dict[str, object],
                stock: Dict[str, float]) -> None:
    """
    Minimal, side-effect-free G-code writer.
    - Ignores unknown fields in moves.
    - Writes only changes (modal & coordinate de-dup).
    - Always starts and ends at safe Z.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    safe_z = float(stock["safe_z_mm"])
    lines: List[str] = _header(machine, safe_z)

    last_mode = None
    last_x = last_y = last_z = None
    last_f = None

    for m in moves:
        mode = int(m["mode"])
        x = float(m.get("x")) if "x" in m else None
        y = float(m.get("y")) if "y" in m else None
        z = float(m.get("z")) if "z" in m else None
        f = int(m.get("f")) if "f" in m else None

        parts: List[str] = []

        if mode != last_mode:
            parts.append("G0" if mode == 0 else "G1")
            last_mode = mode

        if x is not None and (last_x is None or abs(x - last_x) > 1e-9):
            parts.append(f"X{_fmt(x)}"); last_x = x
        if y is not None and (last_y is None or abs(y - last_y) > 1e-9):
            parts.append(f"Y{_fmt(y)}"); last_y = y
        if z is not None and (last_z is None or abs(z - last_z) > 1e-9):
            parts.append(f"Z{_fmt(z)}"); last_z = z

        if mode == 1 and f is not None and (last_f is None or f != last_f):
            parts.append(f"F{f}")
            last_f = f

        if not parts:
            # Force a Z emit (harmless no-op) to avoid blank lines
            parts.append(f"Z{_fmt(last_z if last_z is not None else safe_z)}")

        lines.append(" ".join(parts))

    # Always retract to safe Z at end
    if last_z is None or abs(last_z - safe_z) > 1e-9:
        lines.append(f"G0 Z{_fmt(safe_z)}")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
