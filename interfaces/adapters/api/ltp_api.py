from __future__ import annotations
import json
from typing import Any, Iterable
import tempfile
from pathlib import Path
from flask import Blueprint, jsonify, request
from skills.living_truth_partner.action_items import append as append_action, load as load_actions, set_state
from skills.living_truth_partner.config import Config
from skills.living_truth_partner.distill import Distill
from skills.living_truth_partner.export_doc import ExportDoc
from skills.living_truth_partner.guardrails import analyze
from skills.living_truth_partner.persona_builder import add_persona
from skills.living_truth_partner.project_store import ProjectStore
from skills.living_truth_partner.revision import apply as apply_revision, prepare
from skills.living_truth_partner.section_patch import SectionPatch
from skills.living_truth_partner.target_patch import TargetPatch
from skills.living_truth_partner.voice_append import VoiceAppend

ltp_api_bp = Blueprint("ltp_api_bp", __name__)


def _config() -> Config:
    return Config.load()


def _store(slug: str) -> tuple[Config, ProjectStore]:
    config = _config()
    return config, ProjectStore.open(config, slug)


def _summary(store: ProjectStore) -> dict[str, Any]:
    if not store.summary_path.exists():
        return {}
    return json.loads(store.summary_path.read_text(encoding="utf-8"))


def _prompts(store: ProjectStore) -> list[str]:
    if not store.prompts_path.exists():
        return []
    data = json.loads(store.prompts_path.read_text(encoding="utf-8"))
    return data.get("prompts", [])


def _action_items(store: ProjectStore) -> list[dict[str, Any]]:
    return load_actions(store)


def _sections(store: ProjectStore) -> list[dict[str, Any]]:
    payload = []
    for insight in analyze(store):
        payload.append({
            "id": insight.section_id,
            "title": insight.title,
            "word_count": insight.word_count,
            "snippet": insight.snippet,
            "issues": insight.issues,
            "quick_actions": insight.quick_actions
        })
    return payload


def _revision(store: ProjectStore, section_ids: Iterable[str] | None) -> list[dict[str, Any]]:
    suggestions = prepare(store, section_ids)
    return [
        {
            "section_id": s.section_id,
            "title": s.title,
            "intent": s.intent,
            "constraints": s.constraints,
            "reason": s.reason
        }
        for s in suggestions
    ]


def _patch_response(result: SectionPatch.Result) -> dict[str, Any]:
    return {
        "changed": result.changed,
        "patch": str(result.patch_path) if result.patch_path else None,
        "before": result.before,
        "after": result.after,
        "diff": result.diff
    }


def _target_response(result: TargetPatch.Result) -> dict[str, Any]:
    return {
        "changed": result.changed,
        "patch": str(result.patch_path) if result.patch_path else None,
        "before": result.before,
        "after": result.after,
        "diff": result.diff
    }


@ltp_api_bp.get("/projects/<slug>/snapshot")
def snapshot(slug: str):
    _, store = _store(slug)
    data = {
        "summary": _summary(store),
        "prompts": _prompts(store),
        "action_items": _action_items(store),
        "sections": _sections(store)
    }
    return jsonify(data)


@ltp_api_bp.post("/projects/<slug>/voice")
def voice(slug: str):
    config, store = _store(slug)
    file = request.files.get("file")
    if file is None:
        return jsonify({"error": "file missing"}), 400
    store.history_root.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav", dir=store.history_root) as handle:
        file.save(handle)
        temp_file = Path(handle.name)
    result = VoiceAppend.run(store, config, temp_file, None)
    temp_file.unlink(missing_ok=True)
    distill_result = Distill.run(store, config)
    payload = {
        "transcript": result.transcript,
        "notes_path": str(result.notes_path),
        "summary_path": str(distill_result.summary_path),
        "summary": _summary(store),
        "prompts": _prompts(store),
        "action_items": _action_items(store),
        "sections": _sections(store)
    }
    return jsonify(payload)


