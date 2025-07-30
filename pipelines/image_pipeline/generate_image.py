"""
Generates images using OpenAI's DALL·E model from configuration files.
"""

import os
import sys
import json
import base64
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("OPENAI_API_KEY")
API_URL = "https://api.openai.com/v1/images/generations"
HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}

with open("../personas/cam_image_experts/personas.json") as f:
    PERSONAS = {p["name"]: p for p in json.load(f)["personas"]}

with open("../personas/cam_image_experts/styles.json") as f:
    STYLES = {s["name"]: s for s in json.load(f)["styles"]}

def assemble_prompt(subject: str, persona_name: str, style_name: str) -> str:
    persona = PERSONAS.get(persona_name)
    style = STYLES.get(style_name)

    if not persona or not style:
        raise ValueError(f"Invalid persona or style: {persona_name}, {style_name}")

    return (
        f"{subject}, in the style of {persona['genre']}. "
        f"{persona['prompting_style']}. "
        f"{style['machinability_prompt']}"
    )

def generate_dalle_image(config_name: str):
    config_path = Path("./") / f"{config_name}.json"
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

    response = requests.post(API_URL, headers=HEADERS, json={
        "model": "gpt-image-1",
        "prompt": prompt,
        "size": size,
        "n": 1
    })

    if response.status_code != 200:
        try:
            print(f"[!] API error {response.status_code}:\n{response.json()}")
        except Exception:
            print(f"[!] API error {response.status_code} (non-JSON response):\n{response.text}")
        return

    try:
        b64_data = response.json()["data"][0]["b64_json"]
    except KeyError:
        print("[!] Unexpected API response format.")
        print(response.json())
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
        print("Usage: python generate_dalle_image.py <config_name>")
    else:
        generate_dalle_image(sys.argv[1])