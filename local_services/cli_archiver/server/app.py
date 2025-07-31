"""
Flask API for receiving and storing CLI logs, and pushing commands to memory.
"""

from pathlib import Path
from flask import Flask, request, jsonify
from .cli_log_store import save_cli_logs   # <-- relative import (if in the same package/folder)
from flask_cors import CORS
import os
import json

from scripts.memory.memory_manager import add_to_domain  # <-- absolute package import

app = Flask(__name__)
CORS(app)

SAVE_PATH = "/home/squinlan/cliff_ai/memory/cliff_state/cli_logs.jsonl"

def save_cli_logs(logs):
    os.makedirs(os.path.dirname(SAVE_PATH), exist_ok=True)
    with open(SAVE_PATH, "a") as f:
        for log in logs:
            f.write(json.dumps(log) + "\n")

@app.route("/cli-logs", methods=["POST"])
def receive_cli_logs():
    incoming_logs = request.json.get("logs", [])
    for log in incoming_logs:
        save_cli_logs([log])
        command_text = log.get("command", "").strip()
        hostname = log.get("hostname", "unknown")
        MEMORY_JUNK_COMMANDS = ["ls", "pwd", "cd", "clear", "reset", "exit", "stty", "resize"]
        print(f"[CLI Logger Server] Received command: {command_text}")
        if not any(command_text.startswith(junk) for junk in MEMORY_JUNK_COMMANDS):
            try:
                print(f"[CLI Logger Server] Pushing to memory: {command_text}")
                add_to_domain(
                    domain="production",
                    text=f"CLI Command from {hostname}: {command_text}",
                    source="cli_logger",
                    tags=["cli_command"]
                )
                print(f"[CLI Logger Server] Successfully added to memory: {command_text}")
            except Exception as e:
                print(f"[CLI Logger Server] ERROR adding to memory: {e}")
        else:
            print(f"[CLI Logger Server] Skipped junk command for memory: {command_text}")
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050)
