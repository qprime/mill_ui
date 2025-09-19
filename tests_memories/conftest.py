from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

import pytest

from skills.memory_framework import actions, capsule, policies, registry, timeline
from skills.memory_framework.executors import codex_cli, ops_shell, prose_llm
from skills.memory_framework import utils

MODULES: Iterable[object] = (
    utils,
    registry,
    capsule,
    actions,
    policies,
    timeline,
    prose_llm,
    codex_cli,
    ops_shell,
)

DIRECTORIES = [
    "artifacts/code.diff",
    "artifacts/doc.export",
    "artifacts/test.log",
    "artifacts/ops.runlog",
    "artifacts/cnc.gcode",
    "actions",
    "capsules",
    "decisions",
    "notes",
    "policies",
    "truth",
]


@pytest.fixture(autouse=True)
def _offline_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OFFLINE", "1")
    monkeypatch.setenv("ENABLE_CODEX_CLI", "0")
    monkeypatch.setenv("ENABLE_PANDOC", "0")
    monkeypatch.setenv("ENABLE_FFMPEG", "0")
    monkeypatch.setenv("ACTOR_SIGNING_SECRET", "test-secret")


@pytest.fixture
def tmp_memories(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    for module in MODULES:
        if hasattr(module, "MEMORIES_ROOT"):
            monkeypatch.setattr(module, "MEMORIES_ROOT", tmp_path, raising=False)
    monkeypatch.setattr(utils, "WORKTREE_ROOT", tmp_path, raising=False)
    for item in DIRECTORIES:
        (tmp_path / item).mkdir(parents=True, exist_ok=True)
    (tmp_path / "policies" / "safety.json").write_text(
        '{ "safety_critical_paths": ["skills/memory_framework/*"], "required_tests": ["pytest -q"], "required_signers": ["steve"] }',
        encoding="utf-8",
    )
    (tmp_path / "policies" / "pii.json").write_text(
        '{ "fields": ["ssn", "dob", "email"], "requires_executor": "scrub_executor" }',
        encoding="utf-8",
    )
    (tmp_path / "policies" / "freeze_windows.json").write_text(
        '{ "windows_utc": [], "deny_intents": [] }',
        encoding="utf-8",
    )
    (tmp_path / "truth" / "cliff_ai.mind.md").write_text("# Truth\n\n## Abstract\nBase truth.\n", encoding="utf-8")
    return tmp_path


@pytest.fixture
def memory_registry(tmp_memories: Path) -> registry.MemoryRegistry:
    return registry.MemoryRegistry(root=tmp_memories)

