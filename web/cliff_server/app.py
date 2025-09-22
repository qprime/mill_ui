# path: web/cliff_server/app.py
# type: web_application
# tags: flask, server, blueprints, chat, tasks, dashboard
# owner: cliff
# depends_on: .blueprints.chat, .blueprints.tasks, .blueprints.dashboard
# description: Initializes and runs the Flask server application with chat, tasks, and dashboard components.

from flask import Flask
from .services.ledger_service import get_ledger_status
from .blueprints.chat import chat_bp
from .blueprints.tasks import tasks_bp
from .blueprints.dashboard import dashboard_bp


def create_app():
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.register_blueprint(chat_bp)
    app.register_blueprint(tasks_bp)
    app.register_blueprint(dashboard_bp)

    @app.context_processor
    def inject_ledger_status():
        return {"ledger_status": get_ledger_status()}

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
