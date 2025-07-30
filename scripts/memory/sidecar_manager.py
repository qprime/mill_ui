# sidecar_manager.py

from pathlib import Path
from typing import List, Dict, Any
import json
from scripts.llm.llm_tools import distill_sidecar_llm 
from scripts.memory.memory_manager import get_chat_log_paths, ensure_chat_log_folder


def get_sidecar_path(chat_id: str, persona: str) -> Path:
    ensure_chat_log_folder(chat_id, persona)
    paths = get_chat_log_paths(chat_id, persona)
    path = paths.get("sidecar")
    if path is None:
        raise RuntimeError(f"No sidecar path for chat_id={chat_id} persona={persona}")
    return Path(path)

def load_sidecar(chat_id: str, persona: str) -> List[Dict[str, Any]]:
    path = get_sidecar_path(chat_id, persona)
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_sidecar(chat_id: str, persona: str, entries: List[Dict[str, Any]]):
    path = get_sidecar_path(chat_id, persona)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2)

def add_sidecar_entry(chat_id: str, persona: str, entry: Dict[str, Any]):
    entries = load_sidecar(chat_id, persona)
    entries.append(entry)
    save_sidecar(chat_id, persona, entries)

def distill_sidecar(chat_id: str, persona: str) -> List[Dict[str, Any]]:
    entries = load_sidecar(chat_id, persona)
    distilled = distill_sidecar_llm(entries)
    save_sidecar(chat_id, persona, distilled)
    return distilled

def get_curated_sidecar(chat_id: str, persona: str) -> List[Dict[str, Any]]:
    """Load or distill sidecar as needed (e.g. on size, time, user command)."""
    entries = load_sidecar(chat_id, persona)
    # Example: distill if entries > 10, or always distill per policy
    if len(entries) > 10:
        return distill_sidecar(chat_id, persona)
    return entries

def prune_conflicting_sidecar_entries(chat_id: str, persona: str, code_context: str) -> None:
    """Remove or tag any sidecar entries now obsolete due to updated canonical context."""
    entries = load_sidecar(chat_id, persona)
    pruned = [
        e for e in entries
        if not (e['type'] == "code" and e['content'] in code_context)
    ]
    save_sidecar(chat_id, persona, pruned)

def update_sidecar_field(chat_id: str, persona: str, field: str, value: Any):
    path = get_sidecar_path(chat_id, persona)
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = {"chat_id": chat_id}
    data[field] = value
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
