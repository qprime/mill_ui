from __future__ import annotations

import platform
from pathlib import Path
from typing import Dict, List, Tuple

from ..ids import generate_ulid
from ..models import Action, Memory, MemoryContent, MemoryMetadata, Relations
from ..registry import MemoryRegistry
from ..utils import MEMORIES_ROOT, OFFLINE, ensure_dir, sha256_text, utc_now, write_json, write_text
from . import register_executor

__all__ = ["run", "summarize_for_capsule", "simulate_artifacts"]


def summarize_for_capsule(text: str, max_chars: int) -> str:
    if not text:
        return ""
    header = "SUMMARY\n"
    chunks: List[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        chunks.append(stripped)
        candidate = header + " ".join(chunks)
        if len(candidate) >= max_chars:
            break
    summary = header + " ".join(chunks)
    if len(summary) > max_chars:
        if max_chars <= 3:
            summary = summary[: max_chars]
        else:
            summary = summary[: max_chars - 3] + "..."
    return summary


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
        relations=Relations(thread_of=action.id, derived_from=[action.truth_ref] if action.truth_ref else []),
        content=MemoryContent(path=rel_path),
        metadata=MemoryMetadata(constraints={}, acceptance_criteria=[]),
        actor=action.actor,
        created_at=stamp,
        updated_at=stamp,
    )


def simulate_artifacts(action: Action) -> Dict[str, str]:
    if OFFLINE:
        new_content = f"OFFLINE prose output for action {action.id}\n"
    else:
        new_content = f"ONLINE prose output for {action.id}\n"
    diff_body = (
        f"--- original.md\n"
        f"+++ updated.md\n"
        f"@@\n-<original>\n+{new_content.strip()}\n"
    )
    rel_path = f"artifacts/code.diff/{action.id}.patch"
    return {rel_path: diff_body}


def run(action: Action, capsule, registry: MemoryRegistry) -> Tuple[Memory, List[Memory], dict]:
    run_dir = MEMORIES_ROOT / "actions" / action.id
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
        purpose = rel_path.parts[1] if len(rel_path.parts) > 1 else "artifact"
        if purpose == "code.diff":
            title = f"Diff for {action.title}"
        elif purpose == "test.log":
            title = f"Test log for {action.title}"
        else:
            title = f"Artifact for {action.title}"
        memory = _artifact_memory(action, purpose=purpose, title=title, rel_path=rel_str)
        registry.register(memory)
        artifact_memories.append(memory)

    summary = ("offline" if OFFLINE else "online") + f" prose update {action.id}"

    manifest = {
        "action_id": action.id,
        "executor": "prose_llm",
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


register_executor("prose_llm", run)

