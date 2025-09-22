from __future__ import annotations
import json
from typing import Any, Iterable, Optional
import tempfile
from pathlib import Path
from flask import Blueprint, jsonify, request
import httpx
from cortex.ai_router import get_router
from skills.living_truth_partner.action_items import append as append_action, load as load_actions, set_state
from skills.living_truth_partner.config import Config
from skills.living_truth_partner.distill import Distill
from skills.living_truth_partner.export_doc import ExportDoc
from skills.living_truth_partner.guardrails import analyze
from skills.living_truth_partner.md_index import MarkdownIndex
from skills.living_truth_partner.persona_builder import add_persona
from skills.living_truth_partner.project_store import ProjectInfo, ProjectStore
from skills.living_truth_partner.revision import apply as apply_revision, prepare
from skills.living_truth_partner.section_patch import SectionPatch
from skills.living_truth_partner.target_patch import TargetPatch
from skills.living_truth_partner.templates import (
    TemplateSpec,
    list_templates,
    load_template_body,
    quick_checks,
    tone_presets,
)
from skills.living_truth_partner.voice_append import VoiceAppend

ltp_api_bp = Blueprint("ltp_api_bp", __name__)


def _config() -> Config:
    return Config.load()


def _store(slug: str) -> tuple[Config, ProjectStore]:
    config = _config()
    return config, ProjectStore.open(config, slug)


def _as_verify_arg(raw: Config | bool | str | Path | None) -> bool | str:
    if raw is None:
        return True
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, Path):
        return str(raw)
    return raw


def _project_payload(info: ProjectInfo) -> dict[str, Any]:
    return {
        "slug": info.slug,
        "title": info.title,
        "updated_at": info.updated_at,
        "owners": info.owners,
        "tags": info.tags,
    }


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


def _section_body(store: ProjectStore, section_id: str) -> tuple[str, dict[str, Any]]:
    text = store.doc_path.read_text(encoding="utf-8")
    index = MarkdownIndex.build(text)
    section = index.section(section_id)
    if section is None:
        return "", {"title": "", "id": section_id}
    body = index.slice(text, section_id)
    return body, {"title": section.title, "id": section.id}


@ltp_api_bp.get("/projects")
def projects_index():
    config = _config()
    limit = request.args.get("limit")
    limit_value: Optional[int] = int(limit) if limit and limit.isdigit() else None
    projects = ProjectStore.list(config, limit=limit_value)
    return jsonify({"projects": [_project_payload(info) for info in projects]})


@ltp_api_bp.post("/projects")
def projects_create():
    config = _config()
    data = request.get_json(force=True, silent=True) or {}
    title = str(data.get("title", "")).strip()
    if not title:
        return jsonify({"error": "title_required"}), 400
    slug = str(data.get("slug", title)).strip()
    owners = [str(item).strip() for item in data.get("owners", []) if str(item).strip()]
    tags = [str(item).strip() for item in data.get("tags", []) if str(item).strip()]
    template_id = data.get("template")
    body = str(data.get("body", "")).strip() or None
    if template_id:
        try:
            body = load_template_body(config, template_id, title=title)
        except KeyError:
            return jsonify({"error": "template_not_found", "template": template_id}), 404
    store = ProjectStore.create(config, slug, title, owners, tags, body=body)
    payload = {
        "slug": store.slug,
        "title": store.title,
        "summary": _summary(store),
    }
    return jsonify(payload), 201


@ltp_api_bp.get("/templates")
def templates_index():
    config = _config()
    templates: list[TemplateSpec] = list_templates(config)
    return jsonify(
        {
            "templates": [
                {
                    "id": tmpl.id,
                    "title": tmpl.title,
                    "description": tmpl.description,
                }
                for tmpl in templates
            ],
            "tones": [
                {"id": tone.id, "label": tone.label, "instructions": tone.instructions}
                for tone in tone_presets()
            ],
            "quick_checks": [
                {
                    "id": item.id,
                    "label": item.label,
                    "intent": item.intent,
                    "constraints": item.constraints,
                    "section_hint": item.section_hint,
                }
                for item in quick_checks()
            ],
        }
    )


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


