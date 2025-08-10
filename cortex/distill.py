# path: cortex/distill.py
# type: text_processing
# tags: distillation, persona, chat, regex
# owner: cliff
# depends_on: cortex/personas/personas_manager.py, cortex/client.py
# description: Extracts and distills text responses based on personas and chat completions.

import re
from cortex.personas.personas_manager import get_persona
from cortex.client import get_chat_completion


import re


def extract_distilled_block(text: str, pattern: str = None) -> str:
    if not pattern:
        raise ValueError("No extraction pattern provided to extract_distilled_block.")
    m = re.search(pattern, text, re.DOTALL)
    if not m:
        # CRASH LOUDLY so this gets logged and investigated
        raise ValueError(
            f"extract_distilled_block: Pattern not found!\n"
            f"Pattern: {pattern}\n"
            f"Text excerpt: {repr(text[:200])}..."
        )
    content = m.group(1).strip()
    if not content or content.lower() in {"na", "n/a", "none", "na.", "n.a."}:
        raise ValueError(
            f"extract_distilled_block: Extracted content is empty or a known placeholder.\n"
            f"Pattern: {pattern}\n"
            f"Text excerpt: {repr(text[:200])}..."
        )
    return content


def distill(input_text, persona):
    try:
        persona_data = get_persona(persona)
        model = persona_data["default_model"]
        strict = persona_data["strict_mode"]
        extract_pattern = persona_data.get("extract_pattern")
        # if extract_pattern:
        #     print("distill.distill.extract_pattern:" + extract_pattern)
        system_prompt = persona_data["system_prompt"]
        if not isinstance(system_prompt, str):
            if isinstance(system_prompt, list):
                system_prompt = "\n".join(str(x) for x in system_prompt)
            else:
                raise ValueError("system_prompt must be a string or list of strings.")

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": input_text},
        ]

        raw_resp = get_chat_completion(
            messages=messages,
            model=model,
            max_completion_tokens=512,
        )
        print("RAW MODEL RESPONSE:", repr(raw_resp))
        resp = raw_resp.strip()

        content = input_text
        if extract_pattern:
            extracted = extract_distilled_block(resp, extract_pattern)
            print("distill.distill.extracted: " + extracted)
            if extracted:
                content = extracted

        return {
            "distilled_text": content,
            "metadata": {
                "bypassed": content == input_text,
                "persona": persona,
                "extract_pattern": extract_pattern,
            },
        }
    except Exception as e:
        import traceback

        print("DISTILL EXCEPTION:", e)
        print(traceback.format_exc())
        # Re-raise to propagate, or comment this out for fallback:
        raise
        # If you really must return something for prod stability, keep below:
        # return {
        #     "distilled_text": input_text,
        #     "metadata": {
        #         "bypassed": True,
        #         "error": str(e),
        #         "persona": persona,
        #         "extract_pattern": None,
        #     }
        # }
