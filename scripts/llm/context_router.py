import requests
import json
from .personas import get_persona_prompt
from scripts.llm.ai_router import get_router
from scripts.memory.memory_manager import get_known_contexts

LLAMA_SERVER_URL = "http://192.168.0.179:5050/v1/chat/completions"
MODEL_NAME = "phi-3.5.Q4_K_M"
OPENAI_MODEL = "gpt-4o"

# --- Persona stub (future switch logic can plug into this) ---
KNOWN_PERSONAS = ["developer", "accountant", "assistant", "lab_manager"]
KNOWN_CONTEXTS = get_known_contexts()

router_backup = get_router("openai")

def route_context(prompt: str, active_persona: str | None = None) -> dict:
    system_prompt = (
        "You are a routing assistant for CLIFF AI.\n"
        "Your job is to classify user prompts into:\n"
        "- one appropriate PERSONA from the list below\n"
        "- one or more CONTEXT paths from the list below\n\n"
        f"Valid PERSONAS: {', '.join(KNOWN_PERSONAS)}\n"
        f"Valid CONTEXT paths: {', '.join(KNOWN_CONTEXTS)}\n\n"
        "Respond using exactly this format:\n"
        "PERSONA: <one of the valid PERSONAS>\n"
        "CONTEXT: <comma-separated list of valid CONTEXT paths>\n"
        "CONFIDENCE: <float between 0.0 and 1.0>\n"
        "CLARIFY: <true or false>\n\n"
        "You MUST choose only from the valid values above.\n"
        "Do NOT include any commentary, formatting, or explanation."
    )

    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.0
    }

    # Attempt with local Phi
    try:
        response = requests.post(LLAMA_SERVER_URL, json=payload, timeout=8)
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"].strip()
        print("[context_router] Phi raw output:")
        print(content)
        result = parse_tag_output(content)

    except Exception as e:
        print("[context_router] Phi failed, escalating to OpenAI. Reason:", e)
        result = route_with_openai(prompt, system_prompt)

    # Validate persona
    if result.get("persona") not in KNOWN_PERSONAS:
        result["persona"] = active_persona or "assistant"

    # Filter invalid context paths
    result["suggested_context"] = [
        c for c in result.get("suggested_context", []) if c in KNOWN_CONTEXTS
    ]
    if not result["suggested_context"]:
        result["suggested_context"] = ["development/project_summaries"]

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
        print("[context_router] OpenAI fallback also failed:", e)
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
