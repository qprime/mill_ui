# path: cam_generator/serialize.py
# desc: Create deterministic JSON summary of plan results
# api: to_json
# tags: json,report

from __future__ import annotations

from typing import Any, Dict, List
import numpy as np

__all__ = ["to_json"]

def _stats(a: np.ndarray) -> Dict[str, float]:
    a = a.astype(np.float32, copy=False)
    return {
        "min": float(np.min(a)),
        "max": float(np.max(a)),
        "mean": float(np.mean(a)),
        "std": float(np.std(a)),
    }

def to_json(plan_result: Dict[str, Any]) -> Dict[str, Any]:
    # Pass list is the only hard requirement
    passes = plan_result.get("passes", []) or []

    bands_json: Dict[str, Any] = {}
    bands = plan_result.get("bands")
    pass_bands = bands.get("pass_bands") if isinstance(bands, dict) else None

    if isinstance(pass_bands, dict):
        for p in passes:
            name = p.get("name")
            b = pass_bands.get(name) if name is not None else None
            if isinstance(b, dict) and all(k in b for k in ("top", "bot", "dz")):
                bands_json[name] = {
                    "top_stats": _stats(b["top"]),
                    "bot_stats": _stats(b["bot"]),
                    "dz_stats": _stats(b["dz"]),
                }

    passes_json: List[Dict[str, Any]] = []
    for p in passes:
        passes_json.append({
            "name": p.get("name"),
            "role": p.get("role"),
            "tool": p.get("tool"),
            "move_count": int(len(p.get("moves", []))),
        })

    out = {
        "project_name": plan_result.get("project_name"),
        "pixel_pitch_mm": float(plan_result.get("pixel_pitch_mm", 0.0)),
        "passes": passes_json,
    }
    if bands_json:
        out["bands"] = bands_json
    return out
