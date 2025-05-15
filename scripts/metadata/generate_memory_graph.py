import os
import json

ROOT_DIR = os.path.abspath(os.path.expanduser("."))
MEMORY_DIR = os.path.join(ROOT_DIR, "memory")
OUTPUT_FILE = os.path.join(MEMORY_DIR, "metadata/memory_graph.json")

def describe_purpose(name):
    return {
        "development": "Active project code memory (chunks, annotations, summaries)",
        "cliff_state": "CLI usage logs and local system context",
        "chat_logs": "Captured chats for training, recall, and context injection",
        "tasks": "Tracked task memory and per-task files",
        "production": "Stable memory used by active deployed services",
        "personal": "Personal memory domain (chat exports, journal logs)",
        "lab": "Lab device state, inventory, and sensor logs",
        "research": "Experimental or imported research data",
        "accounting": "Usage-based cost tracking and operations accounting",
        "samples": "Memory schema and JSONL format examples",
        "schemas": "Schemas used across memory domains"
    }.get(name, "Unclassified memory domain")

def scan_memory():
    graph = {"domains": []}
    for name in sorted(os.listdir(MEMORY_DIR)):
        path = os.path.join(MEMORY_DIR, name)
        if not os.path.isdir(path) or name.startswith(".") or name == "metadata":
            continue
        components = []
        for root, _, files in os.walk(path):
            for f in files:
                if f.endswith((".json", ".jsonl", ".sqlite3")):
                    rel_path = os.path.relpath(os.path.join(root, f), MEMORY_DIR)
                    components.append(rel_path)
        graph["domains"].append({
            "name": name,
            "path": f"memory/{name}",
            "purpose": describe_purpose(name),
            "components": sorted(components),
            "links_to": []  # Could be inferred later
        })
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, "w") as f:
        json.dump(graph, f, indent=2)
    print(f"✅ Wrote memory graph to {OUTPUT_FILE}")

if __name__ == "__main__":
    scan_memory()
