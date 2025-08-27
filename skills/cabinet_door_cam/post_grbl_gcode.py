# path: cliff_ai/skills/cabinet_door_cam/post_grbl_gcode.py
# desc: Convert a JobPlan into GRBL-safe G-code text with deterministic formatting.
# api: post_grbl_gcode(cfg: MergedConfig, job: JobPlan) -> str
# tags: gcode, post, grbl, formatting

from __future__ import annotations
from typing import Optional, List
from skills.cabinet_door_cam.types import MergedConfig, JobPlan, Move
from skills.cabinet_door_cam.util import round_mm

def _fmt_num(v: float, prec: int) -> str:
    q = 10 ** prec
    return f"{round(v * q) / q:.{prec}f}"

def _emit_header(cfg: MergedConfig, lines: List[str]) -> None:
    # Best-guess GRBL modal block (editable in settings.py via cfg.grbl_header)
    lines.append(f"(post: grbl, units: mm, prec: {cfg.machine.post_precision})")
    lines.append(f"({cfg.grbl_header})")
    lines.append(cfg.grbl_header)

def _emit_footer(lines: List[str]) -> None:
    lines.append("M5")   # spindle stop
    lines.append("M9")   # coolant off
    lines.append("G0 X0 Y0")
    lines.append("M2")   # program end

def _word(axis: str, val: Optional[float], prec: int) -> str:
    return f"{axis}{_fmt_num(val, prec)}" if val is not None else ""

def _line_g0(x: Optional[float], y: Optional[float], z: Optional[float], prec: int) -> str:
    parts = ["G0"]
    if x is not None: parts.append(_word("X", x, prec))
    if y is not None: parts.append(_word("Y", y, prec))
    if z is not None: parts.append(_word("Z", z, prec))
    return " ".join(parts)

def _line_g1(x: Optional[float], y: Optional[float], z: Optional[float], f: Optional[float], prec: int) -> str:
    parts = ["G1"]
    if x is not None: parts.append(_word("X", x, prec))
    if y is not None: parts.append(_word("Y", y, prec))
    if z is not None: parts.append(_word("Z", z, prec))
    if f is not None: parts.append(f"F{_fmt_num(f, 1)}")  # feed uses 0.1 precision per settings
    return " ".join(parts)

def post_grbl_gcode(cfg: MergedConfig, job: JobPlan) -> str:
    """Return the complete G-code program as a single string."""
    prec = cfg.machine.post_precision
    lines: List[str] = [f"(job: {job.name}, face: {job.face}, tool: {job.tool.tool_id})"]
    _emit_header(cfg, lines)

    current_f: Optional[float] = None
    current_s: Optional[int] = None
    safe_z = cfg.order.safe_z_override_mm or cfg.machine.safe_z_mm

    # Ensure we start safe
    lines.append(_line_g0(None, None, safe_z, prec))

    for m in job.moves:
        k = m.kind
        if k == "comment":
            if m.text:
                lines.append(f"({m.text})")
            continue

        if k == "set_feed":
            # We'll only change when value differs to keep code tidy.
            if m.f is not None and m.f != current_f:
                current_f = m.f
                # Use a no-op G1 feed update line
                lines.append(_line_g1(None, None, None, current_f, prec))
            continue

        if k == "set_spindle":
            if m.s is not None and m.s != current_s:
                current_s = int(m.s)
                lines.append(f"S{current_s}")
                lines.append("M3")  # CW
            continue

        if k == "rapid":
            lines.append(_line_g0(m.x, m.y, m.z, prec))
            continue

        if k == "plunge":
            # plunge uses G1 at current feed
            lines.append(_line_g1(None, None, m.z, current_f, prec))
            continue

        if k == "cut":
            lines.append(_line_g1(m.x, m.y, m.z, current_f, prec))
            continue

        if k == "retract":
            lines.append(_line_g0(None, None, m.z if m.z is not None else safe_z, prec))
            continue

        # Unknown kinds are emitted as comments for safety
        lines.append(f"(unhandled move kind: {k})")

    # End safely
    if lines[-1] != _line_g0(None, None, safe_z, prec):
        lines.append(_line_g0(None, None, safe_z, prec))
    _emit_footer(lines)
    return "\n".join(lines) + "\n"
