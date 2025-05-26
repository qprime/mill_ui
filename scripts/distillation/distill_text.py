import requests
import json
from pathlib import Path
from typing import Optional

LLAMA_SERVER_URL = "http://192.168.0.179:5050/v1/chat/completions"
MODEL_NAME = "phi-3.5.Q4_K_M"

DEFAULT_GUIDANCE = {
    "persona": "developer",
    "task_type": "general",
    "tone": "neutral",
    "urgency": "normal"
}

def fill_guidance_defaults(guidance: dict) -> tuple[dict, list[str]]:
    """Fills missing guidance parameters and returns warnings for each default used."""
    warnings = []
    final = guidance.copy()
    for key, value in DEFAULT_GUIDANCE.items():
        if key not in final:
            final[key] = value
            warnings.append(f"guidance parameter '{key}' missing, using default '{value}'")
    return final, warnings

def distill_text(cleaned_text: str, guidance: dict) -> dict:
    """Sends cleaned text to LLM and returns distilled output and metadata."""
    guidance_filled, warnings = fill_guidance_defaults(guidance)

    system_prompt = (
        "You are a distillation engine. Your job is to reduce a cleaned input string to a minimal, logically sound instruction.\n"
        "Use the following constraints:\n"
        f"- persona: {guidance_filled['persona']}\n"
        f"- task_type: {guidance_filled['task_type']}\n"
        f"- tone: {guidance_filled['tone']}\n"
        f"- urgency: {guidance_filled['urgency']}\n\n"
        "Return only the final instruction text."
    )

    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": cleaned_text}
        ],
        "temperature": 0.2
    }

    try:
        response = requests.post(LLAMA_SERVER_URL, json=payload, timeout=15)
        response.raise_for_status()
        distilled = response.json()["choices"][0]["message"]["content"].strip()

    except Exception as e:
        distilled = cleaned_text
        warnings.append(f"LLM request failed: {str(e)}. Outputting cleaned text only.")

    return {
        "distilled_text": distilled,
        "metadata": {
            **guidance_filled,
            "warnings": warnings
        },
        "original_input": {
            "cleaned_text": cleaned_text,
            "guidance": guidance
        }
    }

def batch_distill(
    text_guidance_pairs: list[tuple[str, dict]],
    output_path: Path
) -> None:
    """Processes a batch of cleaned text + guidance into JSONL output."""
    with output_path.open("w", encoding="utf-8") as f:
        for cleaned_text, guidance in text_guidance_pairs:
            result = distill_text(cleaned_text, guidance)
            f.write(json.dumps(result) + "\n")
