from __future__ import annotations

from flask import Flask

from skills.living_truth_partner.ctx_api import ctx_api_bp, ctx_web_bp


def register(app: Flask) -> None:
    app.register_blueprint(ctx_api_bp, url_prefix="/ctx")
    app.register_blueprint(ctx_web_bp, url_prefix="/ctx")

