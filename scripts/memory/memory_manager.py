from pathlib import Path
from typing import List
import json
from datetime import datetime

MEMORY_ROOT = Path(__file__).resolve().parents[2] / "memory"

def get_known_contexts() -> List[str]:
    """
    Return all valid memory context paths in the form:
    - 'domain/' if content is directly inside (e.g., chat_logs/2025-05-03.jsonl)
    - 'domain/subdomain' if nested folders contain valid content
    """
    contexts = []

    for domain in MEMORY_ROOT.iterdir():
        if not domain.is_dir():
            continue

        # Include domain itself if it has .md or .jsonl
        if any(f.suffix in [".md", ".jsonl"] for f in domain.glob("*")):
            contexts.append(domain.name)

        # Include subfolders if they contain valid content
        for sub in domain.iterdir():
            if sub.is_dir() and any(f.suffix in [".md", ".jsonl"] for f in sub.glob("**/*")):
                contexts.append(f"{domain.name}/{sub.name}")

    return sorted(set(contexts))

def add_to_domain(domain: str, text: str, source: str = "unknown", tags: List[str] = []):
    """
    Append a memory record to a given domain. Writes to memory/<domain>/memory_log.jsonl.
    """
    target_path = MEMORY_ROOT / domain / "memory_log.jsonl"
    target_path.parent.mkdir(parents=True, exist_ok=True)

    record = {
        "timestamp": datetime.utcnow().isoformat(),
        "source": source,
        "tags": tags,
        "text": text
    }

    with target_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")