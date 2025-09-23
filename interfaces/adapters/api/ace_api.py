from __future__ import annotations

from flask import Blueprint, Response, jsonify, request, stream_with_context

from ace_control import (
    Brief,
    BriefPlanPreference,
    MachineProfile,
    OPERATE_ACTIONS,
    RunManager,
    RunStatus,
)
from ace_control.config_store import (
    load_budget_config,
    load_router_config,
    save_budget_config,
    save_router_config,
)
from ace_control.operate_policy import (
    ALLOWED_VALUES as OPERATE_POLICY_VALUES,
    get_policy as operate_policy_get_map,
    known_types as operate_policy_known_types,
    set_policy as operate_policy_set_map,
    update_policy as operate_policy_update_map,
)

ace_api_bp = Blueprint("ace_api_bp", __name__)

_RUN_MANAGER = RunManager()
@ace_api_bp.post("/runs")
def create_run():
    payload = request.get_json(force=True, silent=True) or {}
    brief_payload = payload.get("brief") or {}
    operate_action = payload.get("operate_action")
    conversation = payload.get("conversation")
    brief = Brief.from_dict(brief_payload)
    if brief.plan_preview == BriefPlanPreference.AUTO and any(tag.startswith("chat") for tag in brief.tags):
        brief.plan_preview = BriefPlanPreference.SHOW
    if brief.plan_preview == BriefPlanPreference.SHOW and not payload.get("execute", False):
        outline = RunManager.plan_outline(brief)
        return jsonify({"status": "plan_required", "plan_outline": outline}), 202
    record = _RUN_MANAGER.start_run(brief, operate_action=operate_action, conversation=conversation)
    return jsonify({"run": record.to_dict()})


@ace_api_bp.get("/runs")
def list_runs():
    status = request.args.get("status")
    runs = _RUN_MANAGER.list_runs(limit=int(request.args.get("limit", 20)))
    if status:
        status_value = status.lower()
        if status_value == "active":
            runs = [r for r in runs if r.status in {RunStatus.PENDING, RunStatus.RUNNING}]
        else:
            runs = [r for r in runs if r.status.value == status_value]
    return jsonify({"runs": [r.to_dict() for r in runs]})


@ace_api_bp.get("/runs/<run_id>/summary")
def run_summary(run_id: str):
    record = _RUN_MANAGER.get_run(run_id)
    return jsonify({"run": record.to_dict()})


@ace_api_bp.get("/runs/<run_id>/stream")
def run_stream(run_id: str):
    record = _RUN_MANAGER.get_run(run_id)
    try:
        if not record.log_path:
            raise FileNotFoundError
        log_path = _RUN_MANAGER.get_run_file(run_id, record.log_path)
        content = log_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        content = ""
    return Response(content, mimetype="text/plain")


@ace_api_bp.get("/runs/<run_id>/sse")
def run_sse(run_id: str):
    def generate():
        yield "retry: 5000\n\n"
        for event in _RUN_MANAGER.log_event_stream(run_id):
            yield event

    response = Response(stream_with_context(generate()), mimetype="text/event-stream")
    response.headers["Cache-Control"] = "no-cache"
    response.headers["X-Accel-Buffering"] = "no"
    return response


@ace_api_bp.get("/runs/<run_id>/artifacts")
def run_artifacts(run_id: str):
    record = _RUN_MANAGER.get_run(run_id)
    return jsonify({
        "artifacts": record.artifacts,
        "diff_path": record.diff_path,
        "prompt_path": record.prompt_path,
        "log_path": record.log_path,
    })


@ace_api_bp.post("/runs/<run_id>/rerun")
def rerun(run_id: str):
    record = _RUN_MANAGER.get_run(run_id)
    new_record = _RUN_MANAGER.start_run(record.brief)
    return jsonify({"run": new_record.to_dict(), "rerun_of": run_id})


@ace_api_bp.post("/runs/<run_id>/ignore")
def ignore_run(run_id: str):
    record = _RUN_MANAGER.update_status(run_id, status=RunStatus.CANCELLED, headline="Marked ignored")
    return jsonify({"run": record.to_dict()})


