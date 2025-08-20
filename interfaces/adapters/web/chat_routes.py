from __future__ import annotations
from flask import Blueprint, render_template, request
from markupsafe import escape, Markup
from ...services.chat import chat_reply

chat_web_bp = Blueprint("chat_web_bp", __name__, template_folder="../../templates")

@chat_web_bp.get("/chat")
def chat_page():
    return render_template("chat/index.html")

@chat_web_bp.post("/ask")
def ask_fragment():
    j = request.get_json(silent=True) or {}
    text = request.form.get("message") or request.form.get("input") or j.get("input") or j.get("message") or ""
    data = {"chat_id": request.form.get("chat_id") or j.get("chat_id", ""), "input": text}
    result = chat_reply(data)
    content = escape(str(result.get("response", "")))
    return Markup(f'<div class="assistant-response"><pre style="white-space:pre-wrap">{content}</pre></div>')
