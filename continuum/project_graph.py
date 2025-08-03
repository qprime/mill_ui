# path: continuum/project_graph.py
# type: project_graph_generator
# tags: graph, context, cli, file_crawl, metadata
# owner: cliff
# depends_on: continuum/file_crawl.py
# description: Builds a structured, metadata-aware project graph for CLIFF AI, using file_crawl and extracting optional file headers for LLM context.


import re
import json
from pathlib import Path
from collections import defaultdict
from continuum.file_crawl import find_files, is_excluded

# Adjust for your repo layout as needed
MODULE_DIRS = [
    "ai_core",
    "pipelines",
    "continuum",
    "web",
    "memory",   # include if code, else remove
    # Add more top-level dirs as needed
]

# Pattern to match header metadata fields, e.g. "# key: value"
HEADER_FIELD_RE = re.compile(r'#\s*(\w+):\s*(.*)')

def parse_metadata_header(path: Path):
    """
    Reads metadata header from the top of a file, returns dict.
    Returns empty dict if none present.
    """
    meta = {}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                if not line.strip().startswith("#"):
                    break  # Stop at first code/import
                m = HEADER_FIELD_RE.match(line)
                if m:
                    key, value = m.group(1).lower(), m.group(2).strip()
                    if key == "tags":
                        meta[key] = [t.strip() for t in value.split(",")]
                    else:
                        meta[key] = value
            return meta
    except Exception:
        return {}

def rel_path(path: Path):
    """Path relative to repo root, as string."""
    return str(path.relative_to(Path('.').resolve()))

def module_for_file(path: Path):
    """Infers module by top-level folder name."""
    parts = path.parts
    for mod in MODULE_DIRS:
        if mod in parts:
            return mod
    return "root"

def file_links(path: Path):
    """Optionally, parses direct file imports. (Skip for now, add if needed.)"""
    return []

def build_project_graph():
    modules = defaultdict(lambda: {
        "files": [],
        "links_to": set(),
        # new metadata fields (optional, filled if header found)
        "type": None,
        "tags": None,
        "owner": None,
        "description": None
    })

    py_files = find_files(Path('.'), allowed_ext=[".py"])
    for path in py_files:
        rel = rel_path(path)
        mod = module_for_file(path)
        meta = parse_metadata_header(path)
        file_entry = {
            "name": rel,
            "links_to": [],  # Optionally, fill with file-level imports
        }
        # Add metadata if present
        for k in ["type", "tags", "owner", "description"]:
            if k in meta:
                file_entry[k] = meta[k]
        modules[mod]["files"].append(file_entry)

        # Promote module-level metadata if file is __init__.py or main file
        if path.name in {"__init__.py", "main.py"}:
            for k in ["type", "tags", "owner", "description"]:
                if k in meta:
                    modules[mod][k] = meta[k]

        # Parse and add module links (import tree)
        try:
            with open(path, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip().startswith("import ") or line.strip().startswith("from "):
                        for other_mod in MODULE_DIRS:
                            if f"{other_mod}." in line or f"{other_mod}/" in line:
                                modules[mod]["links_to"].add(other_mod)
        except Exception:
            pass

    # Build output: minimal, sorted, omit empty fields
    output = []
    for mod, d in modules.items():
        obj = {"name": mod}
        for key in ["type", "tags", "owner", "description"]:
            if d[key]:
                obj[key] = d[key]
        obj["files"] = d["files"]
        if d["links_to"]:
            obj["links_to"] = sorted(d["links_to"] - {mod})  # Exclude self-links
        output.append(obj)

    # Optional: top-level summary
    summary = {
        "module_count": len(output),
        "file_count": sum(len(m["files"]) for m in output),
    }

    return {"summary": summary, "modules": sorted(output, key=lambda x: x["name"])}

if __name__ == "__main__":
    graph = build_project_graph()
    with open("project_graph.json", "w", encoding="utf-8") as f:
        json.dump(graph, f, indent=2, sort_keys=True)
    print("Project graph written to project_graph.json")
