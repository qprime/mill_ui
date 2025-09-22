# path: web/cliff_server/services/chat_service.py
# type: chat service module
# tags: chat, service, cortex, memory, error_handling
# owner: cliff
# depends_on: cortex/context_manager.py, cortex/distill.py, cortex/client.py, memorieschat_manager.py, memories/sidecar_manager.py
# description: Manages chat interactions, sidecar data, and error handling for AI chats.

from __future__ import annotations

import json
import logging
import traceback
from datetime import datetime

from cortex.client import get_chat_completion
from cortex.context_manager import context
from cortex.distill import distill
from cortex.personas.personas_manager import list_all_personas
from memories.chat_manager import log_chat_turn
from memories.framework import MemoryRegistry
from memories.framework.threading import ensure_chat_session, record_chat_turn
from memories.sidecar_manager import add_sidecar_entry, distill_sidecar, load_sidecar

MAIN_CHAT_MODEL = "gpt-5"
SIDECAR_PERSONA = "system"


def _load_available_personas() -> list[str]:
    try:
        names = list_all_personas("cliff_main")
        return names or ["cliff_core"]
    except Exception:
        logging.exception("Unable to enumerate personas; falling back to cliff_core")
        return ["cliff_core"]


AVAILABLE_PERSONAS = _load_available_personas()
DEFAULT_PERSONA = "cliff_core" if "cliff_core" in AVAILABLE_PERSONAS else AVAILABLE_PERSONAS[0]


def normalize_persona(candidate: str | None) -> str:
    if not candidate:
        return DEFAULT_PERSONA
    persona = str(candidate).strip()
    if persona in AVAILABLE_PERSONAS:
        return persona
    logging.warning("Unknown persona '%s'; defaulting to %s", persona, DEFAULT_PERSONA)
    return DEFAULT_PERSONA


def get_available_personas() -> list[str]:
    return AVAILABLE_PERSONAS


def get_chat_persona(chat_id: str | None) -> str:
    if not chat_id:
        return DEFAULT_PERSONA
    try:
        entries = load_sidecar(chat_id, SIDECAR_PERSONA)
    except Exception:
        logging.exception("Failed to load persona sidecar for chat %s", chat_id)
        return DEFAULT_PERSONA
    for entry in reversed(entries):
        if isinstance(entry, dict) and entry.get("persona"):
            return normalize_persona(entry.get("persona"))
    return DEFAULT_PERSONA


def set_chat_persona(chat_id: str, persona: str) -> str:
    persona_name = normalize_persona(persona)
    entry = {
        "persona": persona_name,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }
    add_sidecar_entry(chat_id, SIDECAR_PERSONA, entry)
    distill_sidecar(chat_id, SIDECAR_PERSONA)
    logging.info("Set persona for chat %s to %s", chat_id, persona_name)
    return persona_name


def generate_chat_reply(data: dict) -> dict:
    """
    Handles the main chat exchange, with robust error handling.
    """
    try:
        raw_input = data.get("input") or data.get("prompt") or ""
        chat_id = data.get("chat_id") or None

        stored_persona = get_chat_persona(chat_id)
        requested_persona = data.get("persona")
        persona = normalize_persona(requested_persona) if requested_persona else stored_persona
        if chat_id and persona != stored_persona:
            stored_persona = set_chat_persona(chat_id, persona)
            persona = stored_persona

        distilled_prompt = distill(raw_input, "turn_distiller")["distilled_text"]
        logging.debug("chat_service.generate_chat_reply.DISTILLED_PROMPT: %s", distilled_prompt)
        system_prompt = context(distilled_prompt, persona, chat_id=chat_id)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": distilled_prompt},
        ]

        try:
            reply = get_chat_completion(messages=messages, model=MAIN_CHAT_MODEL)
        except Exception as model_exc:
            logging.error(
                "Model call failed: %s\n%s", model_exc, traceback.format_exc()
            )
            reply = "[Model error: see logs]"

        log_chat_turn(
            persona=persona,
            chat_id=chat_id,
            user_input=raw_input,
            distilled=distilled_prompt,
            response=reply,
            model=MAIN_CHAT_MODEL,
        )

        turn_memory = None
        # Register chat session/turn in the ledger for provenance (best-effort)
        try:
            if chat_id:
                registry = MemoryRegistry()
                ensure_chat_session(registry, chat_id=chat_id)
                sidecar_path = f"memories/sidecar/{chat_id}_{persona}.json"
                turn_memory = record_chat_turn(
                    registry,
                    chat_id=chat_id,
                    user_input=raw_input or "",
                    response=str(reply) if reply is not None else "",
                    distilled=distilled_prompt or "",
                    model=MAIN_CHAT_MODEL,
                    sidecar_path=sidecar_path,
                    persona=persona,
                )
        except Exception:
            logging.exception("Failed to record chat turn in ledger")

        return {
            "persona": persona,
            "chat_id": chat_id,
            "user_input": raw_input,
            "distilled_input": distilled_prompt,
            "response": reply,
            "model": MAIN_CHAT_MODEL,
            "turn_memory_id": turn_memory.id if turn_memory else None,
            "turn_created_at": turn_memory.created_at if turn_memory else None,
        }
    except Exception as top_exc:
        logging.error(
            "Fatal error in generate_chat_reply: %s\n%s",
            top_exc,
            traceback.format_exc(),
        )
        return {
            "error": "Internal error in chat engine. Please try again or contact support.",
            "details": str(top_exc),
        }


def update_chat_summary(chat_id, summary):
    """
    Update chat summary in sidecar.
    """
    entry = {"summary": summary}
    add_sidecar_entry(chat_id, SIDECAR_PERSONA, entry)
    distill_sidecar(chat_id, SIDECAR_PERSONA)
    logging.info("Updated summary for chat %s", chat_id)


def update_chat_facts(chat_id, facts_json):
    """
    Update chat facts in sidecar.
    """
    if isinstance(facts_json, str):
        facts = json.loads(facts_json)
    else:
        facts = facts_json
    entry = {"facts": facts}
    add_sidecar_entry(chat_id, SIDECAR_PERSONA, entry)
    distill_sidecar(chat_id, SIDECAR_PERSONA)
    logging.info("Updated facts for chat %s", chat_id)


def get_sidecar_data(chat_id):
    """
    Return all sidecar entries (summary, facts, etc) for the chat.
    """
    try:
        turns = load_sidecar(chat_id, SIDECAR_PERSONA)
        meta = {}
        for entry in turns:
            meta.update(entry)
        return meta
    except Exception as exc:
        logging.error("Failed to load sidecar for %s: %s", chat_id, exc)
        return {}
