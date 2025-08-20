from __future__ import annotations
from flask import Flask
from .app_registry import register_all_apps

def create_app() -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")
    register_all_apps(app)
    return app

if __name__ == "__main__":
    app = create_app()
    app.run(
        host="0.0.0.0",
        port=8080,
        ssl_context=(
            "web/cliff_server/cert/web_server.crt",
            "web/cliff_server/cert/web_server.key",
        ),
        debug=False,
    )