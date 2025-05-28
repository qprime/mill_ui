import json
from pathlib import Path
from scripts.chatting.chat_logger import get_chat_log_paths
from scripts.distillation.cleaner import clean_text
from scripts.distillation.distill_text import distill_text

# === Config ===
PRUNE_ENABLED = True
DISTILL_ENABLED = True
MAX_TURNS = 5  # number of turns to retain post-pruning

def prune_sidecar(chat_id: str, persona: str) -> None:
    if not PRUNE_ENABLED:
        return

    path = get_chat_log_paths(chat_id, persona)["sidecar"]
    if not path.exists():
        print(f"[prune_sidecar] No sidecar found at: {path}")
        return

    try:
        with open(path, "r", encoding="utf-8") as f:
            turns = json.load(f).get("turns", [])
    except Exception as e:
        print(f"[prune_sidecar] Failed to read sidecar: {e}")
        return

    cleaned_turns = []
    for turn in turns:
        input_clean = clean_text(turn.get("input", ""))
        response_clean = clean_text(turn.get("response", ""))

        if DISTILL_ENABLED:
            try:
                distilled = distill_text(input_clean, {
                    "persona": persona,
                    "task_type": "summary",
                    "tone": "neutral",
                    "urgency": "low"
                }, strict_mode=True)
                input_clean = distilled["distilled_text"]
            except Exception as e:
                print(f"[prune_sidecar] Distillation failed on turn: {e}")

        cleaned_turns.append({
            "input": input_clean.strip(),
            "response": response_clean.strip()
        })

    trimmed = cleaned_turns[-MAX_TURNS:]

    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"turns": trimmed}, f, indent=2)
        print(f"[prune_sidecar] Wrote {len(trimmed)} distilled turns to {path}")
    except Exception as e:
        print(f"[prune_sidecar] Failed to write sidecar: {e}")
