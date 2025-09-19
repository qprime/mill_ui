from __future__ import annotations

import platform
from pathlib import Path
from typing import Dict, List, Tuple

from ..ids import generate_ulid
from ..models import Action, Memory, MemoryContent, MemoryMetadata, Relations
from ..registry import MemoryRegistry
from ..utils import (
    ENABLE_CODEX_CLI,
    MEMORIES_ROOT,
    OFFLINE,
    WORKTREE_ROOT,
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


def simulate_artifacts(action: Action) -> Dict[str, str]:
    if OFFLINE or not ENABLE_CODEX_CLI:
        diff_body = (
            f"--- a/sample.py\n+++ b/sample.py\n@@\n-print('old')\n+print('offline codex {action.id}')\n"
        )
        test_log = "Simulated tests: PASS\n"
    else:
        diff_body = ""
        test_log = "Tests executed (placeholder)\n"
    return {
        f"artifacts/code.diff/{action.id}.codex.patch": diff_body,
        f"artifacts/test.log/{action.id}.log": test_log,
    }


def run(action: Action, capsule, registry: MemoryRegistry) -> Tuple[Memory, List[Memory], dict]:
    run_dir = MEMORIES_ROOT / "actions" / action.id / "codex_cli"
    ensure_dir(run_dir)

    prompt_path = Path(capsule.prompt_path)
    if not prompt_path.is_absolute():
        prompt_path = MEMORIES_ROOT / capsule.prompt_path
    prompt_text = prompt_path.read_text(encoding="utf-8") if prompt_path.exists() else ""

    artifacts_map = simulate_artifacts(action)
    artifact_memories: List[Memory] = []
    artifact_hashes: List[Dict[str, str]] = []
    for rel_str, body in artifacts_map.items():
        rel_path = Path(rel_str)
        absolute = MEMORIES_ROOT / rel_path
        ensure_dir(absolute.parent)
        write_text(absolute, body)
        artifact_hashes.append({"path": rel_str, "sha256": sha256_text(body)})
        purpose = rel_path.parts[1]
        if purpose == "code.diff":
            title = f"Codex diff for {action.title}"
        elif purpose == "test.log":
            title = f"Test log for {action.title}"
        else:
            title = f"Artifact for {action.title}"
        memory = _artifact_memory(action, purpose=purpose, title=title, rel_path=rel_str)
        registry.register(memory)
        artifact_memories.append(memory)

    exit_code = 0
    summary_text = ("simulated" if OFFLINE or not ENABLE_CODEX_CLI else "codex_cli") + f" run for {action.id}"

    manifest = {
        "action_id": action.id,
        "executor": "codex_cli",
        "worktree_root": str(WORKTREE_ROOT),
        "prompt_sha256": capsule.prompt_sha256,
        "capsule_id": capsule.id,
        "prompt_path": capsule.prompt_path,
        "inputs_hash": sha256_text(prompt_text),
        "artifacts": list(artifacts_map.keys()),
        "artifact_hashes": artifact_hashes,
    }
    manifest_path = run_dir / "manifest.json"
    write_json(manifest_path, manifest)

    env_payload = {
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "offline": OFFLINE,
        "enable_codex_cli": ENABLE_CODEX_CLI,
    }
    env_path = run_dir / "run_env.json"
    write_json(env_path, env_payload)

    updated_action = action.with_status("needs_human", updated_at=utc_now())
    updated_memory = updated_action.to_memory(
        purpose="plan.spec",
        state="active",
        registry_status="registered",
    )

    result = {
        "exit_code": exit_code,
        "summary": summary_text,
        "artifacts": list(artifacts_map.keys()),
    }
    return updated_memory, artifact_memories, result


register_executor("codex_cli", run)