@ace_api_bp.post("/runs/<run_id>/cancel")
def cancel_run(run_id: str):
    record = _RUN_MANAGER.update_status(run_id, status=RunStatus.CANCELLED, headline="Cancelled")
    return jsonify({"run": record.to_dict()})


@ace_api_bp.post("/runs/<run_id>/push")
def push_run(run_id: str):
    payload = request.get_json(force=True, silent=True) or {}
    remote = str(payload.get("remote", "origin"))
    branch = payload.get("branch")
    try:
        result = _RUN_MANAGER.push_run(run_id, remote=remote, branch=branch)
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    except FileNotFoundError as exc:
        return jsonify({"ok": False, "error": "workspace_missing", "details": str(exc)}), 404
    status_code = 200 if result.get("ok") else 500
    return jsonify(result), status_code


@ace_api_bp.post("/runs/<run_id>/commit")
def commit_run(run_id: str):
    payload = request.get_json(force=True, silent=True) or {}
    message = payload.get("message")
    add_all = payload.get("add_all", True)
    try:
        result = _RUN_MANAGER.commit_run(run_id, message=message, add_all=bool(add_all))
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    except FileNotFoundError as exc:
        return jsonify({"ok": False, "error": "workspace_missing", "details": str(exc)}), 404
    status_code = 200 if result.get("ok") else 409
    return jsonify(result), status_code


@ace_api_bp.post("/runs/<run_id>/stage")
def stage_run(run_id: str):
    payload = request.get_json(force=True, silent=True) or {}
    check_only = bool(payload.get("check_only", False))
    try:
        result = _RUN_MANAGER.stage_patch(run_id, check_only=check_only)
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    except FileNotFoundError as exc:
        return jsonify({"ok": False, "error": "patch_missing", "details": str(exc)}), 404
    status_code = 200 if result.get("ok") else 409
    return jsonify(result), status_code


@ace_api_bp.post("/runs/<run_id>/commands")
def run_commands(run_id: str):
    payload = request.get_json(force=True, silent=True) or {}
    dry_run = bool(payload.get("dry_run", False))
    try:
        result = _RUN_MANAGER.run_commands(run_id, dry_run=dry_run)
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    except FileNotFoundError as exc:
        return jsonify({"ok": False, "error": "workspace_missing", "details": str(exc)}), 404
    status_code = 200 if result.get("ok") else 500
    return jsonify(result), status_code


@ace_api_bp.post("/runs/<run_id>/tests")
def run_tests(run_id: str):
    payload = request.get_json(force=True, silent=True) or {}
    dry_run = bool(payload.get("dry_run", False))
    try:
        result = _RUN_MANAGER.run_tests(run_id, dry_run=dry_run)
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    except FileNotFoundError as exc:
        return jsonify({"ok": False, "error": "workspace_missing", "details": str(exc)}), 404
    status_code = 200 if result.get("ok") else 500
    return jsonify(result), status_code


@ace_api_bp.post("/plan")
def plan_endpoint():
    payload = request.get_json(force=True, silent=True) or {}
    brief = Brief.from_dict(payload.get("brief") or payload)
    outline = RunManager.plan_outline(brief)
    return jsonify({"outline": outline})


@ace_api_bp.get("/history")
def history_endpoint():
    limit = int(request.args.get("limit", 20))
    runs = _RUN_MANAGER.list_runs(limit=limit)
    return jsonify({"runs": [r.to_dict() for r in runs]})


@ace_api_bp.get("/runs/<run_id>/file")
def run_file(run_id: str):
    rel_path = request.args.get("path")
    if not rel_path:
        return jsonify({"error": "path_required"}), 400
    try:
        file_path = _RUN_MANAGER.get_run_file(run_id, rel_path)
    except FileNotFoundError:
        return jsonify({"error": "file_not_found", "path": rel_path}), 404
    suffix = file_path.suffix.lower()
    mimetype = "text/plain"
    if suffix == ".json":
        mimetype = "application/json"
    elif suffix in {".md", ".txt", ".patch"}:
        mimetype = "text/plain"
    content = file_path.read_text(encoding="utf-8")
    return Response(content, mimetype=mimetype)


