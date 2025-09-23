from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Optional

from watchfiles import watch

from .context_orchestrator import ContextSpec, assemble_context


def build_once(root: Path, output: Path, spec: ContextSpec) -> None:
    bundle = assemble_context(str(root), spec)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(bundle, indent=2), encoding="utf-8")
    print(f"[watch] wrote {output}")


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Watch project and rebuild context bundle on changes")
    parser.add_argument("--root", default=".")
    parser.add_argument("-o", "--output", default="docs/_reports/context_bundle.json")
    parser.add_argument("--scope", choices=["auto", "all", "changed"], default="auto")
    parser.add_argument("--max-direct", type=int, default=None)
    parser.add_argument("--include-code", action="store_true")
    parser.add_argument("--no-persona", action="store_true")
    parser.add_argument("--persona", default=None)
    parser.add_argument("--persona-category", default="")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    output = Path(args.output).resolve()
    spec = ContextSpec(
        include_code=args.include_code,
        include_persona=not args.no_persona,
        scope=args.scope,
        persona=args.persona,
        persona_category=args.persona_category,
        max_direct_files=args.max_direct,
    )

    build_once(root, output, spec)
    print(f"[watch] watching {root}")
    for _changes in watch(root):
        try:
            build_once(root, output, spec)
        except Exception as exc:
            print(f"[watch] error: {exc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
