from __future__ import annotations

from pathlib import Path

import pytest

from memories.framework.ids import generate_ulid
from memories.framework.models import Actor, Memory, MemoryContent, MemoryMetadata, Relations
from memories.framework.registry import MemoryRegistry
from memories.framework.utils import utc_now


def _memory(title: str, actor: Actor) -> Memory:
    stamp = utc_now()
    return Memory(
        id=generate_ulid(),
        type="note",
        purpose="doc.note",
        handle=None,
        title=title,
        tags=["test"],
        state="active",
        registry_status="staged",
        relations=Relations(),
        content=MemoryContent(bytes="memo"),
        metadata=MemoryMetadata(constraints={}),
        actor=actor,
        created_at=stamp,
        updated_at=stamp,
    )


def test_hash_chain_validation(memory_registry: MemoryRegistry, tmp_memories: Path) -> None:
    actor = Actor(actor_id="tester", actor_type="ai")
    first = _memory("one", actor)
    second = _memory("two", actor)
    memory_registry.register(first)
    memory_registry.register(second)
    assert memory_registry.validate_chain()

    index_path = tmp_memories / "index.jsonl"
    lines = index_path.read_text(encoding="utf-8").splitlines()
    assert lines
    tampered = lines[0].replace("memo", "tamper")
    index_path.write_text("\n".join([tampered, *lines[1:]]) + "\n", encoding="utf-8")

    with pytest.raises(ValueError):
        memory_registry.validate_chain()
