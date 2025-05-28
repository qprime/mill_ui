import os
import json
from pathlib import Path
from datetime import datetime
from collections import deque

from scripts.memory.memory_manager import get_chat_log_paths, ensure_chat_log_folder
from scripts.llm.personas import get_personas


# Max turns to retain in sidecar
MAX_TURNS = 5


def get_chat_log_path(context: str, chat_id: str) -> Path:
    return Path(f"memory/chat_logs/{context}/{chat_id}/full_log.jsonl")


def get_sidecar_path(context: str, chat_id: str) -> Path:
    return Path(f"memory/chat_logs/{context}/{chat_id}/sidecar.json")


def ensure_chat_folder(context: str, chat_id: str) -> None:
    path = Path(f"memory/chat_logs/{context}/{chat_id}")
    path.mkdir(parents=True, exist_ok=True)


def append_to_chat_log(persona: str, chat_id: str, entry: dict) -> None:
    ensure_chat_log_folder(chat_id, persona)
    paths = get_chat_log_paths(chat_id, persona)
    with open(paths["full_log"], "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")

def update_sidecar(persona: str, chat_id: str, turn_data: dict) -> None:
    ensure_chat_log_folder(chat_id, persona)
    paths = get_chat_log_paths(chat_id, persona)
    sidecar_path = paths["sidecar"]

    if sidecar_path.exists():
        with open(sidecar_path, "r", encoding="utf-8") as f:
            state = json.load(f)
    else:
        state = {"chat_id": chat_id, "turns": []}

    turns = deque(state.get("turns", []), maxlen=MAX_TURNS)
    turns.append({
        "timestamp": datetime.utcnow().isoformat() + "Z",
        **turn_data
    })

    state["turns"] = list(turns)
    with open(sidecar_path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)



# Convenience wrapper

def log_chat_turn(persona: str, chat_id: str = None,
                  user_input: str = "", cleaned: str = "",
                  distilled: str = "", routing: dict = None,
                  response: str = "", model: str = "") -> None:
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
    print(f"[🧠 log_chat_turn] Called with chat_id={chat_id}, persona={persona}")

    append_to_chat_log(persona, chat_id, turn)
    update_sidecar(persona, chat_id, turn)

    from scripts.chatting.prune_sidecar import prune_sidecar
    prune_sidecar(chat_id, persona)


