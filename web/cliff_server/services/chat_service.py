"""Handles chat, context routing, distillation, logging, and sidecar/project memory assembly."""
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[3]))
from scripts.llm.ai_router import get_router
from scripts.llm.context_router import route_context
from scripts.llm.personas_manager import get_legacy_persona_prompt
from scripts.llm.distill_text import distill_text
from scripts.llm.context_loader import load_context_for_persona
from scripts.memory.chat_manager import log_chat_turn
from services.status_service import get_cliff_status

MAIN_CHAT_MODEL = "gpt-4.1"
router = get_router("openai")

def generate_chat_reply(data):
    import time
    raw_input = data.get("prompt", "")
    tone = data.get("tone", "neutral")
    chat_id = data.get("chat_id")
    if not raw_input or not chat_id:
        return {"error": "Missing prompt or chat_id"}
    routing = route_context(raw_input)
    persona = routing.get("persona", "default")
    suggested_context = routing.get("suggested_context", [])
    distilled_result = distill_text(raw_input, {
        "persona": persona,
        "task_type": "specification",
        "tone": tone,
        "urgency": "medium"
    }, strict_mode=True)
    distilled_prompt = distilled_result["distilled_text"]
    system_message = get_legacy_persona_prompt(persona)
    context_blocks = load_context_for_persona(distilled_prompt, persona, suggested_context, chat_id=chat_id)
    sidecar_context = context_blocks["sidecar"]
    project_memory = context_blocks["memory"]
    status = get_cliff_status()
    status_block = "\n".join(f"- {k.replace('_', ' ').capitalize()}: {v}" for k, v in status.items())

    def format_block(block):
        if isinstance(block, str):
            return block
        if isinstance(block, dict):
            return block.get("content", "")
        return str(block)
    full_context = "\n\n".join(map(format_block, [
        "# Recent Conversation (last few turns)",
        sidecar_context or "(No recent interaction yet.)",
        "# Related Project Memory",
        project_memory,
        "# System Runtime Status",
        status_block
    ]))
    augmented_prompt = f"{full_context}\n\nUser asked:\n{distilled_prompt}"
    messages = [system_message, {"role": "user", "content": augmented_prompt}]
    start = time.time()
    reply = router.chat(messages, model=MAIN_CHAT_MODEL)
    end = time.time()
    def count_tokens(text): return len(text.split())
    tokens_in = sum(count_tokens(m["content"]) for m in messages)
    tokens_out = count_tokens(reply)
    latency_ms = int((end - start) * 1000)
    log_chat_turn(
        persona=persona,
        chat_id=chat_id,
        user_input=raw_input,
        cleaned=distilled_result["original_input"]["cleaned_text"],
        distilled=distilled_prompt,
        routing=routing,
        response=reply,
        model=MAIN_CHAT_MODEL
    )
    return {
        "response": reply,
        "rag_empty": project_memory.strip().startswith("⚠️"),
        "model": MAIN_CHAT_MODEL,
        "routing": routing,
        "chat_id": chat_id,
        "distilled_input": distilled_prompt,
        "original_input": distilled_result["original_input"]["cleaned_text"],
        "metrics": {
            "latency_ms": latency_ms,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out
        },
        "debug": {
            "full_context": full_context,
            "distilled_input": distilled_prompt,
            "model": MAIN_CHAT_MODEL,
            "routing": routing,
            "metrics": {
                "latency_ms": latency_ms,
                "tokens_in": tokens_in,
                "tokens_out": tokens_out
            }
        }
    }

def update_chat_summary(chat_id, summary):
    from scripts.memory.sidecar_manager import update_sidecar_field
    update_sidecar_field(chat_id, "cliff_core", "summary", summary)

def update_chat_facts(chat_id, facts_json):
    from scripts.memory.sidecar_manager import update_sidecar_field
    import json
    try:
        facts = json.loads(facts_json)
    except json.JSONDecodeError:
        facts = {}
    update_sidecar_field(chat_id, "cliff_core", "facts", facts)

def get_sidecar_data(chat_id):
    from scripts.chatting.chat_logger import get_chat_log_paths
    persona = "cliff_core"
    paths = get_chat_log_paths(chat_id, persona)
    sidecar_path = paths["sidecar"]
    if not sidecar_path.exists():
        return {"summary": "", "facts": {}}
    try:
        with open(sidecar_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return {"summary": "", "facts": {}}
    return {
        "summary": data.get("summary", ""),
        "facts": data.get("facts", {})
    }
