📝 Final README.md Suggestion (Updated for Cleanup)
markdown
Copy
Edit
# Cliff AI - Whisper Transcription Server

This module runs a secure, local HTTP server to transcribe audio files using OpenAI's Whisper model. It's designed to integrate into the Cliff AI voice-command pipeline.

## Features

- Accepts audio via HTTPS POST
- Transcribes using Whisper (base or other models)
- Runs in Python virtual environment
- SSL enabled (self-signed certificates)
- Lightweight, standalone service

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install git+https://github.com/openai/whisper.git
pip install flask torchaudio
Running the Server
bash
Copy
Edit
./run_whisper.sh
Endpoint
Test with:

bash
Copy
Edit
curl -k https://localhost:5000/transcribe -F "file=@your_audio_file.m4a"
Directory Structure
plaintext
Copy
Edit
cliff_ai/whisper/
├── run_whisper.sh
├── whisper_server.py
├── venv/                   # Virtual environment (not committed)
├── __pycache__/            # Python cache (not committed)
└── cert/
    ├── whisper.crt
    ├── whisper.key
    └── conf/
        └── openssl-whisper-san.conf
SSL Notes
Use the provided OpenSSL config to regenerate certs if needed:

bash
Copy
Edit
openssl req -x509 -nodes -days 365 \
  -newkey rsa:2048 \
  -keyout cert/whisper.key \
  -out cert/whisper.crt \
  -config cert/conf/openssl-whisper-san.conf
