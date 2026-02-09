from __future__ import annotations

from typing import Callable, Dict


_REGISTRY: Dict[str, Dict[str, Callable[..., object]]] = {}


def register_strategy(kind: str, name: str, fn: Callable[..., object]) -> None:

    bucket = _REGISTRY.setdefault(kind, {})
    bucket[name] = fn


__all__ = ["register_strategy"]
