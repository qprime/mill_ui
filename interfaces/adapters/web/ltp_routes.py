from __future__ import annotations
from flask import Blueprint, render_template, request

ltp_web_bp = Blueprint("ltp_web_bp", __name__)

@ltp_web_bp.get("/")
def index():
    slug = request.args.get("slug", "")
    return render_template("ltp/index.html", slug=slug)
