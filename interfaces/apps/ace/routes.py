from __future__ import annotations

from flask import Blueprint, render_template

ace_web_bp = Blueprint("ace_web", __name__)


@ace_web_bp.get("/")
@ace_web_bp.get("/app")
@ace_web_bp.get("/ui")
def ace_home():
    return render_template("ace/index.html")
