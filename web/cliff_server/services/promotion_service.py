from __future__ import annotations

import textwrap
import uuid
from dataclasses import dataclass
from typing import Iterable, List, Optional

from ace_control import Brief, BriefPlanPreference, Mode, RunManager
from memories.framework import MemoryRegistry
from memories.framework.actions import create_action, build_brief
from memories.framework.ids import generate_ulid
from memories.framework.models import Action, Actor, Memory, MemoryContent, MemoryMetadata, Relations
from memories.framework.threading import add_derivations, ensure_chat_session, link_produced
from memories.framework.utils import utc_now
from memories.task_manager import TASKS_DIR, create_task
from skills.living_truth_partner.config import Config as LTPConfig
from skills.living_truth_partner.project_store import ProjectStore

from pathlib import Path

RUN_MANAGER = RunManager()
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONVERSATION_LIMIT = 10


@dataclass
class TurnPayload:
    memory_id: Optional[str]
    user_input: str
    response: str
    distilled: str
    persona: str
    model: str


def promote(
    *,
    action: str,
    chat_id: str,
    persona: str,
    scope: str,
    turn_ids: Optional[List[str]] = None,
    fallback_turn: Optional[dict] = None,
    fallback_turns: Optional[List[dict]] = None,
    limit: Optional[int] = None,
) -> dict:
    registry = MemoryRegistry()
    session_memory = ensure_chat_session(registry, chat_id=chat_id)

    turns = _resolve_turns(
        registry,
        chat_id=chat_id,
        turn_ids=turn_ids,
        fallback_turn=fallback_turn,
        fallback_turns=fallback_turns,
        limit=limit,
    )

    if not turns:
        raise ValueError("No chat turns available for promotion")

    if action == "ideate":
        return _promote_run(
            mode=Mode.IDEATE,
            tag="promotion:ideate",
            chat_id=chat_id,
            persona=persona,
            turns=turns,
        )
    if action == "operate":
        return _promote_run(
            mode=Mode.OPERATE,
            tag="promotion:operate",
            chat_id=chat_id,
            persona=persona,
            turns=turns,
        )
    if action == "build":
        return _promote_build(
            registry=registry,
            session=session_memory,
            chat_id=chat_id,
            persona=persona,
            turns=turns,
            scope=scope,
        )
    if action == "task":
        return _promote_task(
            registry=registry,
            session=session_memory,
            chat_id=chat_id,
            persona=persona,
            turns=turns,
            scope=scope,
        )
    if action == "document":
        return _promote_document(
            registry=registry,
            session=session_memory,
            chat_id=chat_id,
            persona=persona,
            turns=turns,
            scope=scope,
        )
    if action == "chat":
        return _promote_chat(chat_id=chat_id, persona=persona, turns=turns)

    raise ValueError(f"Unsupported promotion action '{action}'")


def _resolve_turns(
    registry: MemoryRegistry,
    *,
    chat_id: str,
    turn_ids: Optional[Iterable[str]] = None,
    fallback_turn: Optional[dict] = None,
    fallback_turns: Optional[List[dict]] = None,
    limit: Optional[int] = None,
) -> List[TurnPayload]:
    fallback_map = {}
    if fallback_turn:
        fallback_map[fallback_turn.get("turn_id") or ""] = _normalize_fallback(fallback_turn)
    for item in fallback_turns or []:
        key = item.get("turn_id") or ""
        fallback_map[key] = _normalize_fallback(item)

    turns: List[TurnPayload] = []

    if turn_ids:
        for turn_id in turn_ids:
            memory = registry.latest(turn_id) if turn_id else None
            if memory and memory.purpose == "chat.turn":
                turns.append(_memory_to_turn(memory))
            elif turn_id in fallback_map:
                turns.append(fallback_map[turn_id])
        if not turns and fallback_map:
            turns = list(fallback_map.values())
        return turns

    memories = registry.query({"purpose": "chat.turn", "handle": chat_id}, limit=500)
    if limit:
        try:
            numeric_limit = max(int(limit), 1)
        except (ValueError, TypeError):
            numeric_limit = DEFAULT_CONVERSATION_LIMIT
        memories = memories[-numeric_limit:]
    elif DEFAULT_CONVERSATION_LIMIT and len(memories) > DEFAULT_CONVERSATION_LIMIT:
        memories = memories[-DEFAULT_CONVERSATION_LIMIT:]

    for memory in memories:
        turns.append(_memory_to_turn(memory))

    if fallback_map:
        known_ids = {turn.memory_id for turn in turns if turn.memory_id}
        for key, fallback in fallback_map.items():
            if key and key in known_ids:
                continue
            turns.append(fallback)

    return turns


