# path: web/cliff_server/services/chat_service.py
# type: chat service module
# tags: chat, service, cortex, memory, error_handling
# owner: cliff
# depends_on: cortex/context_manager.py, cortex/distill.py, cortex/client.py, memorieschat_manager.py, memories/sidecar_manager.py
# description: Manages chat interactions, sidecar data, and error handling for AI chats.

import logging
import json
from cortex.context_manager import context
from cortex.distill import distill
from cortex.client import get_chat_completion
from memories.chat_manager import log_chat_turn
from memories.sidecar_manager import add_sidecar_entry, load_sidecar, distill_sidecar

MAIN_CHAT_MODEL = "gpt-4.1"
SIDECAR_PERSONA = "system"

import logging
import traceback


def generate_chat_reply(data: dict) -> dict:
    """
    Handles the main chat exchange, with robust error handling.
    """
    try:
        persona = "cliff_core"
        raw_input = data.get("input") or data.get("prompt") or ""
        chat_id = data.get("chat_id", None)

        distilled_prompt = distill(raw_input, "turn_distiller")["distilled_text"]
        print("chat_service.generate_chat_reply.DISTILLED_PROMPT: " + distilled_prompt)
        system_prompt = context(distilled_prompt, persona, chat_id=chat_id)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": distilled_prompt}
        ]

        try:
            reply = get_chat_completion(
                messages=messages,
                model=MAIN_CHAT_MODEL,
            )
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

        return {
            "persona": persona,
            "chat_id": chat_id,
            "user_input": raw_input,
            "distilled_input": distilled_prompt,
            "response": reply,
            "model": MAIN_CHAT_MODEL,
        }
    except Exception as top_exc:
        logging.error(
            "Fatal error in generate_chat_reply: %s\n%s",
            top_exc,
            traceback.format_exc(),
        )
        # Safe minimal error response for the UI/upstream
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
    logging.info(f"Updated summary for chat {chat_id }")


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
    logging.info(f"Updated facts for chat {chat_id }")


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
    except Exception as e:
        logging.error(f"Failed to load sidecar for {chat_id }: {e }")
        return {}
