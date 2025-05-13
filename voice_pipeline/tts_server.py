from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
from TTS.api import TTS as TTS_API
import tempfile
import os

import torch
import TTS.tts.configs.xtts_config
import TTS.tts.models.xtts
import TTS.config.shared_configs

torch.serialization.add_safe_globals([
    TTS.tts.configs.xtts_config.XttsConfig,
    TTS.tts.models.xtts.XttsAudioConfig,
    TTS.config.shared_configs.BaseDatasetConfig,
    TTS.tts.models.xtts.XttsArgs  # ← this is the last one needed
])




app = Flask(__name__)
CORS(app)

# Load XTTS model (multi-speaker, multilingual)
tts = TTS_API(
    model_name="tts_models/multilingual/multi-dataset/xtts_v2",
    progress_bar=False,
    gpu=True
)


@app.route("/speak", methods=["POST"])
def speak():
    data = request.get_json()
    if not data or "text" not in data:
        return jsonify({"error": "Missing 'text' field"}), 400

    text = data["text"].strip()
    if not text.endswith(('.', '!', '?')):
        text += '.'

    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_wav:
        output_path = tmp_wav.name

    # Run XTTS with tuning params
    tts.tts_to_file(
        text=text,
        file_path=output_path,
        speaker_wav="/home/squinlan/Downloads/speaker_sample.wav",
        language="en"
    )



    return send_file(output_path, mimetype="audio/wav", as_attachment=True, download_name="output.wav")

@app.route("/")
def health():
    return jsonify({"status": "Cliff XTTS Server running"}), 200

if __name__ == "__main__":
    context = (
        "/home/squinlan/cliff_ai/voice_pipeline/certs/cert.pem",
        "/home/squinlan/cliff_ai/voice_pipeline/certs/key.pem"
    )
    app.run(host="0.0.0.0", port=5042, ssl_context=context)
