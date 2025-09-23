from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .brief import build_brief
from .executors import get_executor
from .guardrails import analyze_action
from .ids import generate_ulid
from .models import Action, Actor, Brief as CapsuleModel, Decision, Memory, MemoryContent, MemoryMetadata, Relations
from .policies import PolicyEvaluation, PolicyStore
from .registry import MemoryRegistry
from .signatures import sign_payload, verify_signature
from .utils import active_memories_root, ensure_dir, utc_now, write_text

__all__ = [
    "create_action",
    "auto_check",
    "run_action",
    "approve_action",
    "apply_action",
    "build_brief",
    "get_action",
]

DEFAULT_EXECUTOR = {"name": "prose_llm", "args": {}}
ACTOR_ID = os.getenv("ACTOR_ID", "cliff_ai")
ACTOR_TYPE = os.getenv("ACTOR_TYPE", "ai")
GOD_ACTOR_ID = os.getenv("GOD_ACTOR_ID", "steve")


def _actor(actor_id: str | None = None, actor_type: str | None = None) -> Actor:
    return Actor(actor_id=actor_id or ACTOR_ID, actor_type=actor_type or ACTOR_TYPE)


def _action_constraints(action: Action) -> Dict[str, Any]:
    return dict(action.constraints)


def get_action(registry: MemoryRegistry, action_id: str) -> Action:
    memory = registry.latest(action_id)
    if not memory or memory.type != "action":
        raise KeyError(f"Action {action_id} not found")
    return Action.from_memory(memory)


def create_action(
    registry: MemoryRegistry,
    *,
    title: str,
    intent: str,
    thread: Optional[str] = None,
    truth_ref: Optional[str] = "cliff_ai.truth",
    requirements: Optional[List[str]] = None,
    constraints: Optional[Dict[str, Any]] = None,
    context_scope: Optional[Dict[str, Any]] = None,
    executor: Optional[Dict[str, Any]] = None,
    actor: Optional[Actor] = None,
) -> Memory:
    actor = actor or _actor()
    now = utc_now()
    action = Action(
        id=generate_ulid(),
        title=title,
        intent=intent,
        thread=thread,
        truth_ref=truth_ref,
        requirements=requirements or [],
        constraints=constraints or {},
        context_scope=context_scope or {"include": [], "deny": []},
        executor=executor or DEFAULT_EXECUTOR,
        status="proposed",
        escalation_reasons=[],
        actor=actor,
        created_at=now,
        updated_at=now,
    )
    memory = action.to_memory(purpose="plan.spec", state="draft", registry_status="staged")
    registry.register(memory)
    return memory


def auto_check(
    registry: MemoryRegistry,
    *,
    action_id: str,
    diff_texts: Sequence[str] | None = None,
    context: Dict[str, Any] | None = None,
) -> Tuple[Action, PolicyEvaluation]:
    action = get_action(registry, action_id)
    policy_store = PolicyStore()
    context = context or {}
    combined_context = {
        "paths": context.get("paths") or action.constraints.get("paths", []),
        "visibility": context.get("visibility") or action.constraints.get("visibility", "internal"),
        "sensitivity": context.get("sensitivity") or action.constraints.get("sensitivity", "low"),
    }

    policy_eval = policy_store.evaluate_action(registry, action, context=combined_context)
    guard_report = analyze_action(
        action,
        policy_store=policy_store,
        diff_texts=diff_texts,
        context=combined_context,
    )

    escalations = sorted(
        set(policy_eval.escalation_reasons + guard_report.escalation_reasons)
    )
    new_status = "auto_checked"
    if policy_eval.requires_decision or guard_report.requires_human:
        new_status = "needs_human"
    else:
        new_status = "ready"

    root = active_memories_root()
    new_constraints = _action_constraints(action)
    new_constraints["policy_check_path"] = str(
        policy_eval.path.relative_to(root)
    )
    new_constraints["required_tests"] = guard_report.required_tests
    new_constraints["delta_sloc"] = guard_report.delta_sloc

    updated_action = action.with_status(
        new_status,
        updated_at=utc_now(),
        escalation_reasons=escalations,
        constraints=new_constraints,
    )
    updated_memory = updated_action.to_memory(
        purpose="plan.spec",
        state="active",
        registry_status="registered",
    )
    registry.register(updated_memory)
    return updated_action, policy_eval


