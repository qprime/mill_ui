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
12. Do not use decorators, they will interfere with AST and project graphs.

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

**Refactor-Friendly Python Rules (v1.1)**

* Top metadata header only (no comments/docstrings).
* One file, one public API (`api` key in header).
* Absolute imports only (`skills.foo.bar`, `continuum.tools.refactor` etc.).
* ≤25 lines per function unless unavoidable.
* Flat control flow (nest ≤2).
* All inputs explicit, all outputs deterministic.
* Helpers pure and composable.
* If a module returns structured output, use a dict or dataclass that’s **obvious from the name**—no special “norm”/“met” helpers unless actually needed for the function’s job.
* No unused “standard” fields — if a return shape doesn’t need `error` or `metrics`, don’t include them.



##Sample Python File Skeleton:


# path: {package_path}/{module_name}.py
# desc: {short_description}
# api: {public_function_name}
# tags: {comma,separated,tags}

from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional

__all__ = ["{public_function_name}"]


@dataclass(frozen=True)
class Config:
    limit: Optional[int] = None


def _to_dict(payload: Mapping[str, Any]) -> Dict[str, Any]:
    return dict(payload)


def _normalize_keys(d: Dict[str, Any]) -> Dict[str, Any]:
    return {str(k): v for k, v in d.items()}


def _apply_limit(d: Dict[str, Any], cfg: Config) -> Dict[str, Any]:
    if isinstance(cfg.limit, int) and cfg.limit >= 0:
        return {k: d[k] for k in list(d)[: cfg.limit]} if cfg.limit else {}
    return d


def {public_function_name}(payload: Mapping[str, Any], config: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    cfg = Config(**config) if isinstance(config, Mapping) else Config()
    data = _to_dict(payload)
    data = _normalize_keys(data)
    return _apply_limit(data, cfg)


def main() -> None:
    parser = argparse.ArgumentParser(description="{short_description}")
    parser.add_argument("--limit", type=int, help="Limit number of keys processed")
    parser.add_argument("--payload", type=str, help="Payload as key=value pairs, comma-separated")
    args = parser.parse_args()

    payload = {}
    if args.payload:
        for pair in args.payload.split(","):
            k, v = pair.split("=", 1)
            payload[k] = v

    result = {public_function_name}(payload, {"limit": args.limit})
    print(result)


if __name__ == "__main__":
    main()
