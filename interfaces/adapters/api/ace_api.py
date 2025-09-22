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

ace_api_bp = Blueprint("ace_api_bp", __name__)

_RUN_MANAGER = RunManager()
@ace_api_bp.post("/runs")
def create_run():
    payload = request.get_json(force=True, silent=True) or {}
    brief_payload = payload.get("brief") or {}
    operate_action = payload.get("operate_action")
    brief = Brief.from_dict(brief_payload)
    if brief.plan_preview == BriefPlanPreference.SHOW and not payload.get("execute", False):
        outline = RunManager.plan_outline(brief)
        return jsonify({"status": "plan_required", "plan_outline": outline}), 202
    record = _RUN_MANAGER.start_run(brief, operate_action=operate_action)
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
