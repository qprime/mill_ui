import requests
import json
from .personas import get_persona_prompt, get_personas
from scripts.llm.ai_router import get_router
from scripts.memory.memory_manager import get_known_contexts

LLAMA_SERVER_URL = "http://192.168.0.179:5050/v1/chat/completions"
MODEL_NAME = "phi-3.5.Q4_K_M"
OPENAI_MODEL = "gpt-4o"

# --- Persona stub (future switch logic can plug into this) ---
KNOWN_PERSONAS = get_personas()

KNOWN_CONTEXTS = get_known_contexts()

router_backup = get_router("openai")

def route_context(prompt: str, active_persona: str | None = None, active_context: list[str] | None = None) -> dict:
    persona = active_persona or "cliff_core"

    # If context provided, just return it
    if active_context:
        return {
            "persona": persona,
            "suggested_context": [c for c in active_context if c in KNOWN_CONTEXTS],
            "confidence": 1.0,
            "clarify": False
        }

    # Only context is inferred by LLM now
    system_prompt = (
        "You are a context classification assistant for CLIFF AI.\n"
        "Your task is to choose the most relevant CONTEXT path(s) from the list below\n"
        "based on the user's prompt. These paths are folders where related memory is stored.\n\n"
        f"Valid CONTEXT paths: {', '.join(KNOWN_CONTEXTS)}\n\n"
        "Return only valid paths. Respond in the format:\n"
        "CONTEXT: <comma-separated list of valid CONTEXT paths>\n"
        "CONFIDENCE: <float between 0.0 and 1.0>\n"
        "CLARIFY: <true or false>\n\n"
        "DO NOT include explanation or commentary."
    )

    try:
        payload = {
            "model": MODEL_NAME,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.0
        }

        response = requests.post(LLAMA_SERVER_URL, json=payload, timeout=8)
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"].strip()
        print("[context_router.py][context_router] Phi raw output:")
        print("[context_router.py][context_router] "+content)
        result = parse_tag_output(content)
    except Exception as e:
        print("[context_router.py][context_router] Phi failed, escalating to OpenAI. Reason:", e)
        result = route_with_openai(prompt, system_prompt)

    # Filter context and finalize return
    result["persona"] = persona
    if persona != "assistant":
        result["suggested_context"] = [c for c in result["suggested_context"] if not c.startswith("personal/")]

    if not result["suggested_context"]:
        result["suggested_context"] = ["development"]
    result.setdefault("confidence", 0.0)
    result.setdefault("clarify", False)
    return result



def route_with_openai(prompt: str, system_prompt: str) -> dict:
    try:
        content = router_backup.chat([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ], model=OPENAI_MODEL)
        return parse_tag_output(content)

    except Exception as e:
        print("[context_router.py][context_router] OpenAI fallback also failed:", e)
        return {
            "persona": "unknown",
            "suggested_context": ["unknown"],
            "confidence": 0.0,
            "clarify": True
        }


def parse_tag_output(text: str) -> dict:
    result = {
        "persona": "unknown",
        "suggested_context": [],
        "confidence": 0.0,
        "clarify": False
    }

    for line in text.splitlines():
        line = line.strip()
        if line.startswith("PERSONA:"):
            result["persona"] = line.split(":", 1)[1].strip()
        elif line.startswith("CONTEXT:"):
            result["suggested_context"] = [x.strip() for x in line.split(":", 1)[1].split(",")]
        elif line.startswith("CONFIDENCE:"):
            try:
                result["confidence"] = float(line.split(":", 1)[1].strip())
            except ValueError:
                pass
        elif line.startswith("CLARIFY:"):
            result["clarify"] = "true" in line.lower()
        # Stop if we hit extra commentary
        elif not line or not ":" in line:
            break

    return result
