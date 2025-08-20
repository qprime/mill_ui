from __future__ import annotations
from flask import Blueprint, request, jsonify
from ...services.chat import chat_reply

chat_api_bp = Blueprint("chat_api_bp", __name__)

@chat_api_bp.post("/ask")
def ask():
    j = request.get_json(silent=True) or {}
    data = {
        "chat_id": j.get("chat_id", ""),
        "input": j.get("input") or j.get("message") or "",
    }
    return jsonify(chat_reply(data))
