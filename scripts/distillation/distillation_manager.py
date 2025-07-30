"""
distillation_manager.py

Central engine for distillation: routes LLM calls using persona definitions
from the canonical personas_manager. Only one API to maintain.

"""

import os
from typing import Any, Dict
from scripts.llm.personas_manager import get_persona

# --- Model clients ---
try:
    import openai
    _openai_client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
except ImportError:
    _openai_client = None

def distill(input_text: str, persona_name: str = "chat", model: str = None, strict_mode: bool = None) -> str:
    persona = get_persona(persona_name)
    # For JSON personas, prefer 'system_prompt'; for legacy, use 'prompt'
    system_prompt = persona.get("system_prompt", persona.get("prompt", ""))
    use_model = model or persona.get("default_model", "gpt-4.1-mini")
    use_strict = strict_mode if strict_mode is not None else persona.get("strict_mode", True)

    if use_model.startswith("gpt-") or use_model.startswith("openai"):
        if not _openai_client:
            raise RuntimeError("OpenAI client not available.")
        completion = _openai_client.chat.completions.create(
            model=use_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": input_text}
            ],
            temperature=0.0 if use_strict else 0.2,
            max_tokens=512,
        )
        content = completion.choices[0].message.content.strip()
        return content
    else:
        raise NotImplementedError(f"Model routing for {use_model} not implemented.")

# --- CLI Test Entry Point ---
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Run distillation using a persona.")
    parser.add_argument("input_file", help="Text file to distill.")
    parser.add_argument("--persona", default="chat", help="Persona to use.")
    args = parser.parse_args()

    with open(args.input_file, "r", encoding="utf-8") as f:
        input_text = f.read()

    print(f"[distillation_manager] Using persona: {args.persona}")
    output = distill(input_text, persona_name=args.persona)
    print("\n[Distilled Output]:\n")
    print(output)
