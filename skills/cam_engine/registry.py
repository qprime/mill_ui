from __future__ import annotations
from typing import Callable, Dict

from skills.cam_engine.strategy_rough_zslices import plan_rough
from skills.cam_engine.strategy_raster_finish import plan_finish
from skills.cam_engine.strategy_pencil import plan_pencil
from skills.cam_engine.strategy_border_rect import plan_border_rect
from skills.cam_engine.strategy_profile_rect import plan_profile_rect

__all__ = ["get_strategy"]

_REGISTRY: Dict[str, Callable[..., object]] = {
    "rough_zslices": plan_rough,
    "raster_finish": plan_finish,
    "pencil": plan_pencil,
    "border_rect": plan_border_rect,
    "profile_rect": plan_profile_rect,
}

def get_strategy(name: str) -> Callable[..., object]:
    if name not in _REGISTRY:
        raise KeyError(f"Unknown strategy '{name}'")
    return _REGISTRY[name]
