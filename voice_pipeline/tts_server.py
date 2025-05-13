from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
from TTS.api import TTS
import tempfile
import os

app = Flask(__name__)
CORS(app)

tts = TTS(model_name="tts_models/en/ljspeech/vits", progress_bar=False, gpu=True)


@app.route("/speak", methods=["POST"])
def speak():
    data = request.get_json()
    if not data or "text" not in data:
        return jsonify({"error": "Missing 'text' field"}), 400

    text = data["text"]
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_wav:
        output_path = tmp_wav.name
    tts.tts_to_file(text=text, file_path=output_path)
    return send_file(output_path, mimetype="audio/wav", as_attachment=True, download_name="output.wav")

@app.route("/")
def health():
    return jsonify({"status": "Cliff TTS Server running"}), 200

if __name__ == "__main__":
    context = ("/home/squinlan/cliff_ai/voice_pipeline/certs/cert.pem",
           "/home/squinlan/cliff_ai/voice_pipeline/certs/key.pem")

    app.run(host="0.0.0.0", port=5042, ssl_context=context)