def run_action(
    registry: MemoryRegistry,
    *,
    action_id: str,
    brief: CapsuleModel,
) -> Tuple[Action, List[Memory], Dict[str, Any]]:
    action = get_action(registry, action_id)
    executor_name = action.executor.get("name", DEFAULT_EXECUTOR["name"])
    executor = get_executor(executor_name)
    updated_memory, artifacts, result = executor(action, brief, registry)

    updated_action = Action.from_memory(updated_memory)
    new_constraints = dict(updated_action.constraints)
    new_constraints["last_exit_code"] = result.get("exit_code")
    new_constraints["last_summary"] = result.get("summary")
    updated_action = updated_action.with_status(
        updated_action.status,
        updated_at=utc_now(),
        constraints=new_constraints,
    )
    final_memory = updated_action.to_memory(
        purpose="plan.spec",
        state=updated_memory.state,
        registry_status="registered",
    )
    registry.register(final_memory)
    return updated_action, artifacts, result


def approve_action(
    registry: MemoryRegistry,
    *,
    action_id: str,
    approver_id: str,
    reason: str,
) -> Memory:
    action = get_action(registry, action_id)
    timestamp = utc_now()
    approver_actor = Actor(actor_id=approver_id, actor_type="human" if approver_id == GOD_ACTOR_ID else "ai")
    decision_id = generate_ulid()
    payload = {
        "id": decision_id,
        "action_id": action_id,
        "approver": approver_actor.to_dict(),
        "reason": reason,
        "timestamp": timestamp,
        "policy_check_path": action.constraints.get("policy_check_path"),
    }
    signature = sign_payload(payload)
    decision = Decision(
        id=decision_id,
        action_id=action_id,
        approver=approver_actor,
        signature=signature,
        reason=reason,
        timestamp=timestamp,
        policy_check_path=payload["policy_check_path"],
    )
    memory = decision.to_memory(state="active", registry_status="registered", title=f"Decision on {action.title}")
    registry.register(memory)
    return memory


def _decisions_for_action(registry: MemoryRegistry, action_id: str) -> List[Memory]:
    decisions = registry.query({"type": "decision"}, limit=200)
    return [d for d in decisions if d.handle == action_id]


def apply_action(registry: MemoryRegistry, *, action_id: str, actor_id: str | None = None) -> Memory:
    action = get_action(registry, action_id)
    actor_id = actor_id or ACTOR_ID

    if action.status not in {"ready", "needs_human"}:
        raise RuntimeError(f"Action {action_id} not ready to apply (status {action.status})")

    required_tests = action.constraints.get("required_tests", [])
    if required_tests:
        test_logs = [
            memory
            for memory in registry.query({"purpose": "test.log"}, limit=500)
            if memory.relations.thread_of == action.id
        ]
        if not test_logs:
            raise RuntimeError("Required tests missing")

    last_exit = action.constraints.get("last_exit_code")
    if last_exit is None:
        raise RuntimeError("Action has no executor result")
    if last_exit != 0:
        raise RuntimeError(f"Executor exit code {last_exit} indicates failure")

    if action.status == "needs_human":
        decisions = _decisions_for_action(registry, action_id)
        if not decisions:
            raise RuntimeError("Action requires human decision")
        verified = False
        for decision_memory in decisions:
            decision_data = decision_memory.metadata.constraints.get("decision", {})
            signature = decision_data.get("signature", "")
            payload = {k: v for k, v in decision_data.items() if k != "signature"}
            if verify_signature(payload, signature):
                verified = True
                break
        if not verified and actor_id != GOD_ACTOR_ID:
            raise RuntimeError("No valid decision signature found")

    revert_rel = Path("artifacts") / "code.diff" / f"{action.id}.revert.patch"
    root = active_memories_root()
    revert_path = root / revert_rel
    ensure_dir(revert_path.parent)
    revert_body = (
        f"--- revert\n+++ revert\n@@\n-apply\n+revert {action.id}\n"
    )
    write_text(revert_path, revert_body)

    revert_memory = Memory(
        id=generate_ulid(),
        type="artifact",
        purpose="code.diff",
        handle=action.thread,
        title=f"Revert patch for {action.title}",
        tags=["revert"],
        state="done",
        registry_status="staged",
        relations=Relations(thread_of=action.id),
        content=MemoryContent(path=str(revert_rel)),
        metadata=MemoryMetadata(constraints={"kind": "revert"}),
        actor=_actor(actor_id, ACTOR_TYPE),
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    registry.register(revert_memory)

    updated_action = action.with_status("applied", updated_at=utc_now())
    memory = updated_action.to_memory(
        purpose="plan.spec",
        state="done",
        registry_status="registered",
    )
    registry.register(memory)
    return memory
