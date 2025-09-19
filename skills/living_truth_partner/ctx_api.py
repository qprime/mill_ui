from __future__ import annotations

from flask import Blueprint, jsonify, render_template, request

from skills.memory_framework.actions import (
    apply_action,
    approve_action,
    build_capsule,
    create_action,
    get_action,
    run_action,
    auto_check,
)
from skills.memory_framework.models import Action
from skills.memory_framework.registry import MemoryRegistry
from skills.memory_framework.timeline import build_timeline

ctx_api_bp = Blueprint("ctx_api", __name__)
ctx_web_bp = Blueprint("ctx_web", __name__)


@ctx_web_bp.get("/")
def ctx_index():
    return render_template("ctx/index.html")



def _registry() -> MemoryRegistry:
    return MemoryRegistry()


def _action_payload(action: Action) -> dict:
    return action.to_dict()


@ctx_api_bp.post("/api/actions")
def api_create_action():
    payload = request.get_json(force=True, silent=True) or {}
    reg = _registry()
    memory = create_action(
        reg,
        title=payload.get("title", "Untitled"),
        intent=payload.get("intent", "doc.coauthor"),
        thread=payload.get("thread"),
        requirements=payload.get("requirements", []),
        constraints=payload.get("constraints"),
        context_scope=payload.get("context_scope"),
        executor=payload.get("executor"),
    )
    action = Action.from_memory(memory)
    auto_check(reg, action_id=action.id)
    latest = get_action(reg, action.id)
    return jsonify(_action_payload(latest)), 201


@ctx_api_bp.post("/api/actions/<action_id>/run")
def api_run_action(action_id: str):
    reg = _registry()
    action = get_action(reg, action_id)
    capsule_result = build_capsule(action, reg)
    updated_action, artifacts, result = run_action(reg, action_id=action_id, capsule=capsule_result.capsule)
    return jsonify(
        {
            "action": _action_payload(updated_action),
            "artifacts": [artifact.content.path for artifact in artifacts],
            "result": result,
        }
    )


@ctx_api_bp.post("/api/actions/<action_id>/approve")
def api_approve_action(action_id: str):
    reg = _registry()
    payload = request.get_json(force=True, silent=True) or {}
    reason = payload.get("reason", "")
    approver = payload.get("approver", "steve")
    decision_memory = approve_action(reg, action_id=action_id, approver_id=approver, reason=reason)
    return jsonify(decision_memory.metadata.constraints.get("decision", {}))


@ctx_api_bp.post("/api/actions/<action_id>/apply")
def api_apply_action(action_id: str):
    reg = _registry()
    applied = apply_action(reg, action_id=action_id)
    return jsonify(_action_payload(Action.from_memory(applied)))


@ctx_api_bp.get("/api/threads/<handle>/timeline")
def api_timeline(handle: str):
    reg = _registry()
    events = build_timeline(reg, handle)
    return jsonify({"handle": handle, "events": events})


@ctx_api_bp.get("/api/registry/validate")
def api_registry_validate():
    reg = _registry()
    reg.validate_chain()
    return jsonify({"status": "ok"})


__all__ = ["ctx_api_bp", "ctx_web_bp"]
