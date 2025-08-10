# path: continuum/metadata.py
# type: context_metadata
# tags: context, merge, deduplication, ai-native, metadata, unified
# owner: cliff
# depends_on: continuum/ast_context.py, continuum/project_graph.py, continuum/code_context.py
# description: Canonical entry point to unify AST, project graph, and header metadata.

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Dict, Any, Tuple

from continuum.ast_context import generate_ast_context
from continuum.project_graph import build_project_graph
from continuum.code_context import generate_code_context

import tiktoken

# -------------------------------
# Token counting
# -------------------------------

def count_tokens(text: str, model_name: str = "gpt-4.1") -> int:
    try:
        enc = tiktoken.encoding_for_model(model_name)
    except Exception:
        enc = tiktoken.get_encoding("cl100k_base")
    return len(enc.encode(text))

# -------------------------------
# Normalization / merge helpers
# -------------------------------

EXCLUDE_PATH_PATTERNS = (
    ".Trash-1000/",
    ".venv/",
    "__pycache__/",
    "node_modules/",
    ".git/",
    "dist/",
    "build/",
)

ALIASES = {
    "desc": "description",
}

# list-like fields we should union/dedup
LIST_FIELDS = {
    "tags",
    "depends_on",
    "imports",
    "functions",
    "classes",
    "methods",
}

def _norm_path(p: str, root: Path) -> str:
    """Return posix-style, root-relative path."""
    if not p:
        return ""
    p = p.replace("\\", "/")
    if p.startswith("./"):
        p = p[2:]
    try:
        if p.startswith("/"):
            p = os.path.relpath(p, str(root))
    except Exception:
        pass
    return p.strip("/")

def _is_excluded_path(p: str) -> bool:
    p2 = p if p.endswith("/") else p + "/"
    # Exclude empty/synthetic keys and common junk folders
    if p in ("", "summary", "modules"):
        return True
    return any(x in p2 for x in EXCLUDE_PATH_PATTERNS)

def _apply_aliases(d: Dict[str, Any]) -> Dict[str, Any]:
    return {ALIASES.get(k, k): v for k, v in d.items()}

def _split_to_list(v: Any) -> list[str]:
    if v is None:
        return []
    if isinstance(v, list):
        return [str(x).strip() for x in v if str(x).strip()]
    s = str(v).strip()
    if not s:
        return []
    parts = [x.strip() for x in (s.split(",") if "," in s else re.split(r"\s+", s))]
    return [x for x in parts if x]

def _normalize_record(rec: Dict[str, Any]) -> Dict[str, Any]:
    """Coerce list fields and strip empties after aliases are applied."""
    out: Dict[str, Any] = {}
    for k, v in rec.items():
        if v in ("", None, []):
            continue
        if k in ("tags", "depends_on"):
            vv = _split_to_list(v)
            if vv:
                out[k] = vv
        elif k in LIST_FIELDS:
            out[k] = list(v) if isinstance(v, list) else [v]
        else:
            out[k] = v
    return out

# -------------------------------
# Header parsing
# -------------------------------

def parse_header_metadata(header_blob: str) -> Dict[str, Dict[str, Any]]:
    """
    Parse header blocks (separated by a *blank* line) into {path: meta}.
    Coerce list-like fields and apply aliases up-front.
    """
    blocks = [b.strip() for b in header_blob.strip().split("\n\n") if b.strip()]
    header_map: Dict[str, Dict[str, Any]] = {}
    for block in blocks:
        lines = [line.lstrip("#").strip() for line in block.splitlines() if line.strip()]
        meta: Dict[str, Any] = {}
        path = None
        for line in lines:
            if ":" in line:
                key, value = line.split(":", 1)
                key, value = key.strip(), value.strip()
                if key == "path":
                    path = value
                meta[key] = value
        if not path:
            continue
        meta = _apply_aliases(meta)
        if "tags" in meta:
            meta["tags"] = _split_to_list(meta["tags"])
        if "depends_on" in meta:
            meta["depends_on"] = _split_to_list(meta["depends_on"])
        # drop empties
        meta = {k: v for k, v in meta.items() if v not in ("", None, [])}
        header_map[path] = meta
    return header_map

# -------------------------------
# Merge
# -------------------------------

