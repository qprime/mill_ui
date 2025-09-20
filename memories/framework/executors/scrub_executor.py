from __future__ import annotations

from typing import Dict

__all__ = ["run"]


def run(payload: Dict[str, str]) -> Dict[str, str]:
    """Deterministic scrub stub returning a canned redaction report."""
    return {
        "status": "ok",
        "redactions": [],
        "inputs": payload,
    }

