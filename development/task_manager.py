import json
import uuid
from datetime import datetime
from pathlib import Path

TASK_FILE = Path(__file__).resolve().parents[1] / "memory/development/task_state.jsonl"


def _now():
    return datetime.utcnow().isoformat() + "Z"


def load_tasks():
    if not TASK_FILE.exists():
        return []
    with open(TASK_FILE, "r") as f:
        return [json.loads(line) for line in f if line.strip()]


def save_task(task):
    with open(TASK_FILE, "a") as f:
        f.write(json.dumps(task) + "\n")


def create_task(title, description, files=None, tags=None, steps=None):
    task = {
        "id": f"task_{uuid.uuid4().hex[:8]}",
        "title": title,
        "description": description,
        "status": "planned",
        "created_at": _now(),
        "updated_at": _now(),
        "files": files or [],
        "tags": tags or [],
        "steps": steps or [],
        "current_step": 0,
        "notes": "",
        "paused_state": None,
        "blocked_by": [],
        "related_tasks": []
    }
    save_task(task)
    return task


def list_tasks(status_filter=None):
    tasks = load_tasks()
    if status_filter:
        return [t for t in tasks if t["status"] == status_filter]
    return tasks


def update_task(task_id, updates):
    tasks = load_tasks()
    updated = False
    for task in tasks:
        if task["id"] == task_id:
            task.update(updates)
            task["updated_at"] = _now()
            updated = True
    if updated:
        with open(TASK_FILE, "w") as f:
            for task in tasks:
                f.write(json.dumps(task) + "\n")
    return updated


def get_task(task_id):
    for task in load_tasks():
        if task["id"] == task_id:
            return task
    return None
