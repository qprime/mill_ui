# path: continuum/project_graph.py
# type: graph_builder
# tags: project, dependency, graph, metadata
# owner: cliff
# depends_on: continuum/file_crawl.py
# description: Constructs a dependency graph of project modules and files.

import re
import json
from pathlib import Path
from collections import defaultdict
import tiktoken
from continuum.file_crawl import find_files, is_excluded

MODULE_DIRS = [
    "cortex",
    "skills",
    "continuum",
    "web",
    "memory",
]

HEADER_FIELD_RE = re.compile(r'#\s*(\w+):\s*(.*)')

def parse_metadata_header(path: Path):
    meta = {}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                if not line.strip().startswith("#"):
                    break
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

def rel_path(path: Path, root_dir: Path):
    try:
        return str(path.resolve().relative_to(root_dir.resolve()))
    except Exception:
        return str(path.name)

def module_for_file(path: Path):
    parts = path.parts
    for mod in MODULE_DIRS:
        if mod in parts:
            return mod
    return "root"

def model_tokens(s, model_name="gpt-4.1"):
    try:
        enc = tiktoken.encoding_for_model(model_name)
    except KeyError:
        enc = tiktoken.get_encoding("cl100k_base")
    return len(enc.encode(s))

def build_project_graph(root_dir=".", minified=False, model_name: str = "gpt-4.1"):
    modules = defaultdict(lambda: {
        "files": [],
        "links_to": set(),
        "type": None,
        "tags": None,
        "owner": None,
        "description": None
    })

    py_files = find_files(Path(root_dir), allowed_ext=[".py"])
    for path in py_files:
        if is_excluded(path):
            continue
        rel = rel_path(path, root_dir)
        mod = module_for_file(path)
        meta = parse_metadata_header(path)
        file_entry = {
            "name": rel,
            "links_to": [],
        }
        for k in ["type", "tags", "owner", "description"]:
            if k in meta:
                file_entry[k] = meta[k]
        modules[mod]["files"].append(file_entry)

        if path.name in {"__init__.py", "main.py"}:
            for k in ["type", "tags", "owner", "description"]:
                if k in meta:
                    modules[mod][k] = meta[k]

        try:
            with open(path, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip().startswith("import ") or line.strip().startswith("from "):
                        for other_mod in MODULE_DIRS:
                            if f"{other_mod}." in line or f"{other_mod}/" in line:
                                modules[mod]["links_to"].add(other_mod)
        except Exception:
            pass

    output = []
    for mod, d in modules.items():
        obj = {"name": mod}
        for key in ["type", "tags", "owner", "description"]:
            if d[key]:
                obj[key] = d[key]
        obj["files"] = d["files"]
        if d["links_to"]:
            obj["links_to"] = sorted(d["links_to"] - {mod})
        output.append(obj)

    summary = {
        "module_count": len(output),
        "file_count": sum(len(m["files"]) for m in output),
    }
    result = {"summary": summary, "modules": sorted(output, key=lambda x: x["name"])}

    # Token stats
    per_module_tokens = {}
    total_tokens = 0

    # Minified JSON for token count
    json_modules = json.dumps(result["modules"], separators=(',', ':'))
    for mod in result["modules"]:
        mod_json = json.dumps(mod, separators=(',', ':'))
        n_tokens = model_tokens(mod_json)
        per_module_tokens[mod["name"]] = n_tokens
        total_tokens += n_tokens

    token_stats = {
        "total": total_tokens,
        "per_module": per_module_tokens,
        "module_count": summary["module_count"],
        "file_count": summary["file_count"]
    }

    return result, token_stats

def print_stats(stats: dict):
    print(f"[STATS] Modules: {stats['module_count']}")
    print(f"[STATS] Files: {stats['file_count']}")
    print(f"[STATS] Total tokens: {stats['total']}")
    if stats["per_module"]:
        top5 = sorted(stats["per_module"].items(), key=lambda x: -x[1])[:5]
        print("[STATS] Top 5 largest modules (by tokens):")
        for mod, tokens in top5:
            print(f"  {mod}: {tokens} tokens")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=str, default='.', help='Project root directory')
    parser.add_argument('--out', type=str, default='project_graph.json', help='Output file')
    parser.add_argument('--minified', action='store_true', help='Minified JSON (smaller, no indent)')
    parser.add_argument('--model-name', default='gpt-4.1', help='Tokenizer model name for stats')
    args = parser.parse_args()

    graph, stats = build_project_graph(args.root, minified=args.minified, model_name=args.model_name)
    with open(args.out, "w", encoding="utf-8") as f:
        if args.minified:
            json.dump(graph, f, separators=(',', ':'), sort_keys=True)
        else:
            json.dump(graph, f, indent=2, sort_keys=True)
    print(f"Project graph written to {args.out}")
    print_stats(stats)
