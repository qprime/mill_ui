"""
[CLIFF AI: Image Generation Pipeline]

This module generates DALL·E/gpt-image-1 images from structured subject, persona, and style.
- Loads personas and styles via ai_core.personas.personas_manager and ai_core.personas.styles.
- All OpenAI API calls are routed through ai_core.client for maintainability.
- Designed for headless, programmatic use by CLIFF or pipeline agents.

This file is formatted for optimal AI context/RAG/maintenance.
"""

import sys
import json
import base64
from pathlib import Path

from ai_core.personas.personas_manager import get_persona
from ai_core.personas.styles import get_style
from ai_core.client import get_image_generation

def assemble_prompt(subject: str, persona_name: str, style_name: str) -> str:
    persona = get_persona(persona_name, category="cam/artists")
    style = get_style(style_name, category="cam/styles")
    if not persona or not style:
        raise ValueError(f"Invalid persona or style: {persona_name}, {style_name}")
    return (
        f"{subject}, in the style of {persona['genre']}. "
        f"{persona['prompting_style']}. "
        f"{style['machinability_prompt']}"
    )

def generate_dalle_image(config_name: str):
    config_path = Path(f"{config_name}.json")
    if not config_path.exists():
        print(f"[!] Config not found: {config_path}")
        return

    with open(config_path) as f:
        config = json.load(f)

    subject = config["subject"]
    persona = config["persona"]
    style = config["style"]
    size = config.get("size", "1024x1024")

    try:
        prompt = assemble_prompt(subject, persona, style)
    except ValueError as e:
        print(f"[!] {e}")
        return

    config["prompt"] = prompt
    print(f"[+] Requesting gpt-image-1 image for prompt: {prompt}")

    try:
        b64_images = get_image_generation(prompt, model="gpt-image-1", size=size, n=1)
        b64_data = b64_images[0]
    except Exception as e:
        print(f"[!] Image generation failed: {e}")
        return

    image_data = base64.b64decode(b64_data)
    out_dir = Path("output") / config_name
    out_dir.mkdir(parents=True, exist_ok=True)

    with open(out_dir / "image.png", "wb") as f:
        f.write(image_data)
    with open(out_dir / f"{config_name}.json", "w") as f:
        json.dump(config, f, indent=2)

    print(f"[✓] Image and config saved to: {out_dir}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python generate_image.py <config_name>")
    else:
        generate_dalle_image(sys.argv[1])
