#!/usr/bin/env python3

import argparse
import ast
import sys
from pathlib import Path


def strip_comments_and_docstrings(source: str) -> str:
    lines = source.splitlines(keepends=True)

    shebang = ""
    if lines and lines[0].startswith("#!"):
        shebang = lines[0]
        lines = lines[1:]

    source_for_ast = "".join(lines)
    docstring_lines = set()

    try:
        tree = ast.parse(source_for_ast)
        for node in ast.walk(tree):
            if (
                isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
                and node.body
                and isinstance(node.body[0], ast.Expr)
                and isinstance(node.body[0].value, ast.Constant)
                and isinstance(node.body[0].value.value, str)
            ):
                docstring_node = node.body[0]
                for line_no in range(docstring_node.lineno, docstring_node.end_lineno + 1):
                    docstring_lines.add(line_no)
    except SyntaxError:
        pass

    result_lines = []

    for line_num, line in enumerate(lines, start=1):
        if line_num in docstring_lines:
            continue

        new_line = _remove_inline_comment(line)
        result_lines.append(new_line)

    result = "".join(result_lines)

    cleaned_lines = []
    blank_count = 0
    for line in result.splitlines(keepends=True):
        if line.strip() == "":
            blank_count += 1
            if blank_count <= 2:
                cleaned_lines.append(line)
        else:
            blank_count = 0
            cleaned_lines.append(line)

    final_lines = []
    for line in cleaned_lines:
        if line.endswith("\n"):
            final_lines.append(line.rstrip() + "\n")
        else:
            final_lines.append(line.rstrip())

    result = "".join(final_lines)

    result = result.rstrip() + "\n"

    return shebang + result


def _remove_inline_comment(line: str) -> str:

    in_string = False
    string_char = None
    i = 0

    while i < len(line):
        char = line[i]

        if i > 0 and line[i - 1] == "\\":
            i += 1
            continue

        if not in_string:
            if char in ('"', "'"):
                if line[i : i + 3] in ('"""', "'''"):
                    in_string = True
                    string_char = line[i : i + 3]
                    i += 3
                    continue
                else:
                    in_string = True
                    string_char = char
            elif char == "#":
                return line[:i].rstrip() + "\n" if line.endswith("\n") else line[:i].rstrip()
        else:
            if string_char in ('"""', "'''"):
                if line[i : i + 3] == string_char:
                    in_string = False
                    string_char = None
                    i += 3
                    continue
            elif char == string_char:
                in_string = False
                string_char = None

        i += 1

    return line


def count_tokens_approx(text: str) -> int:
    return len(text) // 4


def process_file(path: Path, dry_run: bool = False, verbose: bool = False) -> tuple[int, int]:
    try:
        original = path.read_text()
    except Exception as e:
        print(f"  Error reading {path}: {e}", file=sys.stderr)
        return 0, 0

    original_tokens = count_tokens_approx(original)

    try:
        stripped = strip_comments_and_docstrings(original)
    except Exception as e:
        print(f"  Error processing {path}: {e}", file=sys.stderr)
        return original_tokens, original_tokens

    new_tokens = count_tokens_approx(stripped)
    saved = original_tokens - new_tokens

    if verbose or saved > 0:
        print(f"  {path}: {original_tokens} -> {new_tokens} tokens (saved {saved})")

    if not dry_run and stripped != original:
        path.write_text(stripped)

    return original_tokens, new_tokens


def find_python_files(root: Path, exclude_dirs: set[str]) -> list[Path]:
    files = []
    for path in root.rglob("*.py"):
        if any(part in exclude_dirs for part in path.parts):
            continue
        files.append(path)
    return sorted(files)


def main():
    parser = argparse.ArgumentParser(description="Strip comments and docstrings from Python files")
    parser.add_argument("paths", nargs="*", help="Files or directories to process")
    parser.add_argument("--dry-run", "-n", action="store_true", help="Don't modify files, just report")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show all files, not just changed ones")
    parser.add_argument("--exclude", action="append", default=[], help="Additional directories to exclude")
    args = parser.parse_args()

    exclude_dirs = {"venv", ".venv", "__pycache__", ".git", "build", ".eggs", "*.egg-info"}
    exclude_dirs.update(args.exclude)

    if args.paths:
        files = []
        for p in args.paths:
            path = Path(p)
            if path.is_file():
                files.append(path)
            elif path.is_dir():
                files.extend(find_python_files(path, exclude_dirs))
    else:
        root = Path.cwd()
        files = find_python_files(root, exclude_dirs)

    if not files:
        print("No Python files found")
        return

    print(f"Processing {len(files)} Python files..." + (" (dry run)" if args.dry_run else ""))

    total_original = 0
    total_new = 0

    for f in files:
        orig, new = process_file(f, dry_run=args.dry_run, verbose=args.verbose)
        total_original += orig
        total_new += new

    saved = total_original - total_new
    print(f"\nTotal: {total_original} -> {total_new} tokens (saved {saved}, {100 * saved / total_original:.1f}%)")


if __name__ == "__main__":
    main()
