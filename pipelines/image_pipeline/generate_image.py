"""
[CLIFF AI: Image Generation Pipeline]

This script generates an image using OpenAI's gpt-image-1, based on a project config.
- Input:  <project_folder>
    Looks for: cliff_ai/memory/cam_projects/<project_folder>/input/image.json
- Output:
    Overwrites: cliff_ai/memory/cam_projects/<project_folder>/input/image.png
- The JSON input must contain valid persona/style names and subject.
- This script is safe for CLI, automation, and webapp calls.

No reliance on config filename. No folder name mutation.
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

def generate_dalle_image(project_folder: str):
    # Absolute path to input/output folder
    base_dir = Path("memory/cam_projects") / project_folder / "input"
    json_path = base_dir / "image.json"
    png_path = base_dir / "image.png"

    print(f"DEBUG: project_folder='{project_folder}'")
    print(f"DEBUG: json_path='{json_path}' (exists: {json_path.exists()})")

    print(f"DEBUG: Absolute json_path: {json_path.resolve()}")
    print(f"DEBUG: Exists? {json_path.exists()}")

    if not json_path.exists():
        print(f"[!] Input not found: {json_path}")
        return

    with open(json_path, "r", encoding="utf-8") as f:
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
    with open(png_path, "wb") as f:
        f.write(image_data)
    print(f"[✓] Image written to: {png_path}")

    # (Optional) Overwrite config with full prompt, if you want:
    # with open(json_path, "w", encoding="utf-8") as f:
    #     json.dump(config, f, indent=2)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python generate_image.py <project_folder>")
    else:
        generate_dalle_image(sys.argv[1])
