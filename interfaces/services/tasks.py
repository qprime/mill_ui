from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional

from memories.task_manager import load_tasks, update_task, create_task, get_task
try:
    from memories.task_manager import reorder_tasks_by_ids as _reorder_ids
except Exception:
    _reorder_ids = None  # type: ignore

__all__ = ["tasks_api"]

@dataclass(frozen=True)
class Config:
    pass

def _get_active_grouped() -> Dict[str, Any]:
    raw = load_tasks()
    tasks = [t for t in raw if str(t.get("archived", "false")).lower() != "true"]
    by_status: Dict[str, list] = {}
    for t in tasks:
        by_status.setdefault(str(t.get("status", "todo")).lower(), []).append(t)
    return {"groups": by_status, "count": len(tasks)}

def _update_status(task_id: str, status: str) -> Dict[str, Any]:
    update_task(task_id, {"status": status})
    return {"ok": True, "task_id": task_id, "status": status}

def _create_entry(title: str, description: str = "") -> Dict[str, Any]:
    t = create_task({"title": title, "description": description})
    return {"ok": True, "task": t}

def _edit_entry(task_id: str, patch: Dict[str, Any]) -> Dict[str, Any]:
    update_task(task_id, patch)
    return {"ok": True, "task": get_task(task_id)}

def _archive(task_id: str) -> Dict[str, Any]:
    from datetime import datetime
    update_task(task_id, {"archived": True, "updated_at": datetime.utcnow().isoformat()})
    return {"ok": True, "task_id": task_id}

def _reorder(ids: list[str]) -> Dict[str, Any]:
    if callable(_reorder_ids):
        _reorder_ids(ids)  # type: ignore[misc]
        return {"ok": True, "ids": ids}
    return {"ok": False, "error": "reorder_not_available"}

def tasks_api(payload: Mapping[str, Any], config: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    """Public entry; expects an 'action' key."""
    _ = Config(**dict(config)) if isinstance(config, Mapping) else Config()
    action = str(payload.get("action", "get_active_grouped"))
    if action == "get_active_grouped":
        return _get_active_grouped()
    if action == "update_status":
        return _update_status(str(payload.get("task_id")), str(payload.get("status")))
    if action == "create":
        return _create_entry(str(payload.get("title", "")), str(payload.get("description") or ""))
    if action == "edit":
        return _edit_entry(str(payload.get("task_id")), dict(payload.get("patch") or {}))
    if action == "archive":
        return _archive(str(payload.get("task_id")))
    if action == "reorder":
        return _reorder(list(payload.get("ids") or []))
    return {"ok": False, "error": "unknown_action", "action": action}
