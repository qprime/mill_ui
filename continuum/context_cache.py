"""Deterministic project context caches (file tree, dependencies, symbols, docs, tests)."""
from __future__ import annotations

import ast
import json
import os
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple

CACHE_ENV_VAR = "ACE_CACHE_DIR"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CACHE_DIR = PROJECT_ROOT / "docs" / "_reports"


CACHE_FILENAMES = {
    "file_tree": "file_tree.json",
    "deps_graph": "deps_graph.json",
    "symbol_table": "symbol_table.json",
    "doc_map": "doc_map.json",
    "test_map": "test_map.json",
}


DOC_EXTENSIONS = {".md", ".rst", ".txt", ".adr", ".adoc"}
TEST_FILE_PREFIXES = {"test_"}
TEST_FILE_SUFFIXES = {"_test.py"}
EXCLUDE_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "dist",
    "build",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".Trash-1000",
}


def cache_dir() -> Path:
    override = os.getenv(CACHE_ENV_VAR)
    if override:
        path = Path(override).expanduser()
    else:
        path = DEFAULT_CACHE_DIR
    path.mkdir(parents=True, exist_ok=True)
    return path


def cache_path(name: str) -> Path:
    if name not in CACHE_FILENAMES:
        raise KeyError(f"Unknown cache '{name}'")
    return cache_dir() / CACHE_FILENAMES[name]


def _rel(path: Path, root: Path) -> str:
    try:
        rel = path.relative_to(root)
        if not rel.parts:
            return "."
        return rel.as_posix()
    except ValueError:
        return path.as_posix()


def _should_skip_dir(directory: Path) -> bool:
    return any(part in EXCLUDE_DIRS for part in directory.parts)


def _iter_files(root: Path, suffix: Optional[str] = None) -> Iterable[Path]:
    for path in root.rglob("*" if suffix is None else f"*{suffix}"):
        if not path.is_file():
            continue
        if _should_skip_dir(path.parent):
            continue
        yield path


def build_file_tree(root: Path) -> List[Dict[str, object]]:
    entries: List[Dict[str, object]] = []
    for directory, dirnames, filenames in os.walk(root):
        directory_path = Path(directory)
        rel_dir = _rel(directory_path, root)

        # prune excluded directories in-place so os.walk skips them
        filtered_dirnames = []
        for name in dirnames:
            candidate = Path(rel_dir) / name if rel_dir != "." else Path(name)
            if _should_skip_dir(candidate):
                continue
            filtered_dirnames.append(name)
        dirnames[:] = filtered_dirnames

        if _should_skip_dir(Path(rel_dir)):
            continue

        dir_entry = {
            "path": rel_dir,
            "type": "dir",
            "children": sorted(filtered_dirnames),
            "files": sorted(filenames),
        }
        entries.append(dir_entry)

        for filename in filenames:
            file_path = directory_path / filename
            if _should_skip_dir(file_path.parent.relative_to(root) if file_path.parent != root else file_path.parent):
                continue
            rel_file = _rel(file_path, root)
            stat = file_path.stat()
            file_entry = {
                "path": rel_file,
                "type": "file",
                "size": stat.st_size,
                "mtime": int(stat.st_mtime),
                "extension": file_path.suffix,
            }
            entries.append(file_entry)
    return sorted(entries, key=lambda item: item["path"])


def build_module_index(root: Path) -> Dict[str, str]:
    index: Dict[str, str] = {}
    for path in _iter_files(root, suffix=".py"):
        rel = _rel(path, root)
        module = ".".join(Path(rel).with_suffix("").parts)
        index[module] = rel
    return index


def build_dependency_graph(root: Path, module_index: Dict[str, str]) -> Dict[str, Dict[str, List[str]]]:
    graph: Dict[str, Dict[str, List[str]]] = {}
    for path in _iter_files(root, suffix=".py"):
        rel = _rel(path, root)
        local_targets: Set[str] = set()
        imports: Set[str] = set()
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (SyntaxError, UnicodeDecodeError):
            graph[rel] = {"imports": [], "local": []}
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name)
                    if alias.name in module_index:
                        local_targets.add(module_index[alias.name])
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module:
                    imports.add(module)
                    if module in module_index:
                        local_targets.add(module_index[module])
                for alias in node.names:
                    full = f"{module}.{alias.name}" if module else alias.name
                    imports.add(full)
                    if full in module_index:
                        local_targets.add(module_index[full])
        graph[rel] = {
            "imports": sorted(imports),
            "local": sorted(local_targets),
        }
    return graph


