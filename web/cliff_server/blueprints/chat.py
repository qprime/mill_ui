# chat.py
#
# Flask blueprint for chat endpoints in CLIFF AI web server.
# Handles chat message API, summary/fact updates, and sidecar metadata retrieval.
# Calls into chat_service for all LLM/distillation/memory logic.
import uuid
import traceback
from flask import Blueprint, request, jsonify
from ..services.chat_service import (
    generate_chat_reply,
    update_chat_summary,
    update_chat_facts,
    get_sidecar_data,
)

chat_bp = Blueprint('chat', __name__)

from flask import render_template

@chat_bp.route("/chat")
def chat():
    chat_id = str(uuid.uuid4())
    return render_template("chat.html", chat_id=chat_id)



@chat_bp.route('/ask', methods=['POST'])
def ask_llm():
    """
    Main chat endpoint.
    Expects JSON: { persona, input, chat_id }
    Returns: full chat LLM result as JSON.
    """
    try:
        data = request.get_json(force=True)
        result = generate_chat_reply(data)
        return jsonify(result)
    except Exception as e:
        print("Error in /ask route:", str(e))
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@chat_bp.route('/summary', methods=['POST'])
def set_summary():
    """
    Endpoint to update chat summary.
    Expects JSON: { chat_id, summary }
    """
    try:
        data = request.get_json(force=True)
        update_chat_summary(data['chat_id'], data['summary'])
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@chat_bp.route('/facts', methods=['POST'])
def set_facts():
    """
    Endpoint to update chat facts.
    Expects JSON: { chat_id, facts }
    """
    try:
        data = request.get_json(force=True)
        update_chat_facts(data['chat_id'], data['facts'])
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@chat_bp.route('/sidecar/<chat_id>', methods=['GET'])
def get_sidecar(chat_id):
    """
    Endpoint to fetch chat sidecar metadata (summary, facts, etc).
    Returns JSON sidecar dict.
    """
    try:
        meta = get_sidecar_data(chat_id)
        return jsonify(meta)
    except Exception as e:
        return jsonify({"error": str(e)}), 404
