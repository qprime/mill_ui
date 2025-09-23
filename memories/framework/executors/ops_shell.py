from __future__ import annotations

import platform
from pathlib import Path
from typing import Dict, List, Tuple

from ..ids import generate_ulid
from ..models import Action, Memory, MemoryContent, MemoryMetadata, Relations
from ..registry import MemoryRegistry
from ..utils import (
    ENABLE_FFMPEG,
    ENABLE_PANDOC,
    OFFLINE,
    active_memories_root,
    ensure_dir,
    sha256_text,
    utc_now,
    write_json,
    write_text,
)
from . import register_executor

__all__ = ["run", "simulate_artifacts"]


def _artifact_memory(action: Action, *, purpose: str, title: str, rel_path: str) -> Memory:
    stamp = utc_now()
    return Memory(
        id=generate_ulid(),
        type="artifact",
        purpose=purpose,
        handle=action.thread,
        title=title,
        tags=[purpose],
        state="done",
        registry_status="staged",
        relations=Relations(thread_of=action.id),
        content=MemoryContent(path=rel_path),
        metadata=MemoryMetadata(constraints={}),
        actor=action.actor,
        created_at=stamp,
        updated_at=stamp,
    )


def simulate_artifacts(action: Action) -> Tuple[Dict[str, str], str]:
    enable = ENABLE_PANDOC or ENABLE_FFMPEG
    if OFFLINE or not enable:
        log_text = f"OFFLINE ops shell run for {action.id}\n"
        summary = "ops shell stub"
    else:
        log_text = f"Enabled operations for {action.id}\n"
        summary = "ops shell executed"
    rel_path = f"artifacts/ops.runlog/{action.id}.log"
    return {rel_path: log_text}, summary


def run(action: Action, brief, registry: MemoryRegistry) -> Tuple[Memory, List[Memory], dict]:
    root = active_memories_root()
    run_dir = root / "actions" / action.id / "ops_shell"
    ensure_dir(run_dir)

    artifacts_map, summary = simulate_artifacts(action)
    artifact_memories: List[Memory] = []
    artifact_hashes: List[Dict[str, str]] = []
    for rel_str, body in artifacts_map.items():
        rel_path = Path(rel_str)
        absolute = root / rel_path
        ensure_dir(absolute.parent)
        write_text(absolute, body)
        artifact_hashes.append({"path": rel_str, "sha256": sha256_text(body)})
        memory = _artifact_memory(
            action,
            purpose=rel_path.parts[1],
            title=f"Ops log for {action.title}",
            rel_path=rel_str,
        )
        registry.register(memory)
        artifact_memories.append(memory)

    manifest = {
        "action_id": action.id,
        "executor": "ops_shell",
        "enable_pandoc": ENABLE_PANDOC,
        "enable_ffmpeg": ENABLE_FFMPEG,
        "offline": OFFLINE,
        "artifacts": list(artifacts_map.keys()),
        "artifact_hashes": artifact_hashes,
    }
    manifest_path = run_dir / "manifest.json"
    write_json(manifest_path, manifest)

    env_payload = {
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "offline": OFFLINE,
    }
    env_path = run_dir / "run_env.json"
    write_json(env_path, env_payload)

    updated_action = action.with_status("ready", updated_at=utc_now())
    updated_memory = updated_action.to_memory(
        purpose="plan.spec",
        state="active",
        registry_status="registered",
    )

    result = {
        "exit_code": 0,
        "summary": summary,
        "artifacts": list(artifacts_map.keys()),
    }
    return updated_memory, artifact_memories, result


register_executor("ops_shell", run)
