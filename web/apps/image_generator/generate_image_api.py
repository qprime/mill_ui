import os
import json
import base64
import requests

from flask import request, jsonify, send_file
from tempfile import NamedTemporaryFile

API_KEY = os.getenv("OPENAI_API_KEY")
API_URL = "https://api.openai.com/v1/images/generations"
HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}

def generate_image_api():
    # Accepts a POSTed JSON body matching your config.json
    config = request.get_json()
    if not config:
        return jsonify({'error': 'No config data received'}), 400

    prompt = config.get("prompt")
    model = config.get("model", "gpt-image-1")
    size = config.get("size", "1024x1024")
    n = 1

    if not prompt:
        # Try to assemble using subject/persona/style if present
        try:
            # Load persona and style libraries
            persona_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../personas/cam_image_experts/ai_core.personas.json"))
            style_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../personas/cam_image_experts/styles.json"))
            with open(persona_path) as pf:
                PERSONAS = {p["name"]: p for p in json.load(pf)["personas"]}
            with open(style_path) as sf:
                STYLES = {s["name"]: s for s in json.load(sf)["styles"]}
            subject = config["subject"]
            persona = config["persona"]
            style = config["style"]
            persona_data = ai_core.personas.get(persona)
            style_data = STYLES.get(style)
            prompt = (
                f"{subject}, in the style of {persona_data['genre']}. "
                f"{persona_data['prompting_style']}. "
                f"{style_data['machinability_prompt']}"
            )
        except Exception as e:
            return jsonify({"error": f"Prompt assembly failed: {e}"}), 400

    # --- Make OpenAI Image Generation Request ---
    payload = {
        "model": model,
        "prompt": prompt,
        "size": size,
        "n": n
    }
    resp = requests.post(API_URL, headers=HEADERS, json=payload)
    if resp.status_code != 200:
        try:
            return jsonify({"error": resp.json()}), 500
        except Exception:
            return jsonify({"error": resp.text}), 500

    try:
        b64_data = resp.json()["data"][0]["b64_json"]
    except Exception:
        return jsonify({"error": "API response missing image data", "response": resp.json()}), 500

    # Option 1: Return image as base64 string (for quick frontend preview)
    # return jsonify({"image_b64": b64_data})

    # Option 2: Return as downloadable PNG file
    image_data = base64.b64decode(b64_data)
    with NamedTemporaryFile(delete=False, suffix=".png") as temp_img:
        temp_img.write(image_data)
        temp_img.flush()
        temp_img_name = temp_img.name

    # Clean up the temp file after sending
    response = send_file(temp_img_name, mimetype='image/png')
    response.call_on_close(lambda: os.unlink(temp_img_name))
    return response

# In app.py, register this:
# from generate_image_api import generate_image_api
# app.add_url_rule('/generate_image', view_func=generate_image_api, methods=['POST'])