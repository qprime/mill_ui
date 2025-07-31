"""Task services for CLIFF."""

from memory.task_manager import load_tasks, update_task, create_task, get_task

def get_active_tasks_grouped():
    raw_tasks = load_tasks()
    tasks = [t for t in raw_tasks if not str(t.get("archived", "false")).lower() == "true"]
    for task in tasks:
        if task.get("status") == "planned":
            task.setdefault("order", 0)
    grouped = {}
    for task in tasks:
        status = task.get("status", "unknown")
        grouped.setdefault(status, []).append(task)
    if "planned" in grouped:
        grouped["planned"].sort(key=lambda t: t.get("order", 0))
    return grouped

def update_task_status(task_id, new_status):
    update_task(task_id, {"status": new_status})

def create_task_entry(title, description, tags, files, steps):
    create_task(
        title=title,
        description=description,
        tags=tags,
        files=files,
        steps=steps
    )

def edit_task_entry(task_id, updated_data):
    update_task(task_id, updated_data)

def get_task_entry(task_id):
    return get_task(task_id)

def archive_task_entry(task_id):
    from datetime import datetime
    update_task(task_id, {
        "archived": True,
        "updated_at": datetime.utcnow().isoformat()
    })

def reorder_tasks_by_ids(ids):
    # NOTE: Ensure correct import path! If this is in the main project, use full package path:
    from memory.task_manager import reorder_tasks_by_ids as _reorder
    _reorder(ids)
