#!/bin/bash
cd ~/cliff_ai/whisper
source venv/bin/activate
uvicorn whisper_server:app --host 0.0.0.0 --port 8001 --ssl-keyfile cert/whisper.key --ssl-certfile cert/whisper.crt
