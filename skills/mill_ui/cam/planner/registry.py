"""Minimal registry for planner strategies."""
from __future__ import annotations

from typing import Callable, Dict, Optional


_REGISTRY: Dict[str, Dict[str, Callable[..., object]]] = {}


def register_strategy(kind: str, name: str, fn: Callable[..., object]) -> None:
    """Register a callable strategy under ``(kind, name)``."""

    bucket = _REGISTRY.setdefault(kind, {})
    bucket[name] = fn


def get_strategy(kind: str, name: str) -> Optional[Callable[..., object]]:
    """Return a strategy callable if it has been registered."""

    return _REGISTRY.get(kind, {}).get(name)


__all__ = ["get_strategy", "register_strategy"]

