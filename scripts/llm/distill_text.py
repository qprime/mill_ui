"""
Distill text using OpenAI GPT-4.1-mini.
Replaces local LLAMA-CPT distillation with OpenAI's API.
"""

import os
import json
import re
from pathlib import Path
from typing import Optional

from scripts.llm.client import get_chat_completion

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DISTILLER_MODEL = "gpt-4.1-mini"
DEFAULT_GUIDANCE = {
    "persona": "developer",
    "task_type": "general",
    "tone": "neutral",
    "urgency": "normal"
}

SYSTEM_PROMPT = """
You are a technical distillation engine.

Your ONLY job is to extract technical facts, actions, or key content *already present* in the input.

Output ONLY the extracted content between these markers:

<<<DISTILL_START
... distilled content here ...
DISTILL_END>>>

Do NOT generate summaries, answers, or any content outside these markers.

- If the input is a user question or command (e.g. 'List all folders'), output an EMPTY block between the markers.
- If the input is only meta-chatter, greetings, or instructions to the assistant, also output an EMPTY block.

Examples:

Input: 'I finished refactoring the code and committed to main.'
Output:
<<<DISTILL_START
Refactored code committed to main.
DISTILL_END>>>

Input: 'List all folders.'
Output:
<<<DISTILL_START
DISTILL_END>>>
"""

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

def extract_distilled_block(text: str) -> Optional[str]:
    """
    Extracts content between <<<DISTILL_START ... DISTILL_END>>>.
    Returns None if empty or if 'NA', 'N/A', etc. is detected.
    """
    m = re.search(r'<<<DISTILL_START\n?(.*?)\n?DISTILL_END>>>', text, re.DOTALL | re.IGNORECASE)
    if m:
        result = m.group(1).strip()
        if not result or result.lower() in {"na", "n/a", "na.", "n.a.", "none", "not applicable"}:
            return None
        return result
    return None

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
    try:
        distilled = get_chat_completion(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_input}
            ],
            model=DISTILLER_MODEL,
            temperature=0.5 if strict_mode else 0.2,
            max_tokens=400
        ).strip()
        if strict_mode and "`" in distilled and "`" not in cleaned_text:
            warnings.append("Distilled text contains code-like output not present in input. Possible hallucination.")
        distilled_block = extract_distilled_block(distilled)
        if distilled_block is None:
            distilled_block = cleaned_text
    except Exception as e:
        distilled_block = cleaned_text
        warnings.append(f"LLM request failed: {str(e)}. Outputting cleaned text only.")
    return {
        "distilled_text": distilled_block,
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
