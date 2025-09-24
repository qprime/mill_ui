"""Deterministic context assembly built on precomputed caches."""
from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from skills.ace_control.config_store import load_budget_config
from continuum.context_cache import (
    CACHE_FILENAMES,
    ContextBudget,
    build_all_caches,
    cache_path,
    load_budget,
    load_cache,
    select_context,
)
from cortex.context_manager import load_persona_context
from tools.context_builder import build_context as _build_code_context


@dataclass
class ContextSpec:
    include_persona: bool = True
    include_code: bool = False
    scope: str = "auto"  # auto, all, changed
    persona: Optional[str] = None
    persona_category: str = ""
    explicit_files: Optional[List[str]] = None
    focus_files: Optional[List[str]] = None
    max_direct_files: Optional[int] = None


def _git_changed_files(root: Path) -> List[str]:
    try:
        def run(cmd: Sequence[str]) -> Tuple[str, int]:
            proc = subprocess.run(cmd, cwd=root, capture_output=True, text=True)
            out = (proc.stdout + ("\n" + proc.stderr if proc.stderr else "")).strip()
            return out, proc.returncode

        names: List[str] = []
        out, rc = run(["git", "diff", "--name-only"])
        if rc == 0 and out:
            names.extend([line.strip() for line in out.splitlines() if line.strip()])
        out2, rc2 = run(["git", "ls-files", "--others", "--exclude-standard"])
        if rc2 == 0 and out2:
            names.extend([line.strip() for line in out2.splitlines() if line.strip()])
        deduped: List[str] = []
        seen = set()
        for name in names:
            if name not in seen:
                seen.add(name)
                deduped.append(name)
        return deduped
    except Exception:
        return []


def _ensure_caches(root: Path) -> Dict[str, Path]:
    missing = [name for name, filename in CACHE_FILENAMES.items() if not cache_path(name).exists()]
    if missing:
        return build_all_caches(root)
    return {name: cache_path(name) for name in CACHE_FILENAMES}


def _cache_manifest() -> Dict[str, Dict[str, object]]:
    manifest: Dict[str, Dict[str, object]] = {}
    for name in CACHE_FILENAMES:
        path = cache_path(name)
        if path.exists():
            stat = path.stat()
            manifest[name] = {
                "path": str(path),
                "size": stat.st_size,
                "mtime": int(stat.st_mtime),
            }
    return manifest


def _load_budget() -> ContextBudget:
    config, _ = load_budget_config()
    return load_budget(config)


def _all_python_files(root: Path) -> List[str]:
    try:
        file_tree = load_cache("file_tree")
    except FileNotFoundError:
        build_all_caches(root)
        file_tree = load_cache("file_tree")
    return [entry["path"] for entry in file_tree if entry.get("type") == "file" and entry.get("path", "").endswith(".py")]


def assemble_context(
    root_dir: str = ".",
    spec: Optional[ContextSpec] = None,
) -> Dict[str, object]:
    root = Path(root_dir).resolve()
    spec = spec or ContextSpec()

    _ensure_caches(root)
    budget = _load_budget()
    if spec.max_direct_files is not None:
        budget.direct_files_max = spec.max_direct_files

    change_set: List[str] = []
    if spec.scope == "all":
        change_set = _all_python_files(root)
    elif spec.scope in {"auto", "changed"}:
        change_set = _git_changed_files(root)
        if spec.scope == "auto" and not change_set:
            change_set = _all_python_files(root)[: budget.direct_files_max]

    manifest = select_context(
        root,
        focus_files=spec.focus_files or [],
        change_set=change_set,
        explicit_files=spec.explicit_files or [],
        budget=budget,
    )

    bundle: Dict[str, object] = {
        "root": str(root),
        "spec": asdict(spec),
        "budget": budget.__dict__,
        "context": manifest,
        "change_set": change_set,
        "cache_manifest": _cache_manifest(),
    }

    if spec.include_persona and spec.persona:
        try:
            persona_text = load_persona_context(spec.persona, spec.persona_category)
        except Exception:
            persona_text = ""
        bundle["persona_prompt"] = persona_text or ""

    if spec.include_code:
        try:
            bundle["code_context_path"] = str(_build_code_context(str(root), output=None))
        except Exception as exc:
            bundle["code_context_error"] = str(exc)

    return bundle


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Assemble project context bundle")
    parser.add_argument("--root", default=".")
    parser.add_argument("--persona", default=None)
    parser.add_argument("--persona-category", default="")
    parser.add_argument("--scope", choices=["auto", "all", "changed"], default="auto")
    parser.add_argument("--include-code", action="store_true")
    parser.add_argument("--no-persona", action="store_true")
    parser.add_argument("--max-direct", type=int, default=None)
    parser.add_argument("-o", "--output", type=Path, default=Path("docs/_reports/context_bundle.json"))
    args = parser.parse_args(argv)

    spec = ContextSpec(
        include_persona=not args.no_persona,
        include_code=args.include_code,
        scope=args.scope,
        persona=args.persona,
        persona_category=args.persona_category,
        max_direct_files=args.max_direct,
    )

    bundle = assemble_context(args.root, spec)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(bundle, indent=2), encoding="utf-8")
    print(f"[context] wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
