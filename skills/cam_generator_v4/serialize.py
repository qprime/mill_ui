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
    # plan_result["bands"] now has {"barriers", "pass_bands"} (no "tool_bands")
    pass_bands: Dict[str, Dict[str, np.ndarray]] = plan_result["bands"]["pass_bands"]

    bands_json: Dict[str, Any] = {}
    for p in plan_result["passes"]:
        name = p["name"]
        b = pass_bands[name]
        bands_json[name] = {
            "top_stats": _stats(b["top"]),
            "bot_stats": _stats(b["bot"]),
            "dz_stats": _stats(b["dz"]),
        }

    passes_json: List[Dict[str, Any]] = []
    for p in plan_result["passes"]:
        passes_json.append({
            "name": p["name"],
            "role": p["role"],
            "tool": p["tool"],
            "move_count": int(len(p["moves"])),
        })

    return {
        "project_name": plan_result["project_name"],
        "pixel_pitch_mm": float(plan_result["pixel_pitch_mm"]),
        "bands": bands_json,
        "passes": passes_json,
    }