def build_symbol_table(root: Path) -> Dict[str, List[Dict[str, object]]]:
    table: Dict[str, List[Dict[str, object]]] = {}
    for path in _iter_files(root, suffix=".py"):
        rel = _rel(path, root)
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (SyntaxError, UnicodeDecodeError):
            continue
        symbols: List[Dict[str, object]] = []
        for node in tree.body:
            if isinstance(node, ast.FunctionDef):
                symbols.append(
                    {
                        "name": node.name,
                        "kind": "function",
                        "lineno": node.lineno,
                        "end_lineno": getattr(node, "end_lineno", node.lineno),
                    }
                )
            elif isinstance(node, ast.ClassDef):
                symbols.append(
                    {
                        "name": node.name,
                        "kind": "class",
                        "lineno": node.lineno,
                        "end_lineno": getattr(node, "end_lineno", node.lineno),
                    }
                )
        if symbols:
            table[rel] = symbols
    return table


def build_doc_map(root: Path) -> Dict[str, List[str]]:
    docs_by_dir: Dict[str, List[str]] = defaultdict(list)
    for path in _iter_files(root):
        if path.suffix.lower() in DOC_EXTENSIONS:
            rel = _rel(path, root)
            directory = _rel(path.parent, root)
            docs_by_dir[directory].append(rel)
    for key in docs_by_dir:
        docs_by_dir[key].sort()

    doc_map: Dict[str, List[str]] = {}
    for path in _iter_files(root, suffix=".py"):
        rel = _rel(path, root)
        collected: List[str] = []
        current = Path(rel).parent
        while True:
            dir_key = current.as_posix() if current.parts else "."
            if dir_key in docs_by_dir:
                collected.extend(docs_by_dir[dir_key])
            if not current.parts:
                break
            current = current.parent
        if collected:
            doc_map[rel] = sorted(dict.fromkeys(collected))[:5]
    return doc_map


def _is_test_file(rel_path: str) -> bool:
    parts = Path(rel_path).parts
    if "tests" not in parts:
        return False
    name = Path(rel_path).name
    if any(name.startswith(prefix) for prefix in TEST_FILE_PREFIXES):
        return True
    if any(name.endswith(suffix) for suffix in TEST_FILE_SUFFIXES):
        return True
    return False


def build_test_map(root: Path, module_index: Dict[str, str]) -> Dict[str, List[str]]:
    reverse_index: Dict[str, Set[str]] = defaultdict(set)
    for module, rel_path in module_index.items():
        reverse_index[rel_path].add(module)

    mapping: Dict[str, List[str]] = defaultdict(list)
    for path in _iter_files(root, suffix=".py"):
        rel = _rel(path, root)
        if not _is_test_file(rel):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (SyntaxError, UnicodeDecodeError):
            continue
        imports: Set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module:
                    imports.add(module)
        for module in imports:
            if module in module_index:
                target = module_index[module]
                mapping[target].append(rel)
        # fallback heuristic: basename match
        stem = Path(rel).stem
        if stem.startswith("test_"):
            candidate = stem[len("test_"):]
            for module, module_path in module_index.items():
                if module_path.endswith(f"{candidate}.py"):
                    mapping[module_path].append(rel)
        elif stem.endswith("_test"):
            candidate = stem[: -len("_test")]
            for module, module_path in module_index.items():
                if module_path.endswith(f"{candidate}.py"):
                    mapping[module_path].append(rel)
    return {key: sorted(set(values)) for key, values in mapping.items()}


def write_cache(name: str, data: object) -> Path:
    path = cache_path(name)
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    return path


