import json
import uuid
from datetime import datetime
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
TASKS_DIR = PROJECT_ROOT / "memory/tasks"

def _now():
    return datetime.utcnow().isoformat() + "Z"

def save_task(task):
    task_dir = TASKS_DIR / task["id"]
    task_dir.mkdir(parents=True, exist_ok=True)
    task_path = task_dir / "task.json"
    with open(task_path, "w") as f:
        json.dump(task, f, indent=2)

def load_tasks():
    all_tasks = []
    if not TASKS_DIR.exists():
        return all_tasks

    for task_dir in TASKS_DIR.iterdir():
        if task_dir.is_dir():
            task_path = task_dir / "task.json"
            if task_path.exists():
                try:
                    with open(task_path, "r") as f:
                        all_tasks.append(json.load(f))
                except json.JSONDecodeError:
                    continue
    return all_tasks

def get_task(task_id):
    task_path = TASKS_DIR / task_id / "task.json"
    if task_path.exists():
        with open(task_path, "r") as f:
            return json.load(f)
    return None

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
        "related_tasks": [],
        "archived": False,
        "order": 0
    }
    save_task(task)
    return task

def update_task(task_id, changes):
    task = get_task(task_id)
    if not task:
        raise FileNotFoundError(f"Task {task_id} not found")
    task.update(changes)
    task["updated_at"] = _now()
    save_task(task)

def list_tasks(status_filter=None):
    tasks = load_tasks()
    if status_filter:
        return [t for t in tasks if t["status"] == status_filter]
    return tasks

def reorder_tasks_by_ids(ordered_ids):
    id_to_index = {tid: idx for idx, tid in enumerate(ordered_ids)}
    tasks = load_tasks()

    for task in tasks:
        if task["status"] == "planned" and task["id"] in id_to_index:
            task["order"] = id_to_index[task["id"]]
            save_task(task)