@ltp_api_bp.post("/projects/<slug>/tidy")
def tidy(slug: str):
    config, store = _store(slug)
    result = Distill.run(store, config)
    payload = {
        "summary_path": str(result.summary_path),
        "summary": _summary(store),
        "prompts": _prompts(store),
        "action_items": _action_items(store),
        "sections": _sections(store)
    }
    return jsonify(payload)


@ltp_api_bp.get("/projects/<slug>/sections")
def sections(slug: str):
    _, store = _store(slug)
    return jsonify({"sections": _sections(store)})


@ltp_api_bp.post("/projects/<slug>/sections/<section_id>/preview")
def section_preview(slug: str, section_id: str):
    config, store = _store(slug)
    data = request.get_json(force=True)
    intent = data.get("intent", "")
    constraints = data.get("constraints", [])
    result = SectionPatch.run(store, config, section_id, intent, constraints, False)
    return jsonify(_patch_response(result))


@ltp_api_bp.post("/projects/<slug>/sections/<section_id>/apply")
def section_apply(slug: str, section_id: str):
    config, store = _store(slug)
    data = request.get_json(force=True)
    intent = data.get("intent", "")
    constraints = data.get("constraints", [])
    result = SectionPatch.run(store, config, section_id, intent, constraints, True)
    return jsonify(_patch_response(result))


@ltp_api_bp.post("/projects/<slug>/targets/<target_id>/preview")
def target_preview(slug: str, target_id: str):
    config, store = _store(slug)
    data = request.get_json(force=True)
    intent = data.get("intent", "")
    constraints = data.get("constraints", [])
    result = TargetPatch.run(store, config, target_id, intent, constraints, False)
    return jsonify(_target_response(result))


@ltp_api_bp.post("/projects/<slug>/targets/<target_id>/apply")
def target_apply(slug: str, target_id: str):
    config, store = _store(slug)
    data = request.get_json(force=True)
    intent = data.get("intent", "")
    constraints = data.get("constraints", [])
    result = TargetPatch.run(store, config, target_id, intent, constraints, True)
    return jsonify(_target_response(result))


@ltp_api_bp.get("/projects/<slug>/prompts")
def prompts(slug: str):
    _, store = _store(slug)
    return jsonify({"prompts": _prompts(store)})


@ltp_api_bp.get("/projects/<slug>/action-items")
def action_items(slug: str):
    _, store = _store(slug)
    return jsonify({"action_items": _action_items(store)})


@ltp_api_bp.post("/projects/<slug>/action-items")
def action_items_update(slug: str):
    _, store = _store(slug)
    data = request.get_json(force=True)
    if "add" in data:
        items = append_action(store, data.get("add", ""))
    elif "index" in data:
        items = set_state(store, int(data.get("index", 0)), bool(data.get("done", False)))
    else:
        items = _action_items(store)
    return jsonify({"action_items": items})


@ltp_api_bp.post("/projects/<slug>/personas")
def persona(slug: str):
    _, store = _store(slug)
    data = request.get_json(force=True)
    ok = add_persona(store, data or {})
    return jsonify({"ok": ok, "sections": _sections(store)})


@ltp_api_bp.post("/projects/<slug>/revise")
def revision(slug: str):
    config, store = _store(slug)
    data = request.get_json(force=True)
    sections = data.get("sections") or []
    apply_flag = bool(data.get("apply", False))
    suggestions = prepare(store, sections)
    response = {
        "suggestions": [
            {
                "section_id": s.section_id,
                "title": s.title,
                "intent": s.intent,
                "constraints": s.constraints,
                "reason": s.reason
            }
            for s in suggestions
        ]
    }
    if apply_flag and suggestions:
        results = apply_revision(store, config, suggestions, True)
        response["results"] = [_patch_response(r) for r in results]
    else:
        response["results"] = []
    return jsonify(response)


@ltp_api_bp.post("/projects/<slug>/export")
def export_doc(slug: str):
    config, store = _store(slug)
    data = request.get_json(force=True)
    kind = data.get("kind", "pdf")
    result = ExportDoc.run(store, config, kind)
    return jsonify({
        "output": str(result.output_path),
        "command": result.command
    })
