import os
import openai
from flask import Flask, request, jsonify
import json

app = Flask(__name__)

CLIFF_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
PERSONAS_PATH = os.path.join(CLIFF_ROOT, "personas", "cam_image_experts", "personas.json")
STYLES_PATH = os.path.join(CLIFF_ROOT, "personas", "cam_image_experts", "styles.json")

with open(PERSONAS_PATH, 'r') as f:
    personas_data = json.load(f)
    PERSONAS = {p['name']: p for p in personas_data['personas']}
with open(STYLES_PATH, 'r') as f:
    styles_data = json.load(f)
    STYLES = {s['name']: s for s in styles_data['styles']}

client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

@app.route('/assist_prompt', methods=['POST'])
def assist_prompt():
    data = request.get_json()
    subject = data.get('subject')
    persona = data.get('persona')
    style = data.get('style')

    persona_data = PERSONAS.get(persona, {})
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

    chat_response = client.chat.completions.create(
        model="gpt-4.1-mini",  # Or "gpt-4.1-mini"
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "Generate the image prompt now."}
        ],
        max_tokens=250,
        temperature=0.6,
        n=1,
    )
    new_prompt = chat_response.choices[0].message.content.strip()
    return jsonify({"prompt": new_prompt})

if __name__ == '__main__':
    app.run(debug=True, port=5001)
