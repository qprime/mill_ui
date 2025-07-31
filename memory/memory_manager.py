"""
📁 memory_manager.py — CLIFF AI Memory Path and Logging Interface

This module defines how CLIFF AI resolves, creates, and writes to memory files.

🔹 DESIGN PRINCIPLES
- All memory is stored under `memory/<domain>/<context>/`
- Domains represent broad memory types (e.g. `chat_logs`, `voice_logs`, `cliff_state`)
- Contexts are subfolders (e.g. chat ID, session name, timestamp)
- This manager provides safe, central access to memory paths and logging

🔹 KEY FUNCTIONS
- `get_memory_path(domain, subpath)` — resolves arbitrary paths under a domain
- `get_known_contexts()` — discovers all valid paths with memory content
- `add_to_domain(domain, text, source, tags)` — appends a memory log to a domain
- `get_chat_log_paths(chat_id)` — returns full/sidecar paths for per-chat logs
- `ensure_chat_log_folder(chat_id)` — ensures directory exists for new chats

🔹 USAGE PATTERNS
- Use this module for ALL file reads/writes inside `memory/`
- Do not manually hardcode `Path("memory/...")` elsewhere in the project
- Use `add_to_domain()` for simple logging
- Use `get_chat_log_paths()` for structured per-session logging (e.g., Cliff Chat UI)

🔹 FUTURE EXPANSIONS
- Add indexed memory types (e.g., vector, event logs)
- Add timestamped snapshot folders (e.g., `cli_logs/2025-05-27/`)
- Add support for media memory (e.g., image/audio associations)

"""

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

def get_memory_path(domain: str, subpath: str = "") -> Path:
    """
    Returns a resolved path under memory/<domain>/<subpath>
    """
    return MEMORY_ROOT / domain / subpath

def get_chat_log_paths(chat_id: str, persona: str, domain: str = "chatting/chat_logs") -> dict:
    base = MEMORY_ROOT / domain / persona / chat_id
    return {
        "dir": base,
        "full_log": base / "full_log.jsonl",
        "sidecar": base / "sidecar.json"
    }

def ensure_chat_log_folder(chat_id: str, persona: str, domain: str = "chatting/chat_logs") -> Path:
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
    pprint(f"[memory_manager.py][🧪 load_sidecar_summary] Looking for: {sidecar_path.resolve()}")
    if not sidecar_path.exists():
        return ""

    try:
        with open(sidecar_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            turns = data.get("turns", [])[-max_turns:]
    except Exception as e:
        print(f"[memory_manager.py][load_sidecar_summary] Failed to read sidecar: {e}")
        return ""

    formatted = []
    for turn in turns:
        formatted.append(f"🧑 {turn.get('input', '').strip()}")
        formatted.append(f"🤖 {turn.get('response', '').strip()}")
    return "\n".join(formatted)
