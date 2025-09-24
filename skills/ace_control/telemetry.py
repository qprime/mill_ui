"""Simple telemetry recorder for ACE operations."""
from __future__ import annotations

import json
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from .config_store import _config_dir as config_dir_helper

_LOCK = threading.Lock()
_TELEMETRY_FILE = "ace_telemetry.jsonl"


def _telemetry_path() -> Path:
    base = config_dir_helper()
    path = base / _TELEMETRY_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _append(event: Dict[str, Any]) -> None:
    event.setdefault("timestamp", datetime.utcnow().isoformat(timespec="milliseconds") + "Z")
    path = _telemetry_path()
    line = json.dumps(event, sort_keys=True)
    with _LOCK:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")


def record_run(run: Any, provider: str, exit_code: Optional[int], stats: Optional[Dict[str, Any]] = None) -> None:
    payload = {
        "event": "run",
        "run_id": getattr(run, "id", None),
        "provider": provider,
        "status": getattr(run, "status", None).value if getattr(run, "status", None) else None,
        "created_at": getattr(run, "created_at", None),
        "updated_at": getattr(run, "updated_at", None),
        "machine": (run.machines or [None])[0] if getattr(run, "machines", None) else None,
        "command_count": len(getattr(run, "commands", []) or []),
        "test_count": len(getattr(run, "tests", []) or []),
        "artifact_count": len(getattr(run, "artifacts", []) or []),
        "exit_code": exit_code,
    }
    if stats:
        payload.update(stats)
    _append(payload)


def record_action(run_id: str, action: str, ok: bool, metadata: Optional[Dict[str, Any]] = None) -> None:
    payload = {
        "event": "action",
        "run_id": run_id,
        "action": action,
        "ok": bool(ok),
    }
    if metadata:
        payload.update(metadata)
    _append(payload)
