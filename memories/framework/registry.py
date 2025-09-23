from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

from .ids import generate_ulid
from .models import Memory
from .utils import (
    active_memories_root,
    acquire_lock,
    canonical_dumps,
    ensure_dir,
    sha256_bytes,
    utc_now,
    write_json,
)

__all__ = [
    "MemoryRegistry",
    "RegistryEntry",
]

CHAIN_ZERO = "0" * 64


@dataclass
class RegistryEntry:
    memory: Memory
    chain_sha256: str
    prev_chain_sha256: str
    line_no: int


def _load_line(path: Path, line_no: int, raw: str) -> RegistryEntry:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Malformed registry entry at {path}:{line_no}") from exc
    try:
        memory_payload = data["memory"]
    except KeyError as exc:
        raise ValueError(f"Missing memory payload at {path}:{line_no}") from exc

    memory = Memory.from_dict(memory_payload)
    return RegistryEntry(
        memory=memory,
        chain_sha256=data["chain_sha256"],
        prev_chain_sha256=data.get("prev_chain_sha256", CHAIN_ZERO),
        line_no=line_no,
    )


class MemoryRegistry:
    def __init__(self, root: Path | None = None):
        self.root = root or active_memories_root()
        self.index_path = self.root / "index.jsonl"
        self.lock_path = self.root / "index.jsonl.lock"
        ensure_dir(self.root)
        if not self.index_path.exists():
            self.index_path.write_text("", encoding="utf-8")

    def _iter_entries(self) -> Iterator[RegistryEntry]:
        if not self.index_path.exists():
            return iter(())
        with self.index_path.open("r", encoding="utf-8") as handle:
            for idx, line in enumerate(handle, start=1):
                stripped = line.strip()
                if not stripped:
                    continue
                yield _load_line(self.index_path, idx, stripped)

    def _entries_list(self) -> List[RegistryEntry]:
        return list(self._iter_entries())

    def _latest_entry_by_id(self, memory_id: str) -> Optional[RegistryEntry]:
        for entry in reversed(self._entries_list()):
            if entry.memory.id == memory_id:
                return entry
        return None

    def _latest_entry_by_handle(self, handle: str) -> Optional[RegistryEntry]:
        for entry in reversed(self._entries_list()):
            if entry.memory.handle == handle:
                return entry
        return None

    def register(self, memory: Memory) -> Memory:
        now = utc_now()
        if not memory.created_at:
            memory.created_at = now
        memory.updated_at = now

        latest_entry = self._latest_entry_by_id(memory.id)
        if latest_entry:
            allowed = {
                ("staged", "registered"),
                ("registered", "referenced"),
                ("referenced", "archived"),
            }
            prev_status = latest_entry.memory.registry_status
            next_status = memory.registry_status
            if prev_status != next_status and (prev_status, next_status) not in allowed:
                raise ValueError(
                    f"Invalid registry status transition {prev_status} -> {next_status} for {memory.id}"
                )
            if not memory.handle and latest_entry.memory.handle:
                memory.handle = latest_entry.memory.handle
            if memory.created_at != latest_entry.memory.created_at:
                memory.created_at = latest_entry.memory.created_at
        else:
            if memory.registry_status == "staged":
                memory.registry_status = "registered"

        memory_dict = memory.to_dict()
        canonical = canonical_dumps(memory_dict)

        prev_chain = CHAIN_ZERO
        last_entry = None
        for last_entry in self._iter_entries():
            pass
        if last_entry:
            prev_chain = last_entry.chain_sha256
        payload = f"{prev_chain}\n{canonical}\n"
        chain = sha256_bytes(payload.encode("utf-8"))
        record = {
            "memory": memory_dict,
            "prev_chain_sha256": prev_chain,
            "chain_sha256": chain,
        }

        ensure_dir(self.index_path.parent)
        with acquire_lock(self.lock_path):
            with self.index_path.open("a", encoding="utf-8") as handle:
                handle.write(canonical_dumps(record) + "\n")

        return memory

    def register_artifact_sidecar(self, path: Path, meta: Dict[str, Any]) -> Dict[str, Any]:
        write_json(path, meta)
        return meta

    def query(self, filters: Dict[str, Any], limit: int = 100) -> List[Memory]:
        results: List[Memory] = []
        for entry in self._iter_entries():
            memory = entry.memory
            if self._match(memory, filters):
                results.append(memory)
                if len(results) >= limit:
                    break
        return results

    def latest(self, handle_or_id: str) -> Optional[Memory]:
        entry = self._latest_entry_by_id(handle_or_id)
        if entry:
            return entry.memory
        entry = self._latest_entry_by_handle(handle_or_id)
        if entry:
            return entry.memory
        return None

    def validate_chain(self) -> bool:
        prev = CHAIN_ZERO
        for entry in self._iter_entries():
            canonical = canonical_dumps(entry.memory.to_dict())
            payload = f"{prev}\n{canonical}\n"
            computed = sha256_bytes(payload.encode("utf-8"))
            if computed != entry.chain_sha256:
                raise ValueError(
                    f"Chain mismatch at line {entry.line_no}: expected {entry.chain_sha256}, got {computed}"
                )
            prev = entry.chain_sha256
        return True

    def staged(self) -> List[Memory]:
        return [entry.memory for entry in self._iter_entries() if entry.memory.registry_status == "staged"]

    def orphans(self) -> List[Memory]:
        referenced = {
            entry.memory.id
            for entry in self._iter_entries()
            if entry.memory.registry_status == "referenced"
        }
        return [
            entry.memory
            for entry in self._iter_entries()
            if entry.memory.registry_status == "registered" and entry.memory.id not in referenced
        ]

    def _match(self, memory: Memory, filters: Dict[str, Any]) -> bool:
        for key, expected in filters.items():
            if key == "type" and memory.type != expected:
                return False
            if key == "purpose" and memory.purpose != expected:
                return False
            if key == "tags" and not set(expected).issubset(set(memory.tags)):
                return False
            if key == "handle" and memory.handle != expected:
                return False
            if key == "policy_refs" and not set(expected).issubset(set(memory.metadata.policy_refs)):
                return False
        return True


def bootstrap_truth(registry: MemoryRegistry, *, actor_id: str = "cliff_ai", actor_type: str = "ai") -> Memory:
    root = active_memories_root()
    truth_path = root / "truth" / "cliff_ai.mind.md"
    ensure_dir(truth_path.parent)
    if not truth_path.exists():
        truth_path.write_text("# cliff_ai Mind\n", encoding="utf-8")
    timestamp = utc_now()
    memory = Memory.from_dict(
        {
            "id": generate_ulid(),
            "type": "truth",
            "purpose": "doc.truth",
            "handle": "cliff_ai.truth",
            "title": "cliff_ai.mind",
            "tags": ["truth"],
            "state": "active",
            "registry_status": "staged",
            "relations": {"links": [], "derived_from": [], "produces": []},
            "content": {"path": str(truth_path.relative_to(root))},
            "metadata": {
                "owners": ["steve"],
                "constraints": {},
                "acceptance_criteria": [],
                "visibility": "internal",
                "sensitivity": "low",
                "policy_refs": [],
            },
            "actor": {"actor_id": actor_id, "actor_type": actor_type},
            "created_at": timestamp,
            "updated_at": timestamp,
        }
    )
    return registry.register(memory)
