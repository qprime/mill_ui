from __future__ import annotations
from flask import Flask
from ...adapters.api.tasks_api import tasks_api_bp
from ...adapters.web.tasks_routes import tasks_web_bp

def register(app: Flask) -> None:
    app.register_blueprint(tasks_api_bp, url_prefix="/api/tasks")
    app.register_blueprint(tasks_web_bp)