@ace_api_bp.get("/operate/commands")
def operate_commands():
    commands = []
    for command in OPERATE_ACTIONS.values():
        commands.append({
            "id": command.id,
            "title": command.title,
            "description": command.description,
            "command_count": len(command.commands),
        })
    return jsonify({"commands": commands})


@ace_api_bp.get("/operate/policy")
def operate_policy_index():
    policy = operate_policy_get_map()
    known = list(operate_policy_known_types())
    effective = {key: policy.get(key, "accept") for key in known}
    return jsonify(
        {
            "policy": policy,
            "known_types": known,
            "effective": effective,
            "values": sorted(OPERATE_POLICY_VALUES),
        }
    )


@ace_api_bp.put("/operate/policy")
def operate_policy_replace():
    payload = request.get_json(force=True, silent=True) or {}
    data = {
        str(key): str(value)
        for key, value in payload.items()
        if str(value) in OPERATE_POLICY_VALUES
    }
    updated = operate_policy_set_map(data)
    return jsonify({"policy": updated})


@ace_api_bp.patch("/operate/policy")
def operate_policy_patch():
    payload = request.get_json(force=True, silent=True) or {}
    data = {
        str(key): str(value)
        for key, value in payload.items()
        if str(value) in OPERATE_POLICY_VALUES
    }
    updated = operate_policy_update_map(data)
    return jsonify({"policy": updated})


@ace_api_bp.get("/machines")
def list_machines():
    registry = _RUN_MANAGER.machine_registry
    return jsonify({"machines": [m.to_dict() for m in registry.all()]})


@ace_api_bp.post("/machines")
def create_machine():
    payload = request.get_json(force=True, silent=True) or {}
    if "name" not in payload:
        return jsonify({"error": "name_required"}), 400
    profile = MachineProfile.from_dict(payload)
    _RUN_MANAGER.machine_registry.upsert(profile)
    return jsonify({"machine": profile.to_dict()}), 201


@ace_api_bp.patch("/machines/<name>")
def patch_machine(name: str):
    payload = request.get_json(force=True, silent=True) or {}
    try:
        updated = _RUN_MANAGER.machine_registry.patch(name, payload)
    except KeyError:
        return jsonify({"error": "machine_not_found", "name": name}), 404
    return jsonify({"machine": updated.to_dict()})


@ace_api_bp.delete("/machines/<name>")
def delete_machine(name: str):
    _RUN_MANAGER.machine_registry.delete(name)
    return jsonify({"ok": True})


@ace_api_bp.put("/machines")
def replace_machines():
    payload = request.get_json(force=True, silent=True) or {}
    machines_payload = payload.get("machines", [])
    machines = [MachineProfile.from_dict(item) for item in machines_payload]
    _RUN_MANAGER.machine_registry.replace_all(machines)
    return jsonify({"machines": [m.to_dict() for m in _RUN_MANAGER.machine_registry.all()]})


@ace_api_bp.get("/config/router")
def router_config_index():
    config, source = load_router_config()
    return jsonify({"config": config, "source": source})


@ace_api_bp.put("/config/router")
def router_config_update():
    payload = request.get_json(force=True, silent=True) or {}
    if not isinstance(payload, dict):
        return jsonify({"error": "invalid_payload", "detail": "Expected JSON object"}), 400
    config = save_router_config(payload)
    return jsonify({"config": config})


@ace_api_bp.get("/config/budget")
def budget_config_index():
    config, source = load_budget_config()
    return jsonify({"config": config, "source": source})


@ace_api_bp.put("/config/budget")
def budget_config_update():
    payload = request.get_json(force=True, silent=True) or {}
    if not isinstance(payload, dict):
        return jsonify({"error": "invalid_payload", "detail": "Expected JSON object"}), 400
    config = save_budget_config(payload)
    return jsonify({"config": config})
