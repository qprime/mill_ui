from __future__ import annotations

from flask import Flask

from ...adapters.api.system_api import system_api_bp


def register(app: Flask) -> None:
    app.register_blueprint(system_api_bp, url_prefix="/api/system")
