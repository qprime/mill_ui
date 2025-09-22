# path: web/cliff_server/blueprints/chat.py
# type: chat_blueprint
# tags: blueprint, chat, flask, web_service
# owner: cliff
# depends_on: web/cliff_server/services/chat_service.py
# description: Manages chat routes and interactions for the Flask web service.

import uuid
import traceback
import logging
from urllib.parse import quote_plus
from flask import Blueprint, request, jsonify
from ..services.chat_service import (
    generate_chat_reply,
    update_chat_summary,
    update_chat_facts,
    get_sidecar_data,
    get_available_personas,
    get_chat_persona,
    set_chat_persona,
)
from ..services.promotion_service import promote

chat_bp = Blueprint("chat", __name__)

from flask import render_template


@chat_bp.route("/chat")
def chat():
    personas = get_available_personas()
    chat_id = request.args.get("chat_id") or str(uuid.uuid4())
    seed = request.args.get("seed", "")
    requested_persona = request.args.get("persona") or None
    default_persona = personas[0] if personas else "cliff_core"
    if requested_persona and requested_persona in personas:
        default_persona = requested_persona
    return render_template(
        "chat.html",
        chat_id=chat_id,
        personas=personas,
        default_persona=default_persona,
        seed=seed,
    )


@chat_bp.route("/ask", methods=["POST"])
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


@chat_bp.route("/persona", methods=["POST"])
def set_persona():
    try:
        data = request.get_json(force=True)
        chat_id = data.get("chat_id")
        persona = data.get("persona")
        if not chat_id:
            return jsonify({"error": "chat_id is required"}), 400
        updated = set_chat_persona(chat_id, persona)
        return jsonify({"persona": updated})
    except Exception as exc:
        logging.exception("Failed to set persona")
        return jsonify({"error": str(exc)}), 400


@chat_bp.route("/persona/<chat_id>", methods=["GET"])
def get_persona(chat_id):
    persona = get_chat_persona(chat_id)
    return jsonify({"persona": persona})


@chat_bp.route("/promote", methods=["POST"])
def promote_chat():
    try:
        data = request.get_json(force=True)
        chat_id = data.get("chat_id")
        if not chat_id:
            return jsonify({"error": "chat_id is required"}), 400
        action = data.get("action")
        if not action:
            return jsonify({"error": "action is required"}), 400
        persona = data.get("persona") or get_chat_persona(chat_id)
        scope = data.get("scope", "turn")
        limit = data.get("limit")
        turn_ids = data.get("turn_ids")
        turn_id = data.get("turn_id")
        fallback_turn = data.get("turn_fallback")
        fallback_turns = data.get("turn_fallbacks")
        result = promote(
            action=action,
            chat_id=chat_id,
            persona=persona,
            scope=scope,
            turn_ids=turn_ids or ([turn_id] if turn_id else None),
            fallback_turn=fallback_turn,
            fallback_turns=fallback_turns,
            limit=limit,
        )
        if result.get("kind") == "chat" and "new_chat_id" in result:
            seed_value = result.get("seed", "")
            persona_out = result.get("persona") or persona
            new_chat_id = result["new_chat_id"]
            result["new_chat_url"] = (
                f"/chat?chat_id={quote_plus(new_chat_id)}"
                f"&seed={quote_plus(seed_value)}"
                f"&persona={quote_plus(persona_out)}"
            )
        return jsonify(result)
    except Exception as exc:
        logging.exception("Promotion failed")
        return jsonify({"error": str(exc)}), 400


@chat_bp.route("/summary", methods=["POST"])
def set_summary():
    """
    Endpoint to update chat summary.
    Expects JSON: { chat_id, summary }
    """
    try:
        data = request.get_json(force=True)
        update_chat_summary(data["chat_id"], data["summary"])
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@chat_bp.route("/facts", methods=["POST"])
def set_facts():
    """
    Endpoint to update chat facts.
    Expects JSON: { chat_id, facts }
    """
    try:
        data = request.get_json(force=True)
        update_chat_facts(data["chat_id"], data["facts"])
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@chat_bp.route("/sidecar/<chat_id>", methods=["GET"])
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
