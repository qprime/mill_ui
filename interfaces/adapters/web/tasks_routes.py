from __future__ import annotations
from flask import Blueprint, render_template, request, redirect, url_for
from ...services.tasks import tasks_api

tasks_web_bp = Blueprint("tasks_web_bp", __name__, template_folder="../../templates")

@tasks_web_bp.get("/tasks")
def tasks_page():
    data = tasks_api({"action": "get_active_grouped"})
    return render_template("tasks/index.html", data=data)

@tasks_web_bp.post("/tasks/status")
def tasks_status():
    task_id = str(request.form.get("task_id"))
    status = str(request.form.get("status"))
    tasks_api({"action": "update_status", "task_id": task_id, "status": status})
    return redirect(url_for("tasks_web_bp.tasks_page"))
