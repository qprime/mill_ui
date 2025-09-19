from __future__ import annotations

from pathlib import Path

from skills.memory_framework import actions
from skills.memory_framework.models import Action
from skills.memory_framework.utils import utc_now


def test_action_flow_to_apply(memory_registry, tmp_memories: Path) -> None:
    memory = actions.create_action(
        memory_registry,
        title="Lifecycle",
        intent="doc.coauthor",
        truth_ref="cliff_ai.truth",
        requirements=["Write abstract"],
    )
    action = Action.from_memory(memory)
    actions.auto_check(memory_registry, action_id=action.id)
    action = actions.get_action(memory_registry, action.id)
    capsule_result = actions.build_capsule(action, memory_registry)
    updated_action, artifacts, result = actions.run_action(
        memory_registry, action_id=action.id, capsule=capsule_result.capsule
    )
    assert updated_action.status in {"ready", "needs_human"}
    applied_memory = actions.apply_action(memory_registry, action_id=action.id)
    revert_path = tmp_memories / "artifacts" / "code.diff" / f"{action.id}.revert.patch"
    assert revert_path.exists()
    assert Action.from_memory(applied_memory).status == "applied"


def test_apply_requires_successful_exit(memory_registry) -> None:
    memory = actions.create_action(
        memory_registry,
        title="Failure Exit",
        intent="doc.coauthor",
        truth_ref="cliff_ai.truth",
        requirements=["Write"],
    )
    action = Action.from_memory(memory)
    actions.auto_check(memory_registry, action_id=action.id)
    action = actions.get_action(memory_registry, action.id)
    capsule_result = actions.build_capsule(action, memory_registry)
    actions.run_action(memory_registry, action_id=action.id, capsule=capsule_result.capsule)

    action = actions.get_action(memory_registry, action.id)
    constraints = dict(action.constraints)
    constraints["last_exit_code"] = 1
    faulty = action.with_status(action.status, updated_at=utc_now(), constraints=constraints)
    memory_registry.register(
        faulty.to_memory(purpose="plan.spec", state="active", registry_status="registered")
    )

    try:
        actions.apply_action(memory_registry, action_id=action.id)
    except RuntimeError as exc:
        assert "exit code" in str(exc)
    else:
        raise AssertionError("apply_action should fail when exit code is non-zero")