def _normalize_fallback(payload: dict) -> TurnPayload:
    return TurnPayload(
        memory_id=payload.get("turn_id"),
        user_input=(payload.get("user_input") or "").strip(),
        response=(payload.get("response") or "").strip(),
        distilled=(payload.get("distilled") or "").strip(),
        persona=(payload.get("persona") or "").strip(),
        model=(payload.get("model") or "").strip(),
    )


def _memory_to_turn(memory: Memory) -> TurnPayload:
    metadata = memory.metadata.constraints or {}
    user_input = (metadata.get("input") or _parse_summary(memory.content.bytes or "")[0]).strip()
    response = (metadata.get("response") or _parse_summary(memory.content.bytes or "")[1]).strip()
    distilled = (metadata.get("distilled") or "").strip()
    persona = (metadata.get("persona") or "").strip()
    model = (metadata.get("model") or "").strip()
    return TurnPayload(
        memory_id=memory.id,
        user_input=user_input,
        response=response,
        distilled=distilled,
        persona=persona,
        model=model,
    )


def _parse_summary(summary: str) -> tuple[str, str]:
    if not summary:
        return "", ""
    user_text = ""
    assistant_text = ""
    for line in summary.splitlines():
        stripped = line.strip()
        if stripped.startswith("🧑"):
            user_text = stripped.lstrip("🧑").strip()
        elif stripped.startswith("🤖"):
            assistant_text = stripped.lstrip("🤖").strip()
    return user_text, assistant_text


def _build_conversation_text(turns: List[TurnPayload]) -> str:
    sections: List[str] = []
    for idx, turn in enumerate(turns, start=1):
        block = textwrap.dedent(
            f"""Turn {idx}
            User: {turn.user_input}
            Assistant: {turn.response}
            """
        ).strip()
        sections.append(block)
    return "\n\n".join(sections).strip()


def _derive_title(turns: List[TurnPayload]) -> str:
    for turn in turns:
        candidate = turn.user_input.strip()
        if candidate:
            return candidate[:80]
    for turn in turns:
        if turn.response.strip():
            return turn.response.strip()[:80]
    return "Chat Promotion"


def _extract_requirements(turns: List[TurnPayload]) -> List[str]:
    for turn in turns:
        distilled = turn.distilled
        if distilled:
            items = [item.strip("-• ") for item in distilled.splitlines() if item.strip()]
            if items:
                return items[:5]
    first = turns[0]
    fallback = [first.user_input.strip()] if first.user_input.strip() else []
    return fallback or ["Follow up on conversation"]


def _gather_turn_ids(turns: List[TurnPayload]) -> List[str]:
    return [turn.memory_id for turn in turns if turn.memory_id]


def _promote_run(*, mode: Mode, tag: str, chat_id: str, persona: str, turns: List[TurnPayload]) -> dict:
    text = _build_conversation_text(turns)
    brief_payload = {
        "mode": mode.value,
        "text": textwrap.dedent(
            f"""Based on the conversation below, continue in {mode.value} mode.

            {text}
            """
        ).strip(),
        "machines": ["skylink"],
        "tags": [f"chat:{chat_id}", tag],
        "plan_preview": BriefPlanPreference.AUTO.value,
        "notes": f"Source persona: {persona}",
    }
    brief = Brief.from_dict(brief_payload)
    run_record = RUN_MANAGER.start_run(brief)
    return {
        "kind": "run",
        "run": run_record.to_dict(),
        "message": f"Started {mode.value} run {run_record.id}",
    }


def _promote_build(
    *,
    registry: MemoryRegistry,
    session: Memory,
    chat_id: str,
    persona: str,
    turns: List[TurnPayload],
    scope: str,
) -> dict:
    title = _derive_title(turns)
    requirements = _extract_requirements(turns)
    conversation = _build_conversation_text(turns)
    constraints = {
        "source": "chat",
        "chat_id": chat_id,
        "scope": scope,
        "persona": persona,
        "conversation": conversation,
    }

    action_memory = create_action(
        registry,
        title=title,
        intent="code.patch",
        thread=chat_id,
        requirements=requirements,
        constraints=constraints,
    )
    action = Action.from_memory(action_memory)

    turn_ids = _gather_turn_ids(turns)
    if turn_ids:
        add_derivations(registry, child_id=action.id, sources=turn_ids)
        for turn_id in turn_ids:
            try:
                link_produced(registry, parent_id=turn_id, child_id=action.id)
            except KeyError:
                continue

    try:
        link_produced(registry, parent_id=session.id, child_id=action.id)
    except KeyError:
        pass

    brief_result = build_brief(action, registry)

    return {
        "kind": "action",
        "action_id": action.id,
        "brief_id": brief_result.brief.id,
        "message": f"Created action {action.title}",
    }


