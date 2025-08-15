# path: cam_generator/registry.py
# desc: Strategy registry mapping names to callables
# api: get_strategy
# tags: registry,strategy

from __future__ import annotations
from typing import Callable, Dict

from skills.cam_generator_v4.strategy_rough_zslices import plan_rough
from skills.cam_generator_v4.strategy_raster_finish import plan_finish
from skills.cam_generator_v4.strategy_pencil import plan_pencil

__all__ = ["get_strategy"]

_REGISTRY: Dict[str, Callable[..., object]] = {
    "rough_zslices": plan_rough,
    "raster_finish": plan_finish,   # signature now: (env, band_top, band_bot, ...)
    "pencil": plan_pencil,
}

def get_strategy(name: str) -> Callable[..., object]:
    if name not in _REGISTRY:
        raise KeyError(f"Unknown strategy '{name}'")
    return _REGISTRY[name]
