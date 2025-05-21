#!/bin/bash
set -e

LLAMA_BIN="/home/squinlan/cliff_ai/models/phi2/llama.cpp/build/bin/llama-server"
MODEL_PATH="/home/squinlan/cliff_ai/models/phi3.5-mini/phi-3.5.Q4_K_M.gguf"
CERT="/home/squinlan/cliff_ai/whisper/cert/whisper.crt"
KEY="/home/squinlan/cliff_ai/whisper/cert/whisper.key"

exec "$LLAMA_BIN" \
  --model "$MODEL_PATH" \
  --host 0.0.0.0 \
  --port 5050 \
  --ctx-size 4096 \
  --n-gpu-layers 33 \
  --threads 8 \
  --log-disable
