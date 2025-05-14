# scripts/metadata/update_script_registry.py
# Scans scripts/ folders and builds/updates script_registry.jsonl

import os
import json
from datetime import datetime

SCRIPT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
REGISTRY_PATH = os.path.join(SCRIPT_ROOT, "metadata", "script_registry.jsonl")


def extract_docstring(path):
    try:
        with open(path, "r") as f:
            lines = f.readlines()
        if lines and lines[0].strip().startswith('"""'):
            doc = []
            for line in lines[1:]:
                if line.strip().startswith('"""'):
                    break
                doc.append(line.strip())
            return " ".join(doc).strip()
    except Exception as e:
        print(f"Failed to read {path}: {e}")
    return ""


def scan_scripts():
    script_entries = []
    for root, _, files in os.walk(SCRIPT_ROOT):
        for file in files:
            if file.endswith(".py") and file != os.path.basename(__file__):
                path = os.path.join(root, file)
                rel_path = os.path.relpath(path, SCRIPT_ROOT)
                doc = extract_docstring(path)
                script_entries.append({
                    "script_path": rel_path,
                    "name": os.path.splitext(file)[0],
                    "description": doc or "No docstring found.",
                    "last_verified": datetime.now().isoformat(),
                    "category": os.path.basename(os.path.dirname(path)),
                    "tags": []
                })
    return script_entries


def save_registry(entries):
    with open(REGISTRY_PATH, "w") as f:
        for entry in entries:
            f.write(json.dumps(entry) + "\n")
    print(f"Wrote {len(entries)} entries to {REGISTRY_PATH}")


if __name__ == "__main__":
    entries = scan_scripts()
    save_registry(entries)
