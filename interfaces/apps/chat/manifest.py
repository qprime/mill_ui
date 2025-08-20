from __future__ import annotations
from flask import Flask
from ...adapters.api.chat_api import chat_api_bp
from ...adapters.web.chat_routes import chat_web_bp

def register(app: Flask) -> None:
    app.register_blueprint(chat_api_bp, url_prefix="/api/chat")
    app.register_blueprint(chat_web_bp)
