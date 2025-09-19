from __future__ import annotations

import argparse
import json
import os
from typing import Any, Dict

from skills.memory_framework.actions import (
    apply_action,
    approve_action,
    build_capsule,
    create_action,
    get_action,
    run_action,
)
from skills.memory_framework.ids import generate_ulid
from skills.memory_framework.models import Action, Actor, Memory, MemoryContent, MemoryMetadata, Relations
from skills.memory_framework.registry import MemoryRegistry
from skills.memory_framework.timeline import build_timeline
from skills.memory_framework.utils import utc_now

__all__ = ["api"]

ACTOR_ID = os.getenv("ACTOR_ID", "cliff_ai")
ACTOR_TYPE = os.getenv("ACTOR_TYPE", "ai")


def _registry() -> MemoryRegistry:
    return MemoryRegistry()


def _actor() -> Actor:
    return Actor(actor_id=ACTOR_ID, actor_type=ACTOR_TYPE)


def _print(data: Dict[str, Any]) -> None:
    print(json.dumps(data, indent=2))


def _new_narrative(args: argparse.Namespace) -> Dict[str, Any]:
    reg = _registry()
    timestamp = utc_now()
    memory = Memory(
        id=generate_ulid(),
        type="narrative",
        purpose="doc.note",
        handle=args.handle,
        title=args.title or args.handle,
        tags=list(args.tags or []),
        state="active",
        registry_status="staged",
        relations=Relations(),
        content=MemoryContent(bytes=""),
        metadata=MemoryMetadata(constraints={}),
        actor=_actor(),
        created_at=timestamp,
        updated_at=timestamp,
    )
    reg.register(memory)
    return {"id": memory.id, "handle": memory.handle}


def _action_create(args: argparse.Namespace) -> Dict[str, Any]:
    reg = _registry()
    memory = create_action(
        reg,
        title=args.title,
        intent=args.intent,
        thread=args.thread,
        requirements=args.requirement or [],
    )
    return Action.from_memory(memory).to_dict()


def _capsule_build(args: argparse.Namespace) -> Dict[str, Any]:
    reg = _registry()
    action = get_action(reg, args.action)
    result = build_capsule(action, reg)
    return {"capsule_id": result.capsule.id, "prompt_path": result.capsule.prompt_path}


def _run(args: argparse.Namespace) -> Dict[str, Any]:
    reg = _registry()
    action = get_action(reg, args.action)
    capsule_result = build_capsule(action, reg)
    updated_action, artifacts, result = run_action(reg, action_id=action.id, capsule=capsule_result.capsule)
    return {
        "action": updated_action.to_dict(),
        "artifacts": [artifact.content.path for artifact in artifacts],
        "result": result,
    }


def _approve(args: argparse.Namespace) -> Dict[str, Any]:
    reg = _registry()
    decision_memory = approve_action(
        reg,
        action_id=args.action,
        approver_id=args.approver,
        reason=args.reason,
    )
    return decision_memory.metadata.constraints.get("decision", {})


def _apply(args: argparse.Namespace) -> Dict[str, Any]:
    reg = _registry()
    applied_memory = apply_action(reg, action_id=args.action)
    return Action.from_memory(applied_memory).to_dict()


def _timeline(args: argparse.Namespace) -> Dict[str, Any]:
    reg = _registry()
    events = build_timeline(reg, args.handle)
    return {"handle": args.handle, "events": events}


def _registry_validate(_: argparse.Namespace) -> Dict[str, Any]:
    reg = _registry()
    reg.validate_chain()
    return {"status": "ok"}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ltp ctx")
    sub = parser.add_subparsers(dest="command", required=True)

    new_narrative = sub.add_parser("new-narrative")
    new_narrative.add_argument("--handle", required=True)
    new_narrative.add_argument("--title", default="")
    new_narrative.add_argument("--tags", nargs="*", default=[])

    action_cmd = sub.add_parser("action")
    action_sub = action_cmd.add_subparsers(dest="action_cmd", required=True)
    action_create = action_sub.add_parser("create")
    action_create.add_argument("--title", required=True)
    action_create.add_argument("--intent", required=True)
    action_create.add_argument("--thread")
    action_create.add_argument("--requirement", action="append")

    capsule_cmd = sub.add_parser("capsule")
    capsule_sub = capsule_cmd.add_subparsers(dest="capsule_cmd", required=True)
    capsule_build = capsule_sub.add_parser("build")
    capsule_build.add_argument("--action", required=True)

    run_cmd = sub.add_parser("run")
    run_cmd.add_argument("--action", required=True)

    approve_cmd = sub.add_parser("approve")
    approve_cmd.add_argument("--action", required=True)
    approve_cmd.add_argument("--reason", required=True)
    approve_cmd.add_argument("--approver", default="steve")

    apply_cmd = sub.add_parser("apply")
    apply_cmd.add_argument("--action", required=True)

    timeline_cmd = sub.add_parser("timeline")
    timeline_cmd.add_argument("--handle", required=True)

    sub.add_parser("registry-validate")

    return parser


def api(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)

    if args.command == "new-narrative":
        result = _new_narrative(args)
    elif args.command == "action" and args.action_cmd == "create":
        result = _action_create(args)
    elif args.command == "capsule" and args.capsule_cmd == "build":
        result = _capsule_build(args)
    elif args.command == "run":
        result = _run(args)
    elif args.command == "approve":
        result = _approve(args)
    elif args.command == "apply":
        result = _apply(args)
    elif args.command == "timeline":
        result = _timeline(args)
    elif args.command == "registry-validate":
        result = _registry_validate(args)
    else:
        parser.error("unsupported command")
        return 1

    _print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(api())

