# path: continuum/ast_context.py
# type: code_structure_extractor
# tags: ast, signature, class, function, structure, summary
# owner: cliff
# depends_on: none
# description: Extracts per-file Python code structure (classes, methods, functions, imports) as a minimal AST summary for LLM context and code navigation.

import ast
import argparse
import json
from pathlib import Path
import tiktoken

EXCLUDE_DIRS = {'.venv', 'venv', 'env', '__pycache__', '.git', '.mypy_cache', '.idea', '.tox', 'site-packages'}

def is_excluded(path: Path) -> bool:
    return any(part in EXCLUDE_DIRS for part in path.parts)

def extract_ast_summary(path: Path):
    with open(path, 'r', encoding='utf-8') as f:
        source = f.read()
    tree = ast.parse(source, filename=str(path))
    result = {}

    # Imports
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.append({"type": "import", "names": [alias.name for alias in node.names]})
        elif isinstance(node, ast.ImportFrom):
            imports.append({"type": "from", "module": node.module, "names": [alias.name for alias in node.names]})
    if imports:
        result["imports"] = imports

    # Classes (and their methods)
    classes = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            cls = {"name": node.name}
            methods = []
            for item in node.body:
                if isinstance(item, ast.FunctionDef):
                    methods.append({
                        "name": item.name,
                        "args": [arg.arg for arg in item.args.args]
                    })
            if methods:
                cls["methods"] = methods
            classes.append(cls)
    if classes:
        result["classes"] = classes

    # Top-level functions
    functions = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            functions.append({
                "name": node.name,
                "args": [arg.arg for arg in node.args.args]
            })
    if functions:
        result["functions"] = functions

    return result

def count_tokens(text: str, model_name: str = "gpt-4.1"):
    try:
        enc = tiktoken.encoding_for_model(model_name)
    except KeyError:
        enc = tiktoken.get_encoding("cl100k_base")
    return len(enc.encode(text))

def generate_ast_context(
    root_dir: str,
    output_path: str = None,
    model_name: str = "gpt-4.1"
) -> tuple[dict, dict]:
    root = Path(root_dir)
    ast_index = {}
    per_file_tokens = {}
    total_tokens = 0
    for path in root.rglob("*.py"):
        if is_excluded(path):
            continue
        rel_path = str(path.relative_to(root))
        summary = extract_ast_summary(path)
        if summary:
            ast_index[rel_path] = summary
            minified = json.dumps(summary, separators=(',', ':'))
            tokens = count_tokens(minified, model_name=model_name)
            per_file_tokens[rel_path] = tokens
            total_tokens += tokens
    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(ast_index, f, separators=(',', ':'))
    stats = {
        "per_file": per_file_tokens,
        "total": total_tokens,
        "file_count": len(per_file_tokens)
    }
    return ast_index, stats

def print_stats(stats: dict):
    print(f"[STATS] Files included: {stats['file_count']}")
    print(f"[STATS] Total tokens: {stats['total']}")
    if stats["per_file"]:
        top5 = sorted(stats["per_file"].items(), key=lambda x: -x[1])[:5]
        print("[STATS] Top 5 largest files (by tokens):")
        for fname, tokens in top5:
            print(f"  {fname}: {tokens} tokens")

def main():
    parser = argparse.ArgumentParser(description="Generate minimal AST context for Python project")
    parser.add_argument("root_dir", help="Root directory to scan")
    parser.add_argument("-o", "--output", help="Write output to file (minified JSON)")
    parser.add_argument("--model-name", default="gpt-4.1")
    args = parser.parse_args()

    ast_index, stats = generate_ast_context(args.root_dir, args.output, model_name=args.model_name)
    if not args.output:
        print(json.dumps(ast_index, separators=(',', ':')))
    print_stats(stats)

if __name__ == "__main__":
    main()
