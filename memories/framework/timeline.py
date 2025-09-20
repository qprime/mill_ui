from __future__ import annotations

from typing import Dict, List

from .models import Action
from .registry import MemoryRegistry

__all__ = ["build_timeline"]


def build_timeline(registry: MemoryRegistry, handle: str) -> List[Dict[str, str]]:
    entries = registry.query({}, limit=2000)
    events = []
    for memory in entries:
        related = memory.relations.thread_of
        if memory.handle == handle or related == handle:
            event = {
                "id": memory.id,
                "type": memory.type,
                "title": memory.title,
                "purpose": memory.purpose,
                "created_at": memory.created_at,
                "registry_status": memory.registry_status,
            }
            if memory.type == "action":
                action = Action.from_memory(memory)
                event["status"] = action.status
                event["intent"] = action.intent
            events.append(event)
    events.sort(key=lambda item: (item["created_at"], item["id"]))
    return events