def merge_contexts(
    project_graph,
    header_metadata,
    ast_metadata,
    prefer="project_graph",
    root_dir=".",
):
    root = Path(root_dir).resolve()

    def norm_keys(d):
        out = {}
        for k, v in (d or {}).items():
            nk = _norm_path(k, root)
            if not nk or _is_excluded_path(nk):
                continue
            # Keep only real files; prevents synthetic/ghost keys (e.g., "modules")
            if not (root / nk).is_file():
                continue
            out[nk] = _apply_aliases(v if isinstance(v, dict) else {"description": v})
        return out

    project_graph = norm_keys(project_graph)
    header_metadata = norm_keys(header_metadata)
    ast_metadata = norm_keys(ast_metadata)

    all_paths = set(project_graph) | set(header_metadata) | set(ast_metadata)
    sources = {
        "project_graph": project_graph,
        "header_metadata": header_metadata,
        "ast_metadata": ast_metadata,
    }

    merged = {}

    for path in all_paths:
        merged_fields = {"path": path}
        # Gather values per field in priority order
        field_values = {}
        for source_name in [prefer] + [s for s in sources if s != prefer]:
            src = sources[source_name]
            if path not in src:
                continue
            value = src[path]
            if not isinstance(value, dict):
                continue
            value = _normalize_record(value)
            for k, v in value.items():
                field_values.setdefault(k, []).append(v)
        # Resolve each field
        for k, vals in field_values.items():
            if k in LIST_FIELDS:
                seen_hashes = set()
                out = []
                for v in vals:
                    items = v if isinstance(v, list) else [v]
                    for item in items:
                        # Create a hashable key for dedup — JSON for dicts, str() otherwise
                        key = json.dumps(item, sort_keys=True) if isinstance(item, dict) else str(item)
                        if key not in seen_hashes:
                            seen_hashes.add(key)
                            out.append(item)
                if out:
                    merged_fields[k] = out
            else:
                chosen = None
                for v in vals:
                    if v not in ("", None, []):
                        chosen = v
                        break
                if chosen not in ("", None, []):
                    merged_fields[k] = chosen
        if merged_fields:
            merged[path] = merged_fields
    return merged


# -------------------------------
# Top-level entry
# -------------------------------

def fetch_metadata(
    root_dir: str = ".",
    exclude: list[str] | None = None,
    output_path: str | None = None,
    model_name: str = "gpt-4.1",
) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Any]]:
    exclude = exclude or []

    # --- AST ---
    ast_index: Dict[str, Dict[str, Any]] = {}
    if "ast" not in exclude:
        ast_index, _ = generate_ast_context(root_dir)

    # --- Project Graph ---
    project_graph: Dict[str, Dict[str, Any]] = {}
    if "graph" not in exclude:
        # build_project_graph is updated to accept model_name
        project_graph, _ = build_project_graph(root_dir, model_name=model_name)

    # --- Header Metadata ---
    header_metadata: Dict[str, Dict[str, Any]] = {}
    if "header" not in exclude:
        header_blob, _ = generate_code_context(root_dir, mode="metadata", model_name=model_name)
        header_metadata = parse_header_metadata(header_blob)

    contexts = merge_contexts(
        project_graph,
        header_metadata,
        ast_index,
        prefer="project_graph",
        root_dir=root_dir,
    )

    output_json = json.dumps(contexts, separators=(",", ":"), sort_keys=True)
    total = count_tokens(output_json, model_name=model_name)
    stats = {
        "file_count": len(contexts),
        "total_tokens": total,
        "avg_tokens_per_file": round(total / max(1, len(contexts)), 1),
    }

    if output_path:
        Path(output_path).write_text(output_json, encoding="utf-8")

    return contexts, stats


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Build unified project metadata")
    parser.add_argument("--root", default=".", help="Project root")
    parser.add_argument("-o", "--output", default=None, help="Write JSON to this path")
    parser.add_argument(
        "--exclude",
        nargs="*",
        default=[],
        choices=["ast", "graph", "header"],
        help="Skip parts (any of: ast graph header)",
    )
    parser.add_argument("--model-name", default="gpt-4.1", help="Tokenizer model for stats")
    parser.add_argument("--quiet", action="store_true", help="Don’t print stats")
    args = parser.parse_args()

    contexts, stats = fetch_metadata(
        root_dir=args.root,
        exclude=args.exclude,
        output_path=args.output,
        model_name=args.model_name,
    )

    if not args.quiet:
        print(f"[STATS] Files included: {stats['file_count']}")
        print(f"[STATS] Total tokens: {stats['total_tokens']}")
        print(f"[STATS] Avg tokens/file: {stats['avg_tokens_per_file']}")
        if args.output:
            print(f"[OK] Wrote: {args.output}")
