"""Chat blueprint: /chat, /ask, summary, facts, and sidecar endpoints."""

from flask import Blueprint, request, jsonify, render_template
from services.chat_service import (
    generate_chat_reply,
    update_chat_summary,
    update_chat_facts,
    get_sidecar_data,
)
import uuid

chat_bp = Blueprint("chat", __name__)

@chat_bp.route("/chat")
def chat_page():
    chat_id = str(uuid.uuid4())
    return render_template("chat.html", chat_id=chat_id)

@chat_bp.route("/ask", methods=["POST"])
def ask_llm():
    data = request.get_json()
    result = generate_chat_reply(data)
    return jsonify(result)

@chat_bp.route("/chat/<chat_id>/update_summary", methods=["POST"])
def update_summary(chat_id):
    summary = request.form.get("summary", "")
    update_chat_summary(chat_id, summary)
    return jsonify({"status": "ok"})

@chat_bp.route("/chat/<chat_id>/update_facts", methods=["POST"])
def update_facts(chat_id):
    facts_json = request.form.get("facts", "{}")
    update_chat_facts(chat_id, facts_json)
    return jsonify({"status": "ok"})

@chat_bp.route("/chat/<chat_id>/sidecar", methods=["GET"])
def sidecar(chat_id):
    data = get_sidecar_data(chat_id)
    return jsonify(data)