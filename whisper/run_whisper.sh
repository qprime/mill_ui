#!/bin/bash
cd "$(dirname "$0")"
uv run "uvicorn whisper_server:app --host 0.0.0.0 --port 8001 --ssl-keyfile=cert/whisper.key --ssl-certfile=cert/whisper.crt"
