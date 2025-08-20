# path: interfaces/api/chat.py

from __future__ import annotations
from typing import Any, Dict
from flask import Blueprint, request, jsonify
from interfaces.services.chat import (
    generate_chat_reply,
    update_chat_summary,
    update_chat_facts,
    get_sidecar_data,
)

chat_api_bp = Blueprint("chat_api", __name__, url_prefix="/api/chat")

@chat_api_bp.post("/ask")
def ask() -> Any:
    data: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
    return jsonify(generate_chat_reply(data))

@chat_api_bp.post("/summary")
def summary() -> Any:
    data: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
    update_chat_summary(str(data.get("chat_id", "")), str(data.get("summary", "")))
    return jsonify({"ok": True})

@chat_api_bp.post("/facts")
def facts() -> Any:
    data: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
    update_chat_facts(str(data.get("chat_id", "")), data.get("facts"))
    return jsonify({"ok": True})

@chat_api_bp.get("/sidecar/<chat_id>")
def sidecar(chat_id: str) -> Any:
    return jsonify(get_sidecar_data(chat_id))
