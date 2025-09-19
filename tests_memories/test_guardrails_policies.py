from __future__ import annotations

from skills.memory_framework import actions
from skills.memory_framework.models import Action


def test_safety_guardrail_requires_decision(memory_registry) -> None:
    memory = actions.create_action(
        memory_registry,
        title="Guard safety",
        intent="code.change_request",
        requirements=["Touch safety path"],
        constraints={"paths": ["skills/memory_framework/core.py"]},
        executor={"name": "codex_cli", "args": {}},
    )
    action = Action.from_memory(memory)
    updated_action, policy_eval = actions.auto_check(
        memory_registry,
        action_id=action.id,
        context={"paths": ["skills/memory_framework/core.py"], "sensitivity": "safety"},
    )
    assert updated_action.status == "needs_human"
    assert "policy_required" in updated_action.escalation_reasons
    assert "pytest -q" in updated_action.constraints.get("required_tests", [])
    assert policy_eval.requires_decision


def test_pii_policy(memory_registry) -> None:
    memory = actions.create_action(
        memory_registry,
        title="Collect email",
        intent="doc.coauthor",
        requirements=["request email"],
    )
    action = Action.from_memory(memory)
    updated_action, policy_eval = actions.auto_check(memory_registry, action_id=action.id)
    if policy_eval.checks["pii"]["detected"]:
        assert updated_action.status == "needs_human"


def test_doc_export_requires_decision(memory_registry) -> None:
    memory = actions.create_action(
        memory_registry,
        title="External export",
        intent="doc.export",
        requirements=["Ship PDF"],
        constraints={"visibility": "external"},
        executor={"name": "ops_shell", "args": {}},
    )
    action = Action.from_memory(memory)
    updated_action, policy_eval = actions.auto_check(
        memory_registry,
        action_id=action.id,
        context={"visibility": "external"},
    )
    assert updated_action.status == "needs_human"
    assert "policy_required" in updated_action.escalation_reasons
    assert policy_eval.requires_decision

