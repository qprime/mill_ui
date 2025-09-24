from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterable

from memories.framework import MemoryRegistry
from memories.framework.threading import ensure_chat_session, link_produced
from memories.framework.ids import generate_ulid
from memories.framework.models import Actor, Memory, MemoryContent, MemoryMetadata, Relations

from .models import RunRecord, RunStatus, now_ts

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _summary_json(run: RunRecord, run_dir: Path) -> Dict[str, object]:
    payload: Dict[str, object] = run.to_dict()
    payload["run_dir"] = str(run_dir)
    return payload


def write_summary_file(run: RunRecord, run_dir: Path) -> Path:
    summary_path = run_dir / "summary.json"
    summary_path.write_text(json.dumps(_summary_json(run, run_dir), indent=2), encoding="utf-8")
    return summary_path


def _relative_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path.resolve())


def record_memory_entry(
    registry: MemoryRegistry,
    run: RunRecord,
    *,
    run_dir: Path,
    summary_path: Path,
    result_paths: Iterable[str],
) -> Memory:
    actor = Actor(actor_id="ace_control", actor_type="ai")
    created = now_ts()
    # Detect thread/chat linkage from tags: allow tags like "thread:<chat_id>" or "chat:<chat_id>"
    chat_id = None
    for tag in run.tags:
        if isinstance(tag, str) and (tag.startswith("thread:") or tag.startswith("chat:")):
            chat_id = tag.split(":", 1)[1].strip() or None
            break
    session_id = None
    handle_value = run.id
    thread_of_value = run.id
    if chat_id:
        session = ensure_chat_session(registry, chat_id=chat_id)
        session_id = session.id
        handle_value = chat_id
        thread_of_value = session_id
    memory = Memory(
        id=generate_ulid(),
        type="note",
        purpose="ace.run.summary",
        handle=handle_value,
        title=f"Ace run {run.id}",
        tags=list(set(["acecontrol", run.mode.value, run.status.value] + run.tags)),
        state="done" if run.status == RunStatus.SUCCEEDED else "active",
        registry_status="registered",
        relations=Relations(thread_of=thread_of_value),
        content=MemoryContent(path=_relative_path(summary_path) if summary_path.exists() else None),
        metadata=MemoryMetadata(constraints={
            "run_id": run.id,
            "headline": run.headline,
            "artifacts": sorted({p for p in result_paths if p}),
            "log_path": run.log_path,
        }),
        actor=actor,
        created_at=created,
        updated_at=created,
    )
    memory = registry.register(memory)
    # Link the run summary under the session for forward traversal
    if session_id:
        try:
            link_produced(registry, parent_id=session_id, child_id=memory.id)
        except Exception:
            pass
    return memory
