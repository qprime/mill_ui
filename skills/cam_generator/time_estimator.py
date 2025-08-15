# path: skills/cam_generator/core/time_estimator.py
# # desc: Estimate G-code cut time; robust XY feed handling.
# api: estimate_cut_time
# tags: cam

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Mapping, Optional, Union

@dataclass(frozen=True)
class Config:
    default_feedrate: float = 300.0  # feed units assumed mm/min
    include_rapids: bool = False
    rapid_feed_xy: float = 4000.0   # mm/min
    rapid_feed_z: float = 1500.0    # mm/min
    fudge_factor: float = 1.15
    debug: bool = False
    xy_only: bool = True            # treat feed as planar XY (safer)
    auto_unit_detect: bool = True   # detect mm/s vs mm/min based on ratios

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

def _dist(prev: dict[str, Optional[float]], curr: dict[str, Optional[float]]) -> tuple[float, float, float]:
    if None in prev.values() or None in curr.values():
        return 0.0, 0.0, 0.0
    dx = curr["X"] - prev["X"]
    dy = curr["Y"] - prev["Y"]
    dz = curr["Z"] - prev["Z"]
    dxy = math.hypot(dx, dy)
    d3d = math.hypot(dxy, dz)
    return d3d, dxy, abs(dz)

def _coerce_config(cfg: Optional[Union["Config", Mapping[str, object], float, int]]) -> Config:
    if isinstance(cfg, Config):
        return cfg
    if isinstance(cfg, Mapping):
        return Config(
            default_feedrate=float(cfg.get("default_feedrate", 300.0)),
            include_rapids=bool(cfg.get("include_rapids", False)),
            rapid_feed_xy=float(cfg.get("rapid_feed_xy", 4000.0)),
            rapid_feed_z=float(cfg.get("rapid_feed_z", 1500.0)),
            fudge_factor=float(cfg.get("fudge_factor", 1.15)),
            debug=bool(cfg.get("debug", False)),
            xy_only=bool(cfg.get("xy_only", True)),
            auto_unit_detect=bool(cfg.get("auto_unit_detect", True)),
        )
    if isinstance(cfg, (int, float)):
        return Config(default_feedrate=float(cfg))
    return Config()

def estimate_cut_time(
    gcode_lines: Iterable[str],
    config_or_feed: Optional[Union[Config, Mapping[str, object], float, int]] = None,
    *,
    default_feedrate: Optional[float] = None,
    include_rapids: Optional[bool] = None,
    fudge_factor: Optional[float] = None,
    debug: Optional[bool] = None,
) -> float:
    # Build cfg with any keyword overrides
    base = _coerce_config(config_or_feed)
    if isinstance(default_feedrate, (int, float)):
        base = Config(**{**base.__dict__, "default_feedrate": float(default_feedrate)})
    if include_rapids is not None:
        base = Config(**{**base.__dict__, "include_rapids": bool(include_rapids)})
    if isinstance(fudge_factor, (int, float)):
        base = Config(**{**base.__dict__, "fudge_factor": float(fudge_factor)})
    if debug is not None:
        base = Config(**{**base.__dict__, "debug": bool(debug)})

    prev = {"X": None, "Y": None, "Z": None}
    feed = float(base.default_feedrate)
    total_min = 0.0
    total_xy = 0.0
    total_z = 0.0
    g1_count = 0
    feed_samples = []

    for raw in gcode_lines:
        s = raw.split(";", 1)[0].strip()
        if not s or not s.startswith(("G0", "G1")):
            continue
        parts = s.split()
        is_rapid = parts[0] == "G0"
        curr, feed = _parse_move(parts, prev, feed)
        d3d, dxy, dz = _dist(prev, curr)

        if parts[0] == "G1":
            g1_count += 1
            total_xy += dxy
            total_z += dz
            feed_samples.append(feed)
            eff_d = dxy if base.xy_only else d3d
            if feed > 0:
                total_min += eff_d / feed  # feed assumed mm/min → minutes

        elif is_rapid and base.include_rapids:
            # Conservative max of XY vs Z rapid
            t_xy = dxy / max(1.0, base.rapid_feed_xy)
            t_z  = dz  / max(1.0, base.rapid_feed_z)
            total_min += max(t_xy, t_z)

        prev = curr

    # Auto unit detection: if times are implausibly large relative to XY distance and median feed,
    # assume F was mm/s and convert.
    if base.auto_unit_detect and g1_count and feed_samples:
        med_feed = sorted(feed_samples)[len(feed_samples)//2]
        naive_min = (total_xy / max(1.0, med_feed))
        if total_min > 45.0 * naive_min:  # ~60× inflation heuristic
            total_min /= 60.0  # convert mm/s → mm/min assumption

    if base.debug:
        print(f"[est] XY={total_xy/1000:.3f} km, Z={total_z/1000:.3f} km, G1={g1_count}, feed~median={sorted(feed_samples)[len(feed_samples)//2] if feed_samples else base.default_feedrate:.1f}")
        print(f"[est] raw={total_min:.2f} min, fudge={base.fudge_factor} → {total_min*base.fudge_factor:.2f} min")

    return total_min * base.fudge_factor
