# Python Guidance v1

## Header Format

```
# path: <path>/<to>/<file.py>
# # desc: Estimate G-code cut time
# api: estimate_cut_time
# tags: cam,time
```

**Keys**

* **path** – relative path (unique merge key)
* **desc** – short, single sentence
* **api** – single public entry point
* **tags** – comma-separated for search/graph

---

## Core Principles

1. One file, one job; single public symbol (`api` in header).
2. Pure functions; ≤20 lines unless unavoidable.
3. Flat control flow (max nesting 2); prefer early returns.
4. No comments; context in header or guidance.
5. Clear names; no non-obvious abbreviations.
6. Absolute imports; no dynamic imports/`exec`.
7. Full type hints; dataclasses for structured inputs.
8. All inputs explicit; no globals/env reliance.
9. Deterministic outputs; seed any randomness from config.
10. Helpers are pure and composable.
11. Follow the canonical skeleton exactly.

---

## Risk-Reduction Practices

1. Input validation in entry point; helpers assume valid data.
2. Minimal cross-file coupling; call via public symbols.
3. Consistent return shapes for similar modules.
4. Centralize constants/config.
5. Stable key order in data structures.
6. Avoid implicit truthiness checks, side-effect context managers.
7. Break complex comprehensions into loops.
8. Uniform file layout (imports → constants → dataclasses → helpers → interface).



##Sample Python File Skeleton##
# path: skills/example/do_thing.py
# desc: Transform input payload
# api: run
# tags: example,transform

from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, Optional, TypedDict

__all__ = ["run"]


# --------------------
# Types & Config
# --------------------

class Result(TypedDict):
    ok: bool
    data: Dict[str, Any]
    error: Optional[str]
    metrics: Dict[str, Any]


@dataclass(frozen=True)
class Config:
    mode: str = "default"
    limit: int = 0
    eps: float = 1e-6
    seed: Optional[int] = None


# --------------------
# Pure Helpers
# --------------------

def _validate(payload: Dict[str, Any]) -> Optional[str]:
    if not isinstance(payload, dict):
        return "payload must be a dict"
    return None


def _normalize(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {str(k): payload[k] for k in payload}


def _process(payload: Dict[str, Any], cfg: Config) -> Dict[str, Any]:
    if cfg.limit and len(payload) > cfg.limit:
        ks = list(payload)[: cfg.limit]
        return {k: payload[k] for k in ks}
    return payload


def _metrics(payload: Dict[str, Any], cfg: Config) -> Dict[str, Any]:
    return {
        "n_items": len(payload),
        "mode": cfg.mode,
        "limit": cfg.limit,
        "eps": cfg.eps,
    }


# --------------------
# Public Interface
# --------------------

def run(payload: Dict[str, Any], config: Optional[Dict[str, Any]] = None) -> Result:
    e = _validate(payload)
    if e:
        return {"ok": False, "data": {}, "error": e, "metrics": {}}

    cfg = Config(**config) if isinstance(config, dict) else Config()
    norm = _normalize(payload)
    out = _process(norm, cfg)
    met = _metrics(out, cfg)
    return {"ok": True, "data": out, "error": None, "metrics": met}
