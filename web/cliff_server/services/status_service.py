# path: web/cliff_server/services/status_service.py
# type: status_utility
# tags: service, status, web, flask
# owner: cliff
# depends_on: platform, flask
# description: Provides service status details for the CLIFF server's web interface.

import platform
from flask import request


def get_cliff_status():
    return {
        "model": "gpt-5",
        "context_window_tokens": 128000,
        "voice_enabled": True,
        "whisper_endpoint": "https://192.168.0.179:8001/transcribe",
        "tts_enabled": True,
        "active_modules": [
            "code_chunking",
            "cli_logger",
            "task_manager",
            "memory_graph",
            "voice_pipeline",
        ],
        "ui_mode": "web",
        "request_ip": request.remote_addr,
        "host": platform.node(),
    }
