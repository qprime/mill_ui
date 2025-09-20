from __future__ import annotations

from typing import Dict

__all__ = ["run"]


def run(payload: Dict[str, str]) -> Dict[str, str]:
    """Deterministic stub for simulation runs (CNC / IT sandboxes)."""
    return {
        "status": "not_implemented",
        "details": payload,
    }

