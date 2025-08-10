# path: skills/cam_generator/core/time_estimator.py
# desc: Estimate G-code cut time
# api: estimate_cut_time
# tags: cam,time

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Mapping, Optional, Union


@dataclass(frozen=True)
class Config:
    default_feedrate: float = 300.0
    include_rapids: bool = False
    fudge_factor: float = 1.15
    debug: bool = False


def _parse_move(parts: list[str], prev: dict[str, Optional[float]], current_feed: float) -> tuple[dict[str, Optional[float]], float]:
    x, y, z, feed = prev["X"], prev["Y"], prev["Z"], current_feed
    for part in parts:
        try:
            if part.startswith("X"):
                x = float(part[1:])
            elif part.startswith("Y"):
                y = float(part[1:])
            elif part.startswith("Z"):
                z = float(part[1:])
            elif part.startswith("F"):
                feed = float(part[1:])
        except ValueError:
            continue
    return {"X": x, "Y": y, "Z": z}, feed


def _dist(a: dict[str, Optional[float]], b: dict[str, Optional[float]]) -> float:
    if None in a.values() or None in b.values():
        return 0.0
    dx, dy, dz = b["X"] - a["X"], b["Y"] - a["Y"], b["Z"] - a["Z"]
    return math.sqrt(dx**2 + dy**2 + dz**2)


def _coerce_config(
    arg: Optional[Union[Config, Mapping[str, object], float, int]],
    default_feedrate: Optional[float],
    include_rapids: Optional[bool],
    fudge_factor: Optional[float],
    debug: Optional[bool],
) -> Config:
    if isinstance(arg, Config):
        base = arg
    elif isinstance(arg, Mapping):
        base = Config(
            default_feedrate=float(arg.get("default_feedrate", 300.0)),
            include_rapids=bool(arg.get("include_rapids", False)),
            fudge_factor=float(arg.get("fudge_factor", 1.15)),
            debug=bool(arg.get("debug", False)),
        )
    elif isinstance(arg, (int, float)):
        base = Config(default_feedrate=float(arg))
    else:
        base = Config()
    if isinstance(default_feedrate, (int, float)):
        base = Config(
            default_feedrate=float(default_feedrate),
            include_rapids=base.include_rapids,
            fudge_factor=base.fudge_factor,
            debug=base.debug,
        )
    if include_rapids is not None:
        base = Config(
            default_feedrate=base.default_feedrate,
            include_rapids=bool(include_rapids),
            fudge_factor=base.fudge_factor,
            debug=base.debug,
        )
    if isinstance(fudge_factor, (int, float)):
        base = Config(
            default_feedrate=base.default_feedrate,
            include_rapids=base.include_rapids,
            fudge_factor=float(fudge_factor),
            debug=base.debug,
        )
    if debug is not None:
        base = Config(
            default_feedrate=base.default_feedrate,
            include_rapids=base.include_rapids,
            fudge_factor=base.fudge_factor,
            debug=bool(debug),
        )
    return base


def estimate_cut_time(
    gcode_lines: Iterable[str],
    config_or_feed: Optional[Union[Config, Mapping[str, object], float, int]] = None,
    *,
    default_feedrate: Optional[float] = None,
    include_rapids: Optional[bool] = None,
    fudge_factor: Optional[float] = None,
    debug: Optional[bool] = None,
) -> float:
    cfg = _coerce_config(config_or_feed, default_feedrate, include_rapids, fudge_factor, debug)
    total_time, total_distance = 0.0, 0.0
    prev, feed = {"X": None, "Y": None, "Z": None}, cfg.default_feedrate

    for raw in gcode_lines:
        line = raw.split(";", 1)[0].strip()
        if not line or not line.startswith(("G0", "G1")):
            continue
        if line.startswith("G0") and not cfg.include_rapids:
            continue
        curr, feed = _parse_move(line.split(), prev, feed)
        dist = _dist(prev, curr)
        total_distance += dist
        if feed > 0:
            t = dist / feed
            total_time += t
            if cfg.debug:
                print(f"Move: X{curr['X']:.3f} Y{curr['Y']:.3f} Z{curr['Z']:.3f} | d={dist:.4f} mm @ {feed:.0f} → {t:.4f} min")
        prev = curr

    if cfg.debug:
        print(f"[Debug] Total distance moved: {total_distance:.3f} mm")
        print(f"[Debug] Raw runtime: {total_time:.2f} min")
        print(f"[Debug] Fudge factor applied: x{cfg.fudge_factor}")
    return total_time * cfg.fudge_factor
