# path: skills/cam_engine/strategy_border_rect.py
# desc: Perimeter border strategy using rectangular offsets
# api: plan_border_rect
# tags: cam,strategy,border

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Tuple

from skills.cam_engine.border import generate_rect_border_moves

_Move = Dict[str, float]
_Bounds = Tuple[float, float, float, float]


@dataclass(frozen=True)
class _Inputs:
    bounds_mm: _Bounds
    inset_mm: float
    width_mm: float
    target_depth_mm: float
    stepover_mm: float
    feed_mm_min: float
    climb_ccw: bool


def _float(v: Any, default: float) -> float:
    try:
        return float(v)
    except Exception:
        return float(default)


def _resolve_inputs(pass_cfg: Mapping[str, Any], hm_cfg: Mapping[str, Any]) -> _Inputs:
    bounds = tuple(hm_cfg.get("bounds_mm") or (0.0, 0.0, 0.0, 0.0))  # type: ignore[assignment]
    tool = pass_cfg.get("tool") or {}
    tool_diam = _float(tool.get("diameter_mm", 0.0), 0.0)

    stepover = pass_cfg.get("stepover_mm")
    stepover_mm = _float(stepover, 0.6 * tool_diam) if stepover is not None else (0.6 * tool_diam)

    target_depth_mm = _float(
        pass_cfg.get("target_depth_mm", hm_cfg.get("max_depth_mm", 1.0)),
        1.0,
    )

    return _Inputs(
        bounds_mm=(float(bounds[0]), float(bounds[1]), float(bounds[2]), float(bounds[3])),
        inset_mm=_float(pass_cfg.get("inset_mm", 0.0), 0.0),
        width_mm=_float(pass_cfg.get("width_mm", 0.0), 0.0),
        target_depth_mm=target_depth_mm,
        stepover_mm=stepover_mm,
        feed_mm_min=_float(pass_cfg.get("feed_mm_per_min", 800.0), 800.0),
        climb_ccw=bool(pass_cfg.get("climb_ccw", True)),
    )


def plan_border_rect(pass_cfg: Mapping[str, Any], heightmap_cfg: Mapping[str, Any]) -> List[_Move]:
    if not bool(pass_cfg.get("enable", True)):
        return []
    i = _resolve_inputs(pass_cfg, heightmap_cfg)
    return generate_rect_border_moves(
        bounds_mm=i.bounds_mm,
        inset_mm=i.inset_mm,
        width_mm=i.width_mm,
        target_depth_mm=i.target_depth_mm,
        stepover_mm=i.stepover_mm,
        feed_mm_min=i.feed_mm_min,
        climb_ccw=i.climb_ccw,
    )
