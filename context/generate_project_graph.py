import os
import json
import re
from collections import defaultdict

ROOT_DIR = os.path.abspath(os.path.expanduser("."))
OUTPUT_FILE = os.path.join(ROOT_DIR, "memory/metadata/project_graph.json")
INCLUDE_EXTS = {".py", ".sh", ".md", ".html"}
PROJECT_MODULES = set()
MODULE_FILES = defaultdict(list)
LINK_MAP = defaultdict(set)

def collect_modules():
    for item in os.listdir(ROOT_DIR):
        path = os.path.join(ROOT_DIR, item)
        if os.path.isdir(path) and not item.startswith("."):
            PROJECT_MODULES.add(item)

def collect_files():
    for root, dirs, files in os.walk(ROOT_DIR):
    # Skip ignored folders
        dirs[:] = [d for d in dirs if d not in {".git", "venv", ".venv", "__pycache__", ".model_cache", "node_modules", "models", "memory"}]

        rel_root = os.path.relpath(root, ROOT_DIR)
        parts = rel_root.split(os.sep)
        if parts[0] not in PROJECT_MODULES:
            continue
        for file in files:
            ext = os.path.splitext(file)[1]
            if ext.lower() in INCLUDE_EXTS:
                module = parts[0]
                rel_path = os.path.join(rel_root, file)
                MODULE_FILES[module].append(rel_path)
                update_links(module, os.path.join(root, file))

def update_links(current_module, filepath):
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            text = f.read()
    except:
        return
    for module in PROJECT_MODULES:
        if module == current_module:
            continue
        if re.search(rf'\bimport {re.escape(module)}\b', text) or f"{module}/" in text:
            LINK_MAP[current_module].add(module)

def write_output():
    output = {"modules": []}
    for module in sorted(MODULE_FILES.keys()):
        output["modules"].append({
            "name": module,
            "files": sorted(MODULE_FILES[module]),
            "links_to": sorted(LINK_MAP[module]) if LINK_MAP[module] else []
        })
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, "w") as f:
        json.dump(output, f, indent=2)
    print(f"✅ Wrote full project graph to {OUTPUT_FILE}")

if __name__ == "__main__":
    collect_modules()
    collect_files()
    write_output()
