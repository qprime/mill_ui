import os
import ast
import json
import argparse
from pathlib import Path
import sys

# Add project root to Python path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT))

# Consistent output path for chunked functions
CHUNKS_DIR = PROJECT_ROOT / "memory" / "development" / "code_chunks"
CHUNKS_DIR.mkdir(parents=True, exist_ok=True)



def extract_chunks(file_path):
    with open(file_path, "r") as f:
        source = f.read()

    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        print(f"❌ Syntax error in {file_path}: {e}")
        return []

    lines = source.splitlines()
    chunks = []

    # Identify where the first def/class occurs
    def_or_class_indices = [node.lineno - 1 for node in tree.body if isinstance(node, (ast.FunctionDef, ast.ClassDef))]
    first_code_index = min(def_or_class_indices) if def_or_class_indices else len(lines)
    if first_code_index > 0:
        preamble = "\n".join(lines[:first_code_index])
        chunks.append({
            "file": str(file_path),
            "name": "preamble",
            "type": "preamble",
            "start_line": 1,
            "end_line": first_code_index,
            "code": preamble
        })

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            start_line = node.lineno - 1
            end_line = max(
                getattr(node, 'end_lineno', start_line + 1),
                node.body[-1].lineno if node.body else start_line + 1
            )
            code_lines = lines[start_line:end_line]
            code = "\n".join(code_lines)
            chunks.append({
                "file": str(file_path),
                "name": node.name,
                "type": type(node).__name__,
                "start_line": start_line + 1,
                "end_line": end_line,
                "code": code
            })
    return chunks


def process_file(file_path, output_dir, debug=False):
    chunks = extract_chunks(file_path)
    if not chunks:
        return

    rel_path = file_path.resolve().relative_to(Path.cwd().resolve())
    out_path = output_dir / rel_path.with_suffix(".json")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if debug:
        for chunk in chunks:
            print(f"\n🔧 {chunk['type']} {chunk.get('name', '')} (lines {chunk['start_line']}-{chunk['end_line']}):")
            print(chunk['code'])

    with open(out_path, "w") as f:
        json.dump(chunks, f, indent=2)
    print(f"✅ Wrote {len(chunks)} chunks from {file_path} to {out_path}")


def walk_path(path, output_dir, debug=False):
    path = Path(path)
    if path.is_file() and path.suffix == ".py":
        process_file(path, output_dir, debug)
    else:
        for file_path in path.rglob("*.py"):
            if "_annotated" in file_path.name:
                continue
            process_file(file_path, output_dir, debug)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", type=str, required=True, help="Path to a file or folder to chunk")
    parser.add_argument("--output", type=str, default=str(CHUNKS_DIR), help="Where to store the chunk JSON")
    parser.add_argument("--debug", action="store_true", help="Print chunks to stdout")
    args = parser.parse_args()

    walk_path(args.path, Path(args.output), debug=args.debug)


if __name__ == "__main__":
    main()
