"""Generate trimmed code context snapshots for AI analysis."""
from __future__ import annotations

import argparse
import ast
import importlib
import os
from pathlib import Path
from typing import Iterable, List, Optional

try:
    import tiktoken
    _ENCODING = tiktoken.get_encoding("cl100k_base")
except Exception:  # pragma: no cover - optional dependency
    _ENCODING = None

ALLOWED_EXTENSIONS = {
    ".py",
    ".md",
    ".rst",
    ".txt",
    ".json",
    ".toml",
    ".yaml",
    ".yml",
    ".ini",
}

EXCLUDE_DIRS = {
    "__pycache__",
    ".git",
    ".hg",
    ".svn",
    ".vscode",
    ".idea",
    "node_modules",
    "dist",
    "build",
    ".venv",
    "venv",
    "env",
    ".mypy_cache",
    ".pytest_cache",
}


class _DocstringStripper(ast.NodeTransformer):
    """Remove docstrings from modules, classes, and functions."""

    def visit_Module(self, node: ast.Module) -> ast.AST:
        self.generic_visit(node)
        if node.body and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant) and isinstance(node.body[0].value.value, str):
            node.body = node.body[1:]
        return node

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        self.generic_visit(node)
        if node.body and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant) and isinstance(node.body[0].value.value, str):
            node.body = node.body[1:]
        return node

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AST:
        self.generic_visit(node)
        if node.body and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant) and isinstance(node.body[0].value.value, str):
            node.body = node.body[1:]
        return node

    def visit_ClassDef(self, node: ast.ClassDef) -> ast.AST:
        self.generic_visit(node)
        if node.body and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant) and isinstance(node.body[0].value.value, str):
            node.body = node.body[1:]
        return node


def _normalise_blank_lines(text: str) -> str:
    lines: List[str] = []
    blank_run = 0
    for line in text.splitlines():
        stripped = line.rstrip()
        if stripped:
            blank_run = 0
            lines.append(stripped)
        else:
            blank_run += 1
            if blank_run <= 1:
                lines.append("")
    return "\n".join(lines).strip() + "\n"


def _strip_python(source: str, path: Path) -> str:
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        return _normalise_blank_lines(source)
    tree = _DocstringStripper().visit(tree)
    ast.fix_missing_locations(tree)
    try:
        cleaned = ast.unparse(tree)
    except Exception:  # pragma: no cover - extremely rare
        cleaned = source
    return _normalise_blank_lines(cleaned)


def _strip_generic(text: str) -> str:
    return _normalise_blank_lines(text)


def _iter_source_files(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative_parts = path.relative_to(root).parts
        if any(part in EXCLUDE_DIRS or part.startswith(".") for part in relative_parts[:-1]):
            continue
        if path.suffix.lower() not in ALLOWED_EXTENSIONS:
            continue
        yield path


def _resolve_target(target: str) -> Path:
    potential = Path(target)
    if potential.exists():
        resolved = potential.resolve()
        return resolved if resolved.is_dir() else resolved.parent

    module = importlib.import_module(target)
    if getattr(module, "__path__", None):
        # Package
        return Path(next(iter(module.__path__))).resolve()
    if getattr(module, "__file__", None):
        return Path(module.__file__).resolve().parent
    raise ValueError(f"Unable to resolve target '{target}'")


def _render_file(root: Path, path: Path) -> str:
    rel = path.relative_to(root)
    header = [
        "=====================================",
        f"FILE: ./{rel.as_posix()}",
        "=====================================",
    ]
    text = path.read_text(encoding="utf-8", errors="replace")
    if path.suffix.lower() == ".py":
        body = _strip_python(text, path)
    else:
        body = _strip_generic(text)
    return "\n".join(header + [body.rstrip(), ""])  # extra newline between files


def _count_tokens(text: str) -> int:
    if _ENCODING is None:
        return len(text.split())
    return len(_ENCODING.encode(text))


def build_context(target: str, output: Optional[Path] = None) -> Path:
    root = _resolve_target(target)
    if not root.exists():
        raise FileNotFoundError(f"Target '{target}' does not exist")

    files = list(_iter_source_files(root))
    if not files:
        raise RuntimeError(f"No source files found under '{root}'")

    chunks = [
        _render_file(root, path)
        for path in files
    ]
    content = "\n".join(chunks).rstrip() + "\n"

    if output is None:
        output = root / "code_context.txt"
    else:
        output = output.resolve()
        output.parent.mkdir(parents=True, exist_ok=True)

    output.write_text(content, encoding="utf-8")

    tokens = _count_tokens(content)
    print(f"[build_context] wrote {output} ({len(files)} files, {tokens} tokens)")
    return output


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Generate a compact code snapshot for AI analysis.")
    parser.add_argument("target", help="Module path or filesystem path to summarise")
    parser.add_argument("--output", help="Optional output file path", type=Path)
    args = parser.parse_args(argv)

    try:
        build_context(args.target, args.output)
    except Exception as exc:  # pragma: no cover - CLI surface
        print(f"[build_context] error: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
