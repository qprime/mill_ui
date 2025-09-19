from __future__ import annotations

from skills.memory_framework import actions
from skills.memory_framework.ids import generate_ulid
from skills.memory_framework.models import Action, Actor, Memory, MemoryContent, MemoryMetadata, Relations
from skills.memory_framework.timeline import build_timeline
from skills.memory_framework.utils import utc_now


def test_timeline_orders_events(memory_registry) -> None:
    actor = Actor(actor_id="tester", actor_type="ai")
    note_memory = Memory(
        id=generate_ulid(),
        type="note",
        purpose="doc.note",
        handle="thread-1",
        title="Kickoff",
        tags=["note"],
        state="active",
        registry_status="staged",
        relations=Relations(),
        content=MemoryContent(bytes="Start"),
        metadata=MemoryMetadata(constraints={}),
        actor=actor,
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    memory_registry.register(note_memory)

    action_memory = actions.create_action(
        memory_registry,
        title="Timeline Action",
        intent="doc.coauthor",
        thread="thread-1",
        requirements=["Write section"],
    )
    action = Action.from_memory(action_memory)
    actions.auto_check(memory_registry, action_id=action.id)
    action = actions.get_action(memory_registry, action.id)
    capsule_result = actions.build_capsule(action, memory_registry)
    actions.run_action(memory_registry, action_id=action.id, capsule=capsule_result.capsule)

    events = build_timeline(memory_registry, "thread-1")
    ids = [event["id"] for event in events]
    assert note_memory.id in ids
    assert action.id in ids
    assert ids.index(note_memory.id) < ids.index(action.id)

