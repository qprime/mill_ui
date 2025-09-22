from __future__ import annotations

from flask import Flask

from ...adapters.api.ace_api import ace_api_bp
from .routes import ace_web_bp


def register(app: Flask) -> None:
    app.register_blueprint(ace_web_bp, url_prefix="/ace")
    app.register_blueprint(ace_api_bp, url_prefix="/ace")
