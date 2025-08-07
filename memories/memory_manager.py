# path: memoriesmemory_manager.py
# type: memory management
# tags: memory, chat_log, context, jsonl
# owner: cliff
# depends_on: pathlib, json, datetime
# description: Manages chat logs and memory records, allows adding and retrieving memory contexts.

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

        if any(f.suffix in [".md", ".jsonl"] for f in domain.glob("*")):
            contexts.append(domain.name)

        for sub in domain.iterdir():
            if sub.is_dir() and any(
                f.suffix in [".md", ".jsonl"] for f in sub.glob("**/*")
            ):
                contexts.append(f"{domain .name }/{sub .name }")

    return sorted(set(contexts))


def add_to_domain(
    domain: str, text: str, source: str = "unknown", tags: List[str] = []
):
    """
    Append a memory record to a given domain. Writes to memories<domain>/memory_log.jsonl.
    """
    target_path = MEMORY_ROOT / domain / "memory_log.jsonl"
    target_path.parent.mkdir(parents=True, exist_ok=True)

    record = {
        "timestamp": datetime.utcnow().isoformat(),
        "source": source,
        "tags": tags,
        "text": text,
    }

    with target_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def get_memory_path(domain: str, subpath: str = "") -> Path:
    """
    Returns a resolved path under memories<domain>/<subpath>
    """
    return MEMORY_ROOT / domain / subpath


def get_chat_log_paths(
    chat_id: str, persona: str, domain: str = "chatting/chat_logs"
) -> dict:
    base = MEMORY_ROOT / domain / persona / chat_id
    return {
        "dir": base,
        "full_log": base / "full_log.jsonl",
        "sidecar": base / "sidecar.json",
    }


def ensure_chat_log_folder(
    chat_id: str, persona: str, domain: str = "chatting/chat_logs"
) -> Path:
    paths = get_chat_log_paths(chat_id, persona, domain)
    paths["dir"].mkdir(parents=True, exist_ok=True)
    return paths


def load_sidecar_summary(chat_id: str, persona: str, max_turns: int = 5) -> str:
    """
    Load the most recent turns from a chat sidecar for use in context.
    Returns a formatted string or "" if not found.
    """
    paths = get_chat_log_paths(chat_id, persona)
    sidecar_path = paths["sidecar"]
    from pprint import pprint

    pprint(
        f"[memory_manager.py][🧪 load_sidecar_summary] Looking for: {sidecar_path .resolve ()}"
    )
    if not sidecar_path.exists():
        return ""

    try:
        with open(sidecar_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            turns = data.get("turns", [])[-max_turns:]
    except Exception as e:
        print(f"[memory_manager.py][load_sidecar_summary] Failed to read sidecar: {e }")
        return ""

    formatted = []
    for turn in turns:
        formatted.append(f"🧑 {turn .get ('input','').strip ()}")
        formatted.append(f"🤖 {turn .get ('response','').strip ()}")
    return "\n".join(formatted)