def _promote_task(
    *,
    registry: MemoryRegistry,
    session: Memory,
    chat_id: str,
    persona: str,
    turns: List[TurnPayload],
    scope: str,
) -> dict:
    title = _derive_title(turns)
    conversation = _build_conversation_text(turns)
    description = textwrap.dedent(
        f"""Task sourced from chat {chat_id} ({scope}).

        Conversation:
        {conversation}
        """
    ).strip()
    steps = _extract_requirements(turns)
    task = create_task(
        title=title,
        description=description,
        files=[],
        tags=["chat", chat_id, f"persona:{persona}"],
        steps=steps,
    )
    task_path = TASKS_DIR / task["id"] / "task.json"

    task_rel = _safe_relative(task_path, PROJECT_ROOT)
    note = Memory(
        id=generate_ulid(),
        type="note",
        purpose="chat.task",
        handle=chat_id,
        title=f"Task created: {task['title']}",
        tags=["chat", "task", "promotion"],
        state="active",
        registry_status="registered",
        relations=Relations(thread_of=session.id, derived_from=_gather_turn_ids(turns), produces=[]),
        content=MemoryContent(path=str(task_rel)),
        metadata=MemoryMetadata(constraints={"task_id": task["id"], "scope": scope}),
        actor=Actor(actor_id="chat_promotion", actor_type="service"),
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    registry.register(note)
    try:
        link_produced(registry, parent_id=session.id, child_id=note.id)
    except KeyError:
        pass
    for turn_id in _gather_turn_ids(turns):
        try:
            link_produced(registry, parent_id=turn_id, child_id=note.id)
        except KeyError:
            continue

    return {
        "kind": "task",
        "task": task,
        "task_path": str(task_path),
        "message": f"Created task {task['id']}",
    }


def _promote_document(
    *,
    registry: MemoryRegistry,
    session: Memory,
    chat_id: str,
    persona: str,
    turns: List[TurnPayload],
    scope: str,
) -> dict:
    config = LTPConfig.load()
    title = _derive_title(turns)
    slug_base = ProjectStore.normalize_slug(f"chat-{chat_id[:8]}-{uuid.uuid4().hex[:6]}")
    conversation = _build_conversation_text(turns)
    body = textwrap.dedent(
        f"""# {title or 'Living Truth Update'}

        _Generated from chat {chat_id} on {utc_now()}._

        ## Conversation Context

        {conversation}
        """
    ).strip() + "\n"

    store = ProjectStore.create(
        config,
        slug=slug_base,
        title=title or slug_base,
        owners=[],
        tags=["chat", chat_id, f"scope:{scope}", f"persona:{persona}"],
        body=body,
    )

    doc_rel = _safe_relative(store.doc_path, config.root)
    note = Memory(
        id=generate_ulid(),
        type="note",
        purpose="chat.document",
        handle=chat_id,
        title=f"Document created: {store.title}",
        tags=["chat", "document", "promotion"],
        state="active",
        registry_status="registered",
        relations=Relations(thread_of=session.id, derived_from=_gather_turn_ids(turns), produces=[]),
        content=MemoryContent(path=str(doc_rel)),
        metadata=MemoryMetadata(constraints={"slug": store.slug, "scope": scope}),
        actor=Actor(actor_id="chat_promotion", actor_type="service"),
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    registry.register(note)
    try:
        link_produced(registry, parent_id=session.id, child_id=note.id)
    except KeyError:
        pass
    for turn_id in _gather_turn_ids(turns):
        try:
            link_produced(registry, parent_id=turn_id, child_id=note.id)
        except KeyError:
            continue

    return {
        "kind": "document",
        "slug": store.slug,
        "doc_path": str(store.doc_path),
        "message": f"Created living truth doc {store.slug}",
    }


def _promote_chat(*, chat_id: str, persona: str, turns: List[TurnPayload]) -> dict:
    new_chat_id = uuid.uuid4().hex
    seed_text = _build_conversation_text(turns)
    return {
        "kind": "chat",
        "new_chat_id": new_chat_id,
        "seed": seed_text,
        "persona": persona,
        "message": "Created new chat branch",
    }


def _safe_relative(path: Path, base: Path) -> Path:
    try:
        return path.relative_to(base)
    except ValueError:
        return path
