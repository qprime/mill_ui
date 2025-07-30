# scripts/llm/llm_tools.py

import os
import json
from typing import List, Dict, Any
import openai

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = openai.OpenAI(api_key=OPENAI_API_KEY)

def distill_sidecar_llm(entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Distill and curate sidecar session entries using GPT-4.1-mini (or any OpenAI model).
    Merges, deduplicates, and summarizes as necessary.
    Returns a clean list of structured entries (same schema as input).
    """
    if not entries:
        return []

    prompt = _make_sidecar_distillation_prompt(entries)

    try:
        response = client.chat.completions.create(
            model="gpt-4.1-mini",  # Use "gpt-4-1-mini" or any available mini/preview model
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a precise assistant that curates and summarizes chat session memory for continuity and relevance. "
                        "Given a list of sidecar memory entries (facts, summaries, goals, notes), distill them into a short, deduplicated, and up-to-date list. "
                        "Only include facts that are NOT already present in the latest code context. Keep the list concise. "
                        "Return only a JSON list of entries; do not include any explanation or commentary."
                    )
                },
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=800,
        )
        output = response.choices[0].message.content
        distilled_entries = _extract_json_from_output(output)
        if isinstance(distilled_entries, list):
            return distilled_entries
        else:
            print("[llm_tools] Warning: LLM did not return a valid list. Returning as-is.")
            return entries
    except Exception as e:
        print(f"[llm_tools] Exception in LLM distillation: {e}")
        return entries

def _make_sidecar_distillation_prompt(entries: List[Dict[str, Any]]) -> str:
    example = json.dumps(entries, indent=2)
    return (
        f"Here is a JSON list of session memory entries:\n{example}\n\n"
        "Curate, merge, and deduplicate them as necessary. Return the result as a JSON list in the same schema."
    )

def _extract_json_from_output(output: str) -> Any:
    """
    Attempt to extract a valid JSON array from the model's output.
    """
    try:
        return json.loads(output)
    except json.JSONDecodeError:
        import re
        match = re.search(r"(\[\s*\{.*\}\s*\])", output, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except Exception:
                pass
        return output
