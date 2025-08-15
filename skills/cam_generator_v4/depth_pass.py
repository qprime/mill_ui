# path: skills/cam_generator_v4/depth_pass.py
# desc: Expand toolpath moves into layered step-downs
# api: apply_depth_passes
# tags: cam,toolpath,stepdown

from __future__ import annotations
import math
from typing import Dict, Iterable, List

__all__ = ["apply_depth_passes"]

_Move = Dict[str, float]

def _floors(top_z: float, min_z: float, step: float) -> List[float]:
    if step <= 0 or top_z <= min_z:
        return [min_z]
    n = max(1, int(math.ceil((top_z - min_z) / step)))
    floors = [top_z - i * step for i in range(1, n + 1)]
    floors[-1] = min_z
    return floors

def _clamp_z(m: _Move, floor_z: float) -> _Move:
    if "z" in m:
        v = float(m["z"])
        if v < floor_z:
            m = dict(m)
            m["z"] = floor_z
    return m

def apply_depth_passes(moves: Iterable[_Move], top_z: float, safe_z: float, stepdown_mm: float) -> List[_Move]:
    seq = list(moves)
    if not seq or stepdown_mm <= 0:
        return seq
    min_z = min(float(m.get("z", top_z)) for m in seq)
    out: List[_Move] = []
    for floor in _floors(top_z, min_z, stepdown_mm):
        out.append({"mode": 0, "z": safe_z})
        out.extend(_clamp_z(m, floor) for m in seq)
    return out
