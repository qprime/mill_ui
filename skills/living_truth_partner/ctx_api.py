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
from skills.memory_framework.utils import MEMORIES_ROOT, read_text

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


# ---------- Enhancements for rich UI ----------


@ctx_api_bp.get("/api/actions/<action_id>")
def api_get_action(action_id: str):
    reg = _registry()
    action = get_action(reg, action_id)
    # Collect artifacts and decisions linked to this action
    artifacts = [
        {
            "id": m.id,
            "purpose": m.purpose,
            "title": m.title,
            "path": m.content.path,
            "created_at": m.created_at,
        }
        for m in reg.query({"type": "artifact"}, limit=1000)
        if m.relations.thread_of == action_id
    ]
    decisions = [
        {
            "id": m.id,
            "title": m.title,
            "created_at": m.created_at,
            "policy_check_path": m.content.path,
        }
        for m in reg.query({"type": "decision"}, limit=200)
        if m.handle == action_id
    ]
    # Find latest capsule linked to action
    capsules = [
        m
        for m in reg.query({"type": "capsule"}, limit=500)
        if m.relations.thread_of == action_id
    ]
    latest_capsule = None
    if capsules:
        latest_capsule = sorted(capsules, key=lambda m: (m.created_at, m.id))[-1]
    payload = {
        "action": action.to_dict(),
        "artifacts": artifacts,
        "decisions": decisions,
        "capsule": {
            "id": latest_capsule.id,
            "prompt_path": latest_capsule.content.path,
        }
        if latest_capsule
        else None,
    }
    return jsonify(payload)


@ctx_api_bp.get("/api/actions/<action_id>/artifacts")
def api_action_artifacts(action_id: str):
    reg = _registry()
    items = [
        {
            "id": m.id,
            "purpose": m.purpose,
            "title": m.title,
            "path": m.content.path,
            "created_at": m.created_at,
        }
        for m in reg.query({"type": "artifact"}, limit=1000)
        if m.relations.thread_of == action_id
    ]
    return jsonify({"artifacts": items})


@ctx_api_bp.get("/api/actions/<action_id>/capsule")
def api_action_capsule(action_id: str):
    reg = _registry()
    # latest capsule for this action
    capsules = [
        m
        for m in reg.query({"type": "capsule"}, limit=500)
        if m.relations.thread_of == action_id
    ]
    if not capsules:
        return jsonify({"capsule": None})
    cap = sorted(capsules, key=lambda m: (m.created_at, m.id))[-1]
    prompt_path = cap.content.path
    prompt_text = ""
    if prompt_path:
        abs_path = MEMORIES_ROOT / prompt_path
        if abs_path.exists():
            prompt_text = read_text(abs_path)
    return jsonify(
        {
            "capsule": {
                "id": cap.id,
                "prompt_path": prompt_path,
                "prompt_text": prompt_text,
            }
        }
    )


__all__ = ["ctx_api_bp", "ctx_web_bp"]
