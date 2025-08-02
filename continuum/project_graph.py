"""
AI PROJECT GRAPH.
Encodes the top-level modules, all discovered code files, and their cross-module links.
Optimized for minimal tokens and AI ingestion.
"""

import os
import json
import re
import argparse
from collections import defaultdict

try:
    import tiktoken
except ImportError:
    tiktoken = None

DEFAULT_INCLUDE_EXTS = (".py", ".js")
DEFAULT_EXCLUDE_DIRS = {".git", "venv", ".venv", "__pycache__", "tests"}


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


def collect_files_and_links(
    root_dir,
    modules,
    include_exts=DEFAULT_INCLUDE_EXTS,
    exclude_dirs=DEFAULT_EXCLUDE_DIRS,
    minimize_file_paths=False,
):
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
            if minimize_file_paths:
                rel_path = os.path.basename(rel_path)
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
        if re.search(rf"\bimport {re.escape(module)}\b", text) or f"{module}/" in text:
            link_map[current_module].add(module)


def generate_project_graph(
    root_dir,
    include_exts=DEFAULT_INCLUDE_EXTS,
    exclude_dirs=DEFAULT_EXCLUDE_DIRS,
    minimize_file_paths=False,
):
    modules = collect_modules(root_dir)
    module_files, link_map = collect_files_and_links(
        root_dir,
        modules,
        include_exts,
        exclude_dirs,
        minimize_file_paths=minimize_file_paths,
    )
    output = {"modules": []}
    for module in sorted(module_files.keys()):
        files = sorted(set(module_files[module]))
        links = sorted(link_map[module]) if link_map[module] else []
        output["modules"].append(
            {
                "name": module,
                "files": files,
                "links_to": links,
            }
        )
    return output


def scrub_graph_for_tokens(graph):
    # Remove empty lists, sort lists, strip unneeded whitespace
    for mod in graph.get("modules", []):
        mod["files"] = sorted(set(f.strip() for f in mod.get("files", []) if f.strip()))
        mod["links_to"] = sorted(
            set(s.strip() for s in mod.get("links_to", []) if s.strip())
        )
        # Remove keys that are empty
        empty_keys = [k for k, v in mod.items() if not v]
        for k in empty_keys:
            del mod[k]
    # Optionally, sort the modules by name
    graph["modules"] = sorted(graph["modules"], key=lambda m: m["name"])
    return graph


def count_tokens(text, encoding_name="cl100k_base"):
    if not tiktoken:
        print("[WARNING] tiktoken not installed. Token count unavailable.")
        return None
    enc = tiktoken.get_encoding(encoding_name)
    return len(enc.encode(text))


def write_project_graph(graph, output_path):
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(graph, f, ensure_ascii=False, indent=2)
    print(f"[INFO] Project graph written to {output_path}")


def print_stats(graph, output_text=None):
    print(f"[STATS] Modules: {len(graph['modules'])}")
    for module in graph["modules"]:
        print(
            f"  {module['name']}: {len(module.get('files', []))} files, links to {len(module.get('links_to', []))} modules"
        )
    if output_text:
        tk = count_tokens(output_text)
        if tk is not None:
            print(f"[TOKENS] Output tokens: {tk}")


def main():
    parser = argparse.ArgumentParser(
        description="Generate a project graph for CLIFF or other codebase."
    )
    parser.add_argument(
        "root_dir",
        help="Root directory of the project to scan.",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Write result to this file (default: memory/metadata/project_graph.json)",
        default=None,
    )
    parser.add_argument(
        "--minimize-file-paths",
        action="store_true",
        help="Only store file basenames (reduce tokens but lose hierarchy).",
    )
    args = parser.parse_args()
    root_dir = os.path.abspath(os.path.expanduser(args.root_dir))
    output_file = args.output or os.path.join(
        root_dir, "memory/metadata/project_graph.json"
    )
    graph = generate_project_graph(
        root_dir, minimize_file_paths=args.minimize_file_paths
    )
    graph = scrub_graph_for_tokens(graph)
    output_text = json.dumps(graph, ensure_ascii=False, separators=(",", ":"))
    print_stats(graph, output_text)
    write_project_graph(graph, output_file)


if __name__ == "__main__":
    main()
