from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from .actions import (
    apply_action,
    approve_action,
    auto_check,
    build_capsule,
    create_action,
    run_action,
)
from .ids import generate_ulid
from .models import Action, Actor, Memory, MemoryContent, MemoryMetadata, Relations
from .registry import MemoryRegistry, bootstrap_truth
from .utils import MEMORIES_ROOT, ensure_dir, utc_now

__all__ = ["acceptance_demo"]


@dataclass
class AcceptanceResult:
    actions: List[str]
    artifacts: List[str]


def _register_narrative(registry: MemoryRegistry, handle: str, title: str, actor: Actor) -> Memory:
    narrative_id = generate_ulid()
    timestamp = utc_now()
    memory = Memory(
        id=narrative_id,
        type="narrative",
        purpose="doc.note",
        handle=handle,
        title=title,
        tags=["narrative"],
        state="active",
        registry_status="staged",
        relations=Relations(),
        content=MemoryContent(bytes="Seed narrative context"),
        metadata=MemoryMetadata(constraints={}),
        actor=actor,
        created_at=timestamp,
        updated_at=timestamp,
    )
    registry.register(memory)
    return memory


def acceptance_demo(registry: MemoryRegistry | None = None) -> AcceptanceResult:
    registry = registry or MemoryRegistry()
    actor = Actor(actor_id="cliff_ai", actor_type="ai")
    bootstrap_truth(registry)
    _register_narrative(registry, "revolutionary-context-engine", "Revolutionary Context Engine", actor)

    # Step 1: doc coauthor action
    doc_action_memory = create_action(
        registry,
        title="Draft abstract",
        intent="doc.coauthor",
        thread="revolutionary-context-engine",
        truth_ref="cliff_ai.truth",
        requirements=["Draft abstract section"],
        constraints={"sections": ["cliff_ai Mind"]},
    )
    doc_action_id = doc_action_memory.id
    auto_check(registry, action_id=doc_action_id)
    latest_doc_memory = registry.latest(doc_action_id)
    doc_action = Action.from_memory(latest_doc_memory) if latest_doc_memory else Action.from_memory(doc_action_memory)
    capsule_result = build_capsule(doc_action, registry, actor=actor)
    run_action(registry, action_id=doc_action_id, capsule=capsule_result.capsule)

    # Step 2: code change request hitting safety path
    code_action_memory = create_action(
        registry,
        title="Patch memory manager",
        intent="code.change_request",
        thread="revolutionary-context-engine",
        truth_ref="cliff_ai.truth",
        requirements=["Add guard to memory manager"],
        constraints={"paths": ["skills/memory_framework/critical.py"]},
        executor={"name": "codex_cli", "args": {}},
    )
    code_action_id = code_action_memory.id
    auto_check(
        registry,
        action_id=code_action_id,
        context={"paths": ["skills/memory_framework/critical.py"], "sensitivity": "safety"},
    )
    latest_code_memory = registry.latest(code_action_id)
    code_action = Action.from_memory(latest_code_memory) if latest_code_memory else Action.from_memory(code_action_memory)
    capsule_code = build_capsule(code_action, registry, actor=actor)
    run_action(registry, action_id=code_action_id, capsule=capsule_code.capsule)
    approve_action(registry, action_id=code_action_id, approver_id="steve", reason="Safety reviewed")
    apply_action(registry, action_id=code_action_id, actor_id="steve")

    # Step 3: doc export requiring decision
    export_action_memory = create_action(
        registry,
        title="Export PDF",
        intent="doc.export",
        thread="revolutionary-context-engine",
        requirements=["Produce PDF"],
        constraints={"visibility": "external"},
        executor={"name": "ops_shell", "args": {"command": "export"}},
    )
    export_action_id = export_action_memory.id
    auto_check(registry, action_id=export_action_id, context={"visibility": "external"})
    latest_export_memory = registry.latest(export_action_id)
    export_action = Action.from_memory(latest_export_memory) if latest_export_memory else Action.from_memory(export_action_memory)
    capsule_export = build_capsule(export_action, registry, actor=actor)
    run_action(registry, action_id=export_action_id, capsule=capsule_export.capsule)
    approve_action(registry, action_id=export_action_id, approver_id="steve", reason="External OK")

    return AcceptanceResult(
        actions=[doc_action_id, code_action_id, export_action_id],
        artifacts=[],
    )

