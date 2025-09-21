"""Detect and cache optional backend capabilities."""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any


@dataclass(frozen=True)
class Capabilities:
    native_cad: bool = False

    def require_native(self, feature: str) -> None:
        if not self.native_cad:
            raise RuntimeError(
                f"Native capability required for {feature}, but the native CAD backend is unavailable."
            )

    def as_dict(self) -> dict[str, Any]:
        return {"native_cad": self.native_cad}


@lru_cache(maxsize=1)
def get_capabilities() -> Capabilities:
    try:
        from skills.mill_ui.cad.native.core import is_native_available
    except Exception:  # pragma: no cover - import failure indicates native unavailable
        native = False
    else:
        try:
            native = bool(is_native_available())
        except Exception:  # pragma: no cover - defensive guard
            native = False
    return Capabilities(native_cad=native)


def has_native_cad() -> bool:
    return get_capabilities().native_cad


__all__ = ["Capabilities", "get_capabilities", "has_native_cad"]
