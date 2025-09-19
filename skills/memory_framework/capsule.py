from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

from .executors.prose_llm import summarize_for_capsule
from .ids import generate_ulid
from .models import Action, Actor, Capsule as CapsuleModel, Memory, MemoryContent, MemoryMetadata, Relations
from .registry import MemoryRegistry
from .utils import MEMORIES_ROOT, WORKTREE_ROOT, ensure_dir, read_text, sha256_text, strip_comments, trim_chars, utc_now, write_text

__all__ = ["build_capsule"]

MAX_NOTES = 3
DEFAULT_MAX_CHARS = 8000


@dataclass
class CapsuleBuildResult:
    capsule: CapsuleModel
    memory: Memory


def _load_truth_section(truth_path: Path, sections: List[str]) -> Dict[str, str]:
    if not truth_path.exists():
        return {}
    text = read_text(truth_path)
    if not sections:
        return {"full": text}
    sections_dict: Dict[str, str] = {}
    lines = text.splitlines()
    current = None
    buffer: List[str] = []
    for line in lines:
        if line.startswith("#"):
            if current and buffer:
                sections_dict[current] = "\n".join(buffer).strip()
            current = line.lstrip("# ")
            buffer = []
        else:
            buffer.append(line)
    if current and buffer:
        sections_dict[current] = "\n".join(buffer).strip()
    return {k: v for k, v in sections_dict.items() if k in sections}


def _select_notes(registry: MemoryRegistry, thread: str | None) -> List[str]:
    filters = {"type": "note"}
    notes = registry.query(filters, limit=50)
    filtered = [note for note in notes if thread is None or note.handle == thread]
    if len(filtered) <= MAX_NOTES:
        return [note.content.bytes or note.content.path or note.title for note in filtered]
    tail = filtered[-MAX_NOTES:]
    return [note.content.bytes or note.content.path or note.title for note in tail]


def _collect_files(includes: List[Any], drops: List[Dict[str, Any]], max_chars: int) -> Dict[str, str]:
    collected: Dict[str, str] = {}
    for item in includes:
        if isinstance(item, dict):
            path = item.get("path")
        else:
            path = str(item)
        if not path:
            continue
        file_path = (WORKTREE_ROOT / path).resolve()
        if not file_path.exists():
            drops.append({"item": path, "reason": "missing"})
            continue
        text = read_text(file_path)
        stripped = strip_comments(file_path, text)
        collected[path] = stripped
    return collected


def build_capsule(action: Action, registry: MemoryRegistry, *, actor: Actor | None = None, max_chars: int | None = None) -> CapsuleBuildResult:
    actor = actor or action.actor
    max_chars = max_chars or action.constraints.get("max_chars", DEFAULT_MAX_CHARS)
    drops: List[Dict[str, Any]] = []

    truth_memory = registry.latest(action.truth_ref or "cliff_ai.truth")
    if truth_memory and truth_memory.content.path:
        truth_path = (MEMORIES_ROOT / truth_memory.content.path).resolve()
    else:
        truth_path = MEMORIES_ROOT / "truth" / "cliff_ai.mind.md"
    sections = action.constraints.get("sections", [])
    truth_sections = _load_truth_section(truth_path, sections)
    if not truth_sections and truth_path.exists():
        truth_sections = {"full": read_text(truth_path)}

    notes = _select_notes(registry, action.thread)
    if len(notes) > MAX_NOTES:
        drops.append({"item": "notes", "reason": "trim", "removed": len(notes) - MAX_NOTES})
        notes = notes[-MAX_NOTES:]

    includes = action.context_scope.get("include", [])
    files = _collect_files(includes, drops, max_chars)

    acceptance = action.constraints.get("acceptance", [])

    inputs = {
        "truth_sections": truth_sections,
        "recent_notes": notes,
        "selected_files": files,
        "constraints": action.constraints,
        "acceptance_criteria": acceptance,
    }

    prompt_parts: List[str] = []
    prompt_parts.append(f"Action: {action.title} ({action.intent})")
    prompt_parts.append("Requirements:")
    for requirement in action.requirements:
        prompt_parts.append(f"- {requirement}")
    prompt_parts.append("\nTruth Context:")
    for key, value in truth_sections.items():
        prompt_parts.append(f"## {key}\n{value}\n")
    if files:
        prompt_parts.append("\nSelected Files:")
        for path, contents in files.items():
            prompt_parts.append(f"### {path}\n{contents}\n")
    if notes:
        prompt_parts.append("\nRecent Notes:")
        for note in notes:
            prompt_parts.append(f"- {note}")
    if acceptance:
        prompt_parts.append("\nAcceptance Criteria:")
        for item in acceptance:
            prompt_parts.append(f"- {item}")

    prompt_text = "\n".join(prompt_parts)

    if len(prompt_text) > max_chars:
        prompt_text = summarize_for_capsule(prompt_text, max_chars)
        if len(prompt_text) > max_chars:
            prompt_text = trim_chars(prompt_text, max_chars)
        drops.append({"item": "prompt", "reason": "summarize", "max_chars": max_chars})

    capsule_id = generate_ulid()
    capsule_dir = MEMORIES_ROOT / "capsules" / capsule_id
    ensure_dir(capsule_dir)
    prompt_path = capsule_dir / "prompt.txt"
    write_text(prompt_path, prompt_text)
    prompt_sha = sha256_text(prompt_text)

    capsule_model = CapsuleModel(
        id=capsule_id,
        inputs=inputs,
        budgets={"max_chars": max_chars},
        drops=drops,
        prompt_path=str(prompt_path.relative_to(MEMORIES_ROOT)),
        prompt_sha256=prompt_sha,
        timestamp=utc_now(),
    )

    stamp = utc_now()
    memory = capsule_model.to_memory(
        actor=actor,
        title=f"Capsule for {action.title}",
        registry_status="registered",
        state="active",
        created_at=stamp,
        updated_at=stamp,
    )
    registry.register(memory)

    return CapsuleBuildResult(capsule=capsule_model, memory=memory)

