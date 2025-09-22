from __future__ import annotations

from dataclasses import replace
from typing import Optional, Iterable

from .ids import generate_ulid
from .models import Actor, Memory, MemoryContent, MemoryMetadata, Relations
from .registry import MemoryRegistry
from .utils import utc_now

__all__ = [
    "ensure_chat_session",
    "record_chat_turn",
    "link_produced",
    "add_derivations",
]


def ensure_chat_session(registry: MemoryRegistry, *, chat_id: str, title: Optional[str] = None) -> Memory:
    """
    Ensure a chat session anchor Memory exists for a given chat_id.
    Returns the latest session memory.
    """
    existing = registry.query({"type": "narrative", "purpose": "chat.session", "handle": chat_id}, limit=100)
    if existing:
        return existing[-1]

    stamp = utc_now()
    session = Memory(
        id=generate_ulid(),
        type="narrative",
        purpose="chat.session",
        handle=chat_id,
        title=title or f"Chat session {chat_id}",
        tags=["chat", "session"],
        state="active",
        registry_status="registered",
        relations=Relations(thread_of=None, derived_from=[], produces=[], links=[]),
        content=MemoryContent(bytes=None, path=None, sha256=None),
        metadata=MemoryMetadata(constraints={"chat_id": chat_id}),
        actor=Actor(actor_id="cliff_chat", actor_type="service"),
        created_at=stamp,
        updated_at=stamp,
    )
    return registry.register(session)


def record_chat_turn(
    registry: MemoryRegistry,
    *,
    chat_id: str,
    user_input: str,
    response: str,
    distilled: str,
    model: Optional[str] = None,
    sidecar_path: Optional[str] = None,
    persona: Optional[str] = None,
) -> Memory:
    """
    Register a chat turn in the ledger and link it under the chat session.
    Adds a 'produces' edge on the session to enable forward traversal.
    """
    session = ensure_chat_session(registry, chat_id=chat_id)
    stamp = utc_now()

    summary = (
        f"🧑 {user_input.strip()}\n"
        f"🤖 {response.strip()}\n"
    )
    turn = Memory(
        id=generate_ulid(),
        type="narrative",
        purpose="chat.turn",
        handle=chat_id,
        title=f"Chat turn {stamp}",
        tags=["chat", "turn"],
        state="active",
        registry_status="registered",
        relations=Relations(thread_of=session.id, derived_from=[], produces=[], links=[]),
        content=MemoryContent(bytes=summary),
        metadata=MemoryMetadata(constraints={
            "chat_id": chat_id,
            "model": model or "",
            "distilled": distilled,
            "sidecar_path": sidecar_path,
            "persona": persona or "",
            "input": user_input,
            "response": response,
        }),
        actor=Actor(actor_id="cliff_chat", actor_type="service"),
        created_at=stamp,
        updated_at=stamp,
    )
    turn = registry.register(turn)

    # Update session to reflect produced turn
    latest_session = registry.latest(session.id) or session
    updated = replace(latest_session)
    produced = list(updated.relations.produces)
    if turn.id not in produced:
        produced.append(turn.id)
    updated.relations.produces = produced
    updated.updated_at = utc_now()
    registry.register(updated)

    return turn


def link_produced(registry: MemoryRegistry, *, parent_id: str, child_id: str) -> Memory:
    """
    Append a child edge to parent's relations.produces.
    Returns the updated parent memory as recorded in the registry.
    """
    parent = registry.latest(parent_id)
    if not parent:
        raise KeyError(f"Parent memory {parent_id} not found")
    updated = replace(parent)
    produced = list(updated.relations.produces)
    if child_id not in produced:
        produced.append(child_id)
    updated.relations.produces = produced
    updated.updated_at = utc_now()
    return registry.register(updated)


def add_derivations(registry: MemoryRegistry, *, child_id: str, sources: Iterable[str]) -> Memory:
    """
    Add source memory IDs to child's relations.derived_from and re-register.
    Returns the updated child memory.
    """
    child = registry.latest(child_id)
    if not child:
        raise KeyError(f"Child memory {child_id} not found")
    updated = replace(child)
    derived = set(updated.relations.derived_from)
    derived.update([s for s in sources if s])
    updated.relations.derived_from = list(derived)
    updated.updated_at = utc_now()
    return registry.register(updated)