@ltp_api_bp.get("/status/whisper")
def whisper_status():
    config = _config()
    url = str(config.whisper_url or "").strip()
    if not url:
        return jsonify({"ok": False, "url": "", "reason": "not_configured"})

    verify_arg = _as_verify_arg(config.whisper_verify)
    ok = False
    reason = ""
    status_code = None
    try:
        with httpx.Client(verify=verify_arg, timeout=5.0, follow_redirects=True) as client:
            response = client.head(url)
            status_code = response.status_code
            reason = response.reason_phrase or ""
            if status_code == 405:
                ok = True
            elif status_code is not None and status_code < 500:
                ok = True
    except httpx.RequestError as exc:
        reason = str(exc)
    except Exception as exc:  # pragma: no cover - defensive
        reason = str(exc)
    return jsonify({
        "ok": ok,
        "url": url,
        "status": status_code,
        "reason": reason,
    })


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


@ltp_api_bp.post("/projects/<slug>/compose-brief")
def compose_brief(slug: str):
    config, store = _store(slug)
    data = request.get_json(force=True, silent=True) or {}
    summary = _summary(store)
    intent = str(data.get("intent") or "").strip()
    if not intent:
        intent = f"Advance the document '{summary.get('title') or store.slug}' by applying planned revisions."
    constraints = data.get("constraints") or summary.get("constraints", [])
    sections = data.get("sections") or []
    acceptance = summary.get("acceptance_criteria", [])
    notes = str(data.get("notes", "")).strip()
    doc_path = f"living_docs/docs/{store.slug}.ltd.md"
    lines = [
        f"Document: {summary.get('title') or store.slug}",
        f"Path: {doc_path}",
        "",
        f"Intent: {intent}",
    ]
    if sections:
        lines.append(f"Sections: {', '.join(sections)}")
    if constraints:
        lines.append("Constraints:")
        for constraint in constraints:
            lines.append(f"- {constraint}")
    if acceptance:
        lines.append("Acceptance Criteria:")
        for item in acceptance:
            lines.append(f"- {item}")
    if notes:
        lines.append("Notes:")
        lines.append(notes)
    brief_payload: dict[str, Any] = {
        "mode": data.get("mode", "build"),
        "text": "\n".join(lines).strip(),
        "machines": data.get("machines") or ["skylink"],
        "tags": summary.get("tags", []),
        "plan_preview": data.get("plan_preview", "show" if data.get("request_plan") else "auto"),
    }
    if data.get("model"):
        brief_payload["model"] = data["model"]
    if data.get("reasoning"):
        brief_payload["reasoning"] = data["reasoning"]
    context = {
        "summary": summary,
        "sections": sections,
        "intent": intent,
        "constraints": constraints,
        "acceptance": acceptance,
    }
    return jsonify({"brief": brief_payload, "context": context})


@ltp_api_bp.post("/projects/<slug>/coauthor")
def coauthor(slug: str):
    config, store = _store(slug)
    data = request.get_json(force=True, silent=True) or {}
    prompt = str(data.get("prompt", "")).strip()
    if not prompt:
        return jsonify({"error": "prompt_required"}), 400
    section_id = str(data.get("section_id", "")).strip() or None
    section_text = ""
    section_meta: dict[str, Any] = {}
    if section_id:
        section_text, section_meta = _section_body(store, section_id)
    summary = _summary(store)
    message = {
        "role": "user",
        "content": json.dumps(
            {
                "prompt": prompt,
                "section": section_meta,
                "section_text": section_text[:2000],
                "summary": summary,
            },
            indent=2,
        ),
    }
    system = {
        "role": "system",
        "content": (
            "You draft revision guidance for a Living Truth Partner document. "
            "Return JSON with keys: intent (str), constraints (list[str]), draft (optional str). "
            "Stay grounded in the provided section summary and prompt."
        ),
    }
    router = get_router()
    reply = router.chat([system, message], model=config.prose_model)
    suggestion: dict[str, Any]
    try:
        suggestion = json.loads(reply)
    except json.JSONDecodeError:
        suggestion = {"intent": prompt, "constraints": [], "draft": reply.strip()}
    if "constraints" not in suggestion or not isinstance(suggestion["constraints"], list):
        suggestion["constraints"] = []
    return jsonify({"suggestion": suggestion})
