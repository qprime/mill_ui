from __future__ import annotations

from pathlib import Path

from . import actions, brief, executors, guardrails, policies, registry, timeline
from .ids import generate_ulid, ulid_timestamp_ms
from .models import (
    Action,
    Actor,
    ArtifactMeta,
    Brief,
    Decision,
    Memory,
    MemoryMetadata,
    MemoryType,
    RegistryStatus,
)
from .registry import MemoryRegistry, RegistryEntry

__all__ = [
    "Action",
    "Actor",
    "ArtifactMeta",
    "Brief",
    "Decision",
    "Memory",
    "MemoryMetadata",
    "MemoryRegistry",
    "MemoryType",
    "RegistryEntry",
    "RegistryStatus",
    "actions",
    "brief",
    "executors",
    "generate_ulid",
    "guardrails",
    "policies",
    "registry",
    "timeline",
    "ulid_timestamp_ms",
]


def registry_from_env(root: Path | None = None) -> MemoryRegistry:
    base = root or Path("memories").resolve()
    return MemoryRegistry(base)
