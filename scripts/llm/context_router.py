"""
context_router.py

Routes prompt context for CLIFF AI using OpenAI GPT-4.1-min only.
All legacy fallback logic and Phi/Llama references have been removed.
Returns context suggestion, persona, confidence, and clarify flag.

"""

import json
from scripts.memory.memory_manager import get_known_contexts
from scripts.llm.client import get_chat_completion

OPENAI_MODEL = "gpt-4.1-mini"

# Preload valid context paths
KNOWN_CONTEXTS = get_known_contexts()

def route_context(prompt: str, active_persona: str | None = None, active_context: list[str] | None = None) -> dict:
    persona = active_persona or "cliff_core"

    # If explicit context provided, return it with full confidence.
    if active_context:
        return {
            "persona": persona,
            "suggested_context": [c for c in active_context if c in KNOWN_CONTEXTS],
            "confidence": 1.0,
            "clarify": False
        }

    # Compose system prompt
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
        content = get_chat_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            model=OPENAI_MODEL,
            temperature=0.0,
            max_tokens=128,
        ).strip()
        result = parse_tag_output(content)
    except Exception as e:
        print("[context_router.py][route_context] LLM call failed:", e)
        result = {
            "persona": persona,
            "suggested_context": ["development"],
            "confidence": 0.0,
            "clarify": True
        }

    result["persona"] = persona
    if persona != "assistant":
        result["suggested_context"] = [c for c in result["suggested_context"] if not c.startswith("personal/")]

    if not result["suggested_context"]:
        result["suggested_context"] = ["development"]
    result.setdefault("confidence", 0.0)
    result.setdefault("clarify", False)
    return result


def parse_tag_output(text: str) -> dict:
    """
    Parses the output of the context classification model.
    Expects lines like:
      CONTEXT: context_a, context_b
      CONFIDENCE: 0.95
      CLARIFY: false
    """
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
        elif not line or not ":" in line:
            break

    return result
