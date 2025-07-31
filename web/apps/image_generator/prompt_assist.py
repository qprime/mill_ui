"""Image Prompt Assist API

Provides a Flask endpoint to generate CNC-friendly grayscale image prompts
using LLM persona and style configuration. All LLM calls route through client.py.
"""

import os
import json
from flask import Flask, request, jsonify
from ai_core.client import get_chat_completion  # <--- changed

app = Flask(__name__)

CLIFF_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
PERSONAS_PATH = os.path.join(CLIFF_ROOT, "personas", "cam_image_experts", "ai_core.personas.json")
STYLES_PATH = os.path.join(CLIFF_ROOT, "personas", "cam_image_experts", "styles.json")

with open(PERSONAS_PATH, 'r', encoding='utf-8') as f:
    personas_data = json.load(f)
    PERSONAS = {p['name']: p for p in personas_data['personas']}
with open(STYLES_PATH, 'r', encoding='utf-8') as f:
    styles_data = json.load(f)
    STYLES = {s['name']: s for s in styles_data['styles']}

@app.route('/assist_prompt', methods=['POST'])
def assist_prompt():
    data = request.get_json()
    subject = data.get('subject')
    persona = data.get('persona')
    style = data.get('style')

    persona_data = ai_core.personas.get(persona, {})
    style_data = STYLES.get(style, {})

    persona_desc = persona_data.get('description', '')
    persona_genre = persona_data.get('genre', '')
    style_desc = style_data.get('description', '')
    machinability = style_data.get('machinability_prompt', '')

    system_prompt = (
        f"You are {persona}, a world-class expert in {persona_genre}. "
        f"Your specialty is: {persona_desc}\n"
        f"Given the subject: '{subject}' and the CNC carving style: '{style}', ({style_desc})\n"
        f"with these machining requirements: {machinability}\n"
        "Craft a single, CNC-friendly grayscale image prompt, suitable for DALL·E, using your full artistic and technical judgment. "
        "Be explicit about subject, silhouette, background, depth, and relief features. Output ONLY the prompt—no preamble, no explanation."
    )

    prompt = get_chat_completion(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "Generate the image prompt now."}
        ],
        model="gpt-4.1-mini",
        max_tokens=250,
        temperature=0.6,
        n=1,
    ).strip()

    return jsonify({"prompt": prompt})
