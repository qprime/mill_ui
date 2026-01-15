from __future__ import annotations

from typing import Callable, Dict, Optional


_REGISTRY: Dict[str, Dict[str, Callable[..., object]]] = {}


def register_strategy(kind: str, name: str, fn: Callable[..., object]) -> None:

    bucket = _REGISTRY.setdefault(kind, {})
    bucket[name] = fn


def get_strategy(kind: str, name: str) -> Optional[Callable[..., object]]:

    return _REGISTRY.get(kind, {}).get(name)


__all__ = ["get_strategy", "register_strategy"]