def load_cache(name: str) -> object:
    path = cache_path(name)
    if not path.exists():
        raise FileNotFoundError(f"Cache '{name}' not found at {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def build_all_caches(root: str | Path) -> Dict[str, Path]:
    root_path = Path(root).resolve()
    module_index = build_module_index(root_path)
    outputs = {
        "file_tree": build_file_tree(root_path),
        "deps_graph": build_dependency_graph(root_path, module_index),
        "symbol_table": build_symbol_table(root_path),
        "doc_map": build_doc_map(root_path),
        "test_map": build_test_map(root_path, module_index),
    }
    written = {}
    for name, data in outputs.items():
        written[name] = write_cache(name, data)
    return written


@dataclass
class ContextBudget:
    focus_history: int = 5
    direct_files_max: int = 12
    neighbors_depth: int = 2
    neighbors_per_file: int = 3
    neighbor_signature_budget: int = 500
    docs_tests_budget: int = 2000


def load_budget(budget_config: Dict[str, object]) -> ContextBudget:
    return ContextBudget(
        focus_history=int(budget_config.get("focus_history", 5)),
        direct_files_max=int(budget_config.get("direct_files_max", 12)),
        neighbors_depth=int(budget_config.get("neighbors_depth", 2)),
        neighbors_per_file=int(budget_config.get("neighbors_per_file", 3)),
        neighbor_signature_budget=int(budget_config.get("neighbor_signature_budget", 500)),
        docs_tests_budget=int(budget_config.get("docs_tests_budget", 2000)),
    )


def select_context(
    root: Path,
    focus_files: List[str],
    change_set: List[str],
    explicit_files: Optional[List[str]],
    budget: ContextBudget,
) -> Dict[str, object]:
    module_index = build_module_index(root)
    deps_graph = load_cache("deps_graph") if cache_path("deps_graph").exists() else build_dependency_graph(root, module_index)
    doc_map = load_cache("doc_map") if cache_path("doc_map").exists() else build_doc_map(root)
    test_map = load_cache("test_map") if cache_path("test_map").exists() else build_test_map(root, module_index)

    def _norm(path_str: str) -> str:
        return Path(path_str).as_posix()

    seen: Set[str] = set()
    direct: List[str] = []
    priority_groups = [explicit_files or [], focus_files, change_set]
    for group in priority_groups:
        for item in group:
            rel = _norm(item)
            if rel in seen:
                continue
            seen.add(rel)
            direct.append(rel)
            if len(direct) >= budget.direct_files_max:
                break
        if len(direct) >= budget.direct_files_max:
            break

    neighbors: List[Dict[str, object]] = []
    if budget.neighbors_per_file > 0 and budget.neighbors_depth > 0:
        for origin in direct:
            queue = deque([(origin, 0)])
            added = 0
            visited: Set[str] = {origin}
            while queue and added < budget.neighbors_per_file:
                current, depth = queue.popleft()
                if depth >= budget.neighbors_depth:
                    continue
                edges = deps_graph.get(current, {})
                local_targets = edges.get("local", []) if isinstance(edges, dict) else []
                for target in local_targets:
                    if target in seen or target in visited:
                        continue
                    visited.add(target)
                    neighbors.append({"path": target, "reason": "dependency", "source": origin})
                    seen.add(target)
                    added += 1
                    if added >= budget.neighbors_per_file:
                        break
                    queue.append((target, depth + 1))

    docs: Dict[str, List[str]] = {}
    tests: Dict[str, List[str]] = {}
    remaining_budget = budget.docs_tests_budget
    for path in direct:
        if remaining_budget <= 0:
            break
        doc_candidates = doc_map.get(path, [])
        if doc_candidates:
            docs[path] = doc_candidates[: min(len(doc_candidates), remaining_budget)]
            remaining_budget -= len(docs[path])
        test_candidates = test_map.get(path, [])
        if remaining_budget <= 0:
            continue
        if test_candidates:
            tests[path] = test_candidates[: min(len(test_candidates), remaining_budget)]
            remaining_budget -= len(tests[path])

    manifest = {
        "direct_files": direct,
        "neighbor_files": neighbors,
        "docs": docs,
        "tests": tests,
    }
    return manifest


def main(argv: Optional[List[str]] = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Build deterministic context caches")
    parser.add_argument("--root", default=".")
    parser.add_argument("--show", action="store_true", help="Print written cache paths")
    args = parser.parse_args(argv)

    written = build_all_caches(args.root)
    if args.show:
        for name, path in written.items():
            print(f"[{name}] {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
