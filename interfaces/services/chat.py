from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional
import logging, traceback

from cortex.context_manager import context
from cortex.distill import distill
from cortex.client import get_chat_completion
from memories.chat_manager import log_chat_turn
from memories.framework.profile import profile_status, set_active_profile
from memories.sidecar_manager import add_sidecar_entry, load_sidecar, distill_sidecar

__all__ = ["chat_reply"]

MAIN_CHAT_MODEL = "gpt-5"
SIDECAR_PERSONA = "system"
MEMORY_COMMAND_PREFIX = "!memory"

@dataclass(frozen=True)
class ChatConfig:
    model: str = MAIN_CHAT_MODEL
    persona: str = "cliff_core"

def _coerce_text(x: Any) -> str:
    return "" if x is None else str(x)

def _messages(sys: str, user: str) -> list[dict[str, str]]:
    return [{"role": "system", "content": sys}, {"role": "user", "content": user}]

def chat_reply(payload: Mapping[str, Any], config: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    """Public entry: returns a standard dict used by adapters."""
    cfg = ChatConfig(**dict(config)) if isinstance(config, Mapping) else ChatConfig()
    try:
        # normalize caller field names
        raw = _coerce_text(payload.get("input") or payload.get("prompt") or payload.get("message"))
        chat_id = payload.get("chat_id")

        command_reply = _handle_memory_command(raw)
        if command_reply is not None:
            reply = command_reply
            log_chat_turn(
                persona=cfg.persona,
                chat_id=chat_id,
                user_input=raw,
                distilled=raw,
                response=reply,
                model="system",
            )
            return {
                "persona": cfg.persona,
                "chat_id": chat_id,
                "user_input": raw,
                "distilled_input": raw,
                "response": reply,
                "model": "system",
            }

        distilled = distill(raw, "turn_distiller")
        distilled_input = distilled.get("distilled_text", raw)
        logging.debug("chat_service.chat_reply.DISTILLED_PROMPT: %s", distilled_input)

        sys = context(distilled_input, cfg.persona, chat_id=chat_id)

        try:
            reply = get_chat_completion(messages=_messages(sys, distilled_input), model=cfg.model)
        except Exception as e:
            logging.error("Model call failed: %s\n%s", e, traceback.format_exc())
            reply = "[Model error: see logs]"

        try:
            add_sidecar_entry(chat_id, SIDECAR_PERSONA, {"last_user": raw})
            distill_sidecar(chat_id, SIDECAR_PERSONA, reply)
        except Exception as e:
            logging.warning("Sidecar update skipped: %s", e)

        log_chat_turn(
            persona=cfg.persona,
            chat_id=chat_id,
            user_input=raw,
            distilled=distilled_input,
            response=reply,
            model=cfg.model,
        )

        return {
            "persona": cfg.persona,
            "chat_id": chat_id,
            "user_input": raw,
            "distilled_input": distilled_input,
            "response": reply,
            "model": cfg.model,
        }
    except Exception as e:
        logging.error("Fatal in chat_reply: %s\n%s", e, traceback.format_exc())
        return {"error": "internal_error", "details": str(e)}
def _memory_status_message() -> str:
    status = profile_status()
    return f"Memory profile: {status['profile']} (root: {status['root']})"


def _switch_profile(profile: str) -> str:
    set_active_profile(profile, persist=True, seed=True)
    return _memory_status_message()


def _handle_memory_command(raw: str) -> Optional[str]:
    text = raw.strip()
    if not text.lower().startswith(MEMORY_COMMAND_PREFIX):
        return None
    parts = text.split()
    if len(parts) == 1:
        return _memory_status_message()
    action = parts[1].lower()
    if action == "status":
        return _memory_status_message()
    if action in {"profile", "use", "set"} and len(parts) >= 3:
        target = parts[2]
        return f"Switched profile. {_switch_profile(target)}"
    if action in {"test", "testing"}:
        if len(parts) >= 3 and parts[2].lower() in {"off", "disable", "false", "stop"}:
            return f"Test profile disabled. {_switch_profile('main')}"
        return f"Test profile enabled. {_switch_profile('test')}"
    if action in {"main", "prod", "production"}:
        return f"Main profile active. {_switch_profile('main')}"
    return (
        "Unrecognised memory command. Try '!memory status', "
        "'!memory test on', or '!memory profile <name>'."
    )
