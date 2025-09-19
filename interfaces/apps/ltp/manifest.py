from __future__ import annotations
from flask import Flask
from ...adapters.api.ltp_api import ltp_api_bp
from ...adapters.web.ltp_routes import ltp_web_bp

def register(app: Flask) -> None:
    app.register_blueprint(ltp_api_bp, url_prefix="/api/ltp")
    app.register_blueprint(ltp_web_bp, url_prefix="/ltp")
