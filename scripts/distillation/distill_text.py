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

def is_fact_query(text: str) -> bool:
    return text.strip().lower().startswith(("what", "when", "where", "who", "how many", "how much"))


def fill_guidance_defaults(guidance: dict) -> tuple[dict, list[str]]:
    warnings = []
    final = guidance.copy()
    for key, value in DEFAULT_GUIDANCE.items():
        if key not in final:
            final[key] = value
            warnings.append(f"guidance parameter '{key}' missing, using default '{value}'")
    return final, warnings

def distill_text(cleaned_text: str, guidance: dict, strict_mode: bool = False) -> dict:
    guidance_filled, warnings = fill_guidance_defaults(guidance)

    if is_fact_query(cleaned_text):
        return {
            "distilled_text": cleaned_text,
            "metadata": {**guidance_filled, "bypassed": True},
            "original_input": {
                "cleaned_text": cleaned_text,
                "guidance": guidance
            }
        }


    
    # Wrap input in explicit guard delimiters for strict mode
    if strict_mode:
        user_input = f"BEGIN_INPUT\n{cleaned_text}\nEND_INPUT"
    else:
        user_input = cleaned_text

    # Construct system prompt
    system_prompt = (
        "You are an English language expert with a specialty in summarizing and distilling text to its most succinct, meaningful form. "
        "Your role is to extract only what is necessary to preserve the speaker's intent, actions, and key thoughts.\n"
        "Do not infer or fabricate any content not directly stated by the speaker.\n"
        "Preserve any expressed uncertainty, questions, or feedback-seeking behavior in a concise and meaningful way.\n"
        "Avoid including examples, answers, or suggestions that were not present in the input.\n"
        "Only summarize what appears between BEGIN_INPUT and END_INPUT, if those markers are present.\n"
        f"- persona: {guidance_filled['persona']}\n"
        f"- task_type: {guidance_filled['task_type']}\n"
        f"- tone: {guidance_filled['tone']}\n"
        f"- urgency: {guidance_filled['urgency']}\n\n"
        "Return only the final distilled output."
    )

    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input}
        ],
        "temperature": 0.5 if strict_mode else 0.2
    }

    try:
        response = requests.post(LLAMA_SERVER_URL, json=payload, timeout=15)
        response.raise_for_status()
        distilled = response.json()["choices"][0]["message"]["content"].strip()

        # Post-check for hallucinated content
        if strict_mode and "`" in distilled and "`" not in cleaned_text:
            warnings.append("Distilled text contains code-like output not present in input. Possible hallucination.")

    except Exception as e:
        distilled = cleaned_text
        warnings.append(f"LLM request failed: {str(e)}. Outputting cleaned text only.")

    return {
        "distilled_text": distilled,
        "metadata": {
            **guidance_filled,
            "strict_mode": strict_mode,
            "warnings": warnings
        },
        "original_input": {
            "cleaned_text": cleaned_text,
            "guidance": guidance
        }
    }

def batch_distill(
    text_guidance_pairs: list[tuple[str, dict]],
    output_path: Path,
    strict_mode: bool = False
) -> None:
    with output_path.open("w", encoding="utf-8") as f:
        for cleaned_text, guidance in text_guidance_pairs:
            result = distill_text(cleaned_text, guidance, strict_mode=strict_mode)
            f.write(json.dumps(result) + "\n")