# skills/cam_generator/core/time_estimator.py
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Mapping, Optional, Union

@dataclass(frozen=True)
class Config:
    # Cutting defaults
    default_feedrate: float = 300.0

    # Rapids handling
    include_rapids: bool = False           # when False: don't charge time for G0, but DO update position
    rapid_feed_xy: float = 4000.0          # only used if include_rapids=True
    rapid_feed_z: float = 1500.0           # only used if include_rapids=True

    # Misc
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

def _dist(a: dict[str, Optional[float]], b: dict[str, Optional[float]]) -> tuple[float, float, float]:
    if None in a.values() or None in b.values():
        return 0.0, 0.0, 0.0
    dx, dy, dz = b["X"] - a["X"], b["Y"] - a["Y"], b["Z"] - a["Z"]
    dxy = math.sqrt(dx*dx + dy*dy)
    d = math.sqrt(dx*dx + dy*dy + dz*dz)
    return d, dxy, abs(dz)

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
            rapid_feed_xy=float(arg.get("rapid_feed_xy", 4000.0)),
            rapid_feed_z=float(arg.get("rapid_feed_z", 1500.0)),
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
            rapid_feed_xy=base.rapid_feed_xy,
            rapid_feed_z=base.rapid_feed_z,
            fudge_factor=base.fudge_factor,
            debug=base.debug,
        )
    if include_rapids is not None:
        base = Config(
            default_feedrate=base.default_feedrate,
            include_rapids=bool(include_rapids),
            rapid_feed_xy=base.rapid_feed_xy,
            rapid_feed_z=base.rapid_feed_z,
            fudge_factor=base.fudge_factor,
            debug=base.debug,
        )
    if isinstance(fudge_factor, (int, float)):
        base = Config(
            default_feedrate=base.default_feedrate,
            include_rapids=base.include_rapids,
            rapid_feed_xy=base.rapid_feed_xy,
            rapid_feed_z=base.rapid_feed_z,
            fudge_factor=float(fudge_factor),
            debug=base.debug,
        )
    if debug is not None:
        base = Config(
            default_feedrate=base.default_feedrate,
            include_rapids=base.include_rapids,
            rapid_feed_xy=base.rapid_feed_xy,
            rapid_feed_z=base.rapid_feed_z,
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
    """
    Estimate minutes from G-code.
    - If include_rapids=False (default): G0 moves DO NOT count toward time,
      but we still update the current position so the next G1 isn't charged for that travel.
    - If include_rapids=True: we time G0 using rapid_feed_xy and rapid_feed_z
      (time ≈ max(dxy/rapid_xy, dz/rapid_z) to approximate parallel axis motion).
    """
    cfg = _coerce_config(config_or_feed, default_feedrate, include_rapids, fudge_factor, debug)
    total_time, total_distance = 0.0, 0.0
    prev, feed = {"X": None, "Y": None, "Z": None}, cfg.default_feedrate

    for raw in gcode_lines:
        # strip comments
        line = raw.split(";", 1)[0].strip()
        if not line or not line.startswith(("G0", "G1")):
            continue

        parts = line.split()
        is_rapid = line.startswith("G0")

        # Always parse + compute new position
        curr, feed = _parse_move(parts, prev, feed)
        d, dxy, dz = _dist(prev, curr)

        # Account for time
        if is_rapid:
            if cfg.include_rapids:
                # Approximate: parallel XY/Z at different max rates → take the slower axis time
                t_xy = (dxy / cfg.rapid_feed_xy) if cfg.rapid_feed_xy > 0 else 0.0
                t_z  = (dz  / cfg.rapid_feed_z)  if cfg.rapid_feed_z  > 0 else 0.0
                t = max(t_xy, t_z)
                total_time += t
        else:
            if feed > 0:
                t = d / feed
                total_time += t

        # Always update distance for debugging/telemetry
        total_distance += d

        if cfg.debug:
            kind = "G0" if is_rapid else "G1"
            note = "(ignored)" if (is_rapid and not cfg.include_rapids) else ""
            eff_feed = (cfg.rapid_feed_xy if is_rapid else feed)
            print(f"{kind} to X{curr['X']:.3f} Y{curr['Y']:.3f} Z{curr['Z']:.3f} "
                  f"| d={d:.3f} mm @ {eff_feed:.0f} {note}")

        # IMPORTANT: update position even if we ignored rapid time
        prev = curr

    if cfg.debug:
        print(f"[Debug] Total distance moved: {total_distance:.3f} mm")
        print(f"[Debug] Raw runtime: {total_time:.2f} min")
        print(f"[Debug] Fudge factor applied: x{cfg.fudge_factor}")
    return total_time * cfg.fudge_factor
