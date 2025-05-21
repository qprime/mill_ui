import requests
import json

from .personas import get_persona_prompt


LLAMA_SERVER_URL = "http://192.168.0.179:5050/v1/chat/completions"
MODEL_NAME = "phi-3.5.Q4_K_M"

# --- Persona stub (future switch logic can plug into this) ---
KNOWN_PERSONAS = ["developer", "accountant", "assistant", "lab_manager"]
KNOWN_CONTEXTS = [
    "development/code_chunks",
    "development/project_summaries",
    "lab_manager",
    "cli_logs",
    "voice_pipeline",
    "accounting/expenses",
    "personal_notes",
]

def route_context(prompt: str, active_persona: str | None = None) -> dict:
    system_prompt = (
        "You are a routing assistant for CLIFF AI. "
        "Given a user prompt, return a JSON object with the following format:\n"
        "{\n"
        "  'persona': '<best-fit persona>',\n"
        "  'suggested_context': ['<path1>', '<path2>', ...],\n"
        "  'confidence': <float from 0 to 1>,\n"
        "  'clarify': <true|false>\n"
        "}\n"
        "Only return the JSON. Do not explain or add commentary."
    )

    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.0
    }

    try:
        response = requests.post(LLAMA_SERVER_URL, json=payload, timeout=15)
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"].strip()
        try:
            import json5
            result = json5.loads(content)
        except Exception as e:
            print("[context_router] JSON5 parse failed:", e)
            result = {"persona": "unknown", "suggested_context": ["unknown"], "confidence": 0.0, "clarify": True}


        # Sanity check fields
        result.setdefault("persona", active_persona or "unknown")
        result.setdefault("suggested_context", ["unknown"])
        result.setdefault("confidence", 0.0)
        result.setdefault("clarify", False)
        return result

    except Exception as e:
        print(f"[context_router] Error: {e}")
        return {
            "persona": active_persona or "unknown",
            "suggested_context": ["unknown"],
            "confidence": 0.0,
            "clarify": True
        }


# --- Test harness ---
if __name__ == "__main__":
    test_prompts = [
        "What’s the last thing I committed in CLIFF?",
        "How much did I spend on tools this month?",
        "Show me the CNC job logs for the table legs.",
        "What does 'source' do in Bash?",
        "Hey Cliff, this is Anne. What’s the water bill this month?"
    ]

    for prompt in test_prompts:
        result = route_context(prompt)
        print("\n---")
        print(f"Prompt: {prompt}")
        print(json.dumps(result, indent=2))
