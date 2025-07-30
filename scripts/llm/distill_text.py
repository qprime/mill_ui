"""
Distill text using OpenAI GPT-4.1-mini.
Replaces local LLAMA-CPT distillation with OpenAI's API.
"""

import os
import json
from pathlib import Path
from typing import Optional
from cliff_ai.scripts.llm.client import get_chat_completion

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DISTILLER_MODEL = "gpt-4.1-mini"
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
    if strict_mode:
        user_input = f"BEGIN_INPUT\n{cleaned_text}\nEND_INPUT"
    else:
        user_input = cleaned_text
    system_prompt = (
        """
You are a distillation engine for technical chat logs. 
Extract only facts, technical actions, or content that must persist in the session.
Never include requests for brevity, meta-instructions, or conversational intent.
If the input is only meta-chatter, greetings, or instructions to the assistant, return an empty string.
If in doubt, prefer less over more.
Return only the distilled factual content, as a fragment or phrase if possible.
For each turn, you are only to return a distilled summary.  Nothing else.  Your job is distillation, not responses.
"""
    )
    try:
        distilled = get_chat_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input}
            ],
            model=DISTILLER_MODEL,
            temperature=0.5 if strict_mode else 0.2,
            max_tokens=400
        ).strip()
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
