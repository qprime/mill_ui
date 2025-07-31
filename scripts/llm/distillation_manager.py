"""distillation_manager.py

Central engine for distillation: routes LLM calls using persona definitions
from the canonical personas_manager. Only one API to maintain.
"""

import os
from typing import Any, Dict
from cliff_ai.personas.personas_manager import get_persona
from cliff_ai.scripts.llm.client import get_chat_completion

def distill(input_text: str, persona_name: str = "chat", model: str = None, strict_mode: bool = None) -> str:
    persona = get_persona(persona_name)
    # Prefer 'system_prompt' from JSON; fallback to 'prompt' for legacy personas
    system_prompt = persona.get("system_prompt", persona.get("prompt", ""))
    use_model = model or persona.get("default_model", "gpt-4.1-mini")
    use_strict = strict_mode if strict_mode is not None else persona.get("strict_mode", True)

    if use_model.startswith("gpt-") or use_model.startswith("openai"):
        content = get_chat_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": input_text}
            ],
            model=use_model,
            temperature=0.0 if use_strict else 0.2,
            max_tokens=512,
        ).strip()
        return content
    else:
        raise NotImplementedError(f"Model routing for {use_model} not implemented.")
