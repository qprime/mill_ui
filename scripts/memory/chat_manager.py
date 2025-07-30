import os
import json
from pathlib import Path
from datetime import datetime

from scripts.memory.memory_manager import get_chat_log_paths, ensure_chat_log_folder
from scripts.memory.sidecar_manager import add_sidecar_entry, distill_sidecar

def append_to_chat_log(persona: str, chat_id: str, entry: dict) -> None:
    """
    Append a chat turn entry to the full JSONL log.
    """
    ensure_chat_log_folder(chat_id, persona)
    paths = get_chat_log_paths(chat_id, persona)
    with open(paths["full_log"], "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")

def log_chat_turn(persona: str, chat_id: str = None,
                  user_input: str = "", cleaned: str = "",
                  distilled: str = "", routing: dict = None,
                  response: str = "", model: str = "") -> None:
    """
    Log a chat turn to both the full log and the sidecar (session memory).
    Distillation is triggered after each turn.
    """
    if chat_id is None:
        raise ValueError("log_chat_turn requires a valid chat_id")

    entry_time = datetime.utcnow().isoformat() + "Z"

    turn = {
        "timestamp": entry_time,
        "input": user_input,
        "cleaned": cleaned,
        "distilled": distilled,
        "routing": routing or {},
        "response": response,
        "model": model
    }
    print(f"[chat_logger.py][🧠 log_chat_turn] Called with chat_id={chat_id}, persona={persona}")

    append_to_chat_log(persona, chat_id, turn)
    add_sidecar_entry(chat_id, persona, turn)
    distill_sidecar(chat_id, persona)
