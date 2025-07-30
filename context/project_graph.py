"""
ProjectGraph Generator for CLIFF AI

Scans the project directory to generate a module/file/dep graph as JSON.
- CLI mode: usable as a command-line tool
- Importable: callable from other scripts or RAG pipelines

Usage:
    python project_graph.py <root_dir> [-o OUTPUT]
"""

import os
import json
import re
import argparse
from collections import defaultdict

DEFAULT_INCLUDE_EXTS = (".py", ".js")
DEFAULT_EXCLUDE_DIRS = {".git", "venv", ".venv", "__pycache__", "memory"}

def should_include_file(filename, include_exts=DEFAULT_INCLUDE_EXTS):
    return filename.endswith(include_exts)

def should_exclude_dir(dirname):
    return dirname in DEFAULT_EXCLUDE_DIRS

def collect_modules(root_dir):
    modules = set()
    for item in os.listdir(root_dir):
        path = os.path.join(root_dir, item)
        if os.path.isdir(path) and not item.startswith("."):
            modules.add(item)
    return modules

def collect_files_and_links(root_dir, modules, include_exts=DEFAULT_INCLUDE_EXTS, exclude_dirs=DEFAULT_EXCLUDE_DIRS):
    module_files = defaultdict(list)
    link_map = defaultdict(set)
    for root, dirs, files in os.walk(root_dir):
        dirs[:] = [d for d in dirs if not should_exclude_dir(d)]
        rel_root = os.path.relpath(root, root_dir)
        parts = rel_root.split(os.sep)
        if parts[0] not in modules:
            continue
        for file in files:
            if not should_include_file(file, include_exts):
                continue
            module = parts[0]
            rel_path = os.path.join(rel_root, file)
            abs_path = os.path.join(root, file)
            module_files[module].append(rel_path)
            update_links(module, abs_path, modules, link_map)
    return module_files, link_map

def update_links(current_module, filepath, modules, link_map):
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            text = f.read()
    except Exception:
        return
    for module in modules:
        if module == current_module:
            continue
        if re.search(rf'\bimport {re.escape(module)}\b', text) or f"{module}/" in text:
            link_map[current_module].add(module)

def generate_project_graph(
    root_dir,
    include_exts=DEFAULT_INCLUDE_EXTS,
    exclude_dirs=DEFAULT_EXCLUDE_DIRS,
):
    modules = collect_modules(root_dir)
    module_files, link_map = collect_files_and_links(root_dir, modules, include_exts, exclude_dirs)
    output = {"modules": []}
    for module in sorted(module_files.keys()):
        output["modules"].append({
            "name": module,
            "files": sorted(module_files[module]),
            "links_to": sorted(link_map[module]) if link_map[module] else []
        })
    return output

def write_project_graph(graph, output_path):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(graph, f, indent=2)
    print(f"[INFO] Project graph written to {output_path}")

def print_stats(graph):
    print(f"[STATS] Modules: {len(graph['modules'])}")
    for module in graph["modules"]:
        print(f"  {module['name']}: {len(module['files'])} files, links to {len(module['links_to'])} modules")

def main():
    parser = argparse.ArgumentParser(
        description="Generate a project graph for CLIFF or other codebase."
    )
    parser.add_argument(
        "root_dir",
        help="Root directory of the project to scan.",
    )
    parser.add_argument(
        "-o", "--output",
        help="Write result to this file (default: memory/metadata/project_graph.json)",
        default=None
    )
    args = parser.parse_args()
    root_dir = os.path.abspath(os.path.expanduser(args.root_dir))
    output_file = args.output or os.path.join(root_dir, "memory/metadata/project_graph.json")
    graph = generate_project_graph(root_dir)
    print_stats(graph)
    write_project_graph(graph, output_file)

if __name__ == "__main__":
    main()