from __future__ import annotations
from flask import Blueprint, request, jsonify
from ...services.tasks import tasks_api

tasks_api_bp = Blueprint("tasks_api_bp", __name__)

@tasks_api_bp.post("/call")
def call():
    j = request.get_json(silent=True) or {}
    return jsonify(tasks_api(j))
