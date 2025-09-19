# name: action_items.py
# path: skills/living_truth_partner/action_items.py
# role: Manage Living Truth Partner action items list
# deps: json, typing, skills.living_truth_partner.project_store
# inputs: ProjectStore, updates
# outputs: load and update helpers

from __future__ import annotations

import json
from typing import Dict, List

from skills.living_truth_partner.project_store import ProjectStore

__all__ = ["load", "set_state", "append"]


def load(store: ProjectStore) -> List[Dict[str, object]]:
    if not store.action_items_path.exists():
        return []
    data = json.loads(store.action_items_path.read_text(encoding="utf-8"))
    return data.get("action_items", [])


def set_state(store: ProjectStore, index: int, done: bool) -> List[Dict[str, object]]:
    items = load(store)
    if 0 <= index < len(items):
        items[index]["done"] = bool(done)
    store.action_items_path.write_text(json.dumps({"action_items": items}, indent=2), encoding="utf-8")
    return items


def append(store: ProjectStore, title: str) -> List[Dict[str, object]]:
    items = load(store)
    items.append({"title": title, "done": False})
    store.action_items_path.write_text(json.dumps({"action_items": items}, indent=2), encoding="utf-8")
    return items
