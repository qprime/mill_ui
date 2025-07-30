"""Tasks blueprint: handles /tasks routes for backlog, creation, editing, update, archive, reorder."""

from flask import Blueprint, request, render_template, redirect, url_for, jsonify
from services.task_service import (
    get_active_tasks_grouped,
    update_task_status,
    create_task_entry,
    edit_task_entry,
    get_task_entry,
    archive_task_entry,
    reorder_tasks_by_ids,
)
from datetime import datetime

tasks_bp = Blueprint("tasks", __name__)

@tasks_bp.route("/tasks")
def show_tasks():
    tasks_by_status = get_active_tasks_grouped()
    return render_template("task_backlog.html", tasks_by_status=tasks_by_status)

@tasks_bp.route("/tasks/update", methods=["POST"])
def update_task():
    task_id = request.form.get("task_id")
    new_status = request.form.get("new_status")
    if task_id and new_status:
        update_task_status(task_id, new_status)
    return redirect(url_for("tasks.show_tasks"))

@tasks_bp.route("/tasks/create", methods=["GET", "POST"])
def create_task_form():
    if request.method == "POST":
        data = {
            "title": request.form.get("title"),
            "description": request.form.get("description"),
            "tags": [t.strip() for t in request.form.get("tags", "").split(",") if t.strip()],
            "files": [f.strip() for f in request.form.get("files", "").split(",") if f.strip()],
            "steps": [s.strip() for s in request.form.get("steps", "").split("\n") if s.strip()]
        }
        create_task_entry(**data)
        return redirect(url_for("tasks.show_tasks"))
    return render_template("task_create.html")

@tasks_bp.route("/tasks/edit/<task_id>", methods=["GET", "POST"])
def edit_task(task_id):
    if request.method == "POST":
        updated_data = {
            "title": request.form.get("title"),
            "description": request.form.get("description"),
            "tags": [t.strip() for t in request.form.get("tags", "").split(",") if t.strip()],
            "files": [f.strip() for f in request.form.get("files", "").split(",") if f.strip()],
            "steps": [s.strip() for s in request.form.get("steps", "").split("\n") if s.strip()],
            "updated_at": datetime.utcnow().isoformat()
        }
        edit_task_entry(task_id, updated_data)
        return redirect(url_for("tasks.show_tasks"))
    task = get_task_entry(task_id)
    return render_template("task_edit.html", task=task)

@tasks_bp.route("/tasks/archive/<task_id>", methods=["POST"])
def archive_task(task_id):
    archive_task_entry(task_id)
    return redirect(url_for("tasks.show_tasks"))

@tasks_bp.route("/tasks/reorder", methods=["POST"])
def reorder_tasks():
    data = request.get_json()
    ids = data.get("ids", [])
    if not isinstance(ids, list):
        return jsonify({"error": "Invalid format"}), 400
    reorder_tasks_by_ids(ids)
    return jsonify({"status": "ok"}), 200
