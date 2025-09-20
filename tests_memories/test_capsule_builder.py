from __future__ import annotations

from pathlib import Path

from skills.memory_framework import actions
from skills.memory_framework.models import Action


def test_brief_respects_budgets(memory_registry, tmp_memories: Path) -> None:
    action_memory = actions.create_action(
        memory_registry,
        title="Short brief",
        intent="doc.coauthor",
        truth_ref="cliff_ai.truth",
        requirements=["Summarise abstract"],
        constraints={"sections": ["Abstract"], "max_chars": 80, "acceptance": ["Clear"]},
    )
    action = Action.from_memory(action_memory)
    result = actions.build_brief(action, memory_registry)
    prompt_path = tmp_memories / result.brief.prompt_path
    prompt_text = prompt_path.read_text(encoding="utf-8")
    assert len(prompt_text) <= 80
    assert any(drop.get("reason") for drop in result.brief.drops or [{}])
    assert "Abstract" in prompt_text
