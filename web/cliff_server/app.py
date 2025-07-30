"""CLIFF Web Main App: Blueprint registration and launch."""

from flask import Flask
from blueprints.chat import chat_bp
from blueprints.tasks import tasks_bp
from blueprints.dashboard import dashboard_bp

def create_app():
    app = Flask(__name__, template_folder='templates', static_folder='static')
    app.register_blueprint(chat_bp)
    app.register_blueprint(tasks_bp)
    app.register_blueprint(dashboard_bp)
    return app

if __name__ == "__main__":
    app = create_app()
    app.run(
        host="0.0.0.0",
        port=8080,
        ssl_context=("cert/web_server.crt", "cert/web_server.key"),
        debug=False  # Can toggle via ENV if desired
    )
