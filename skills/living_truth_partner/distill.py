# name: distill.py
# path: skills/living_truth_partner/distill.py
# role: Distill discussion notes into structured context summary and prompts
# deps: json, dataclasses, pathlib, typing, cortex.ai_router, skills.living_truth_partner.md_index
# inputs: ProjectStore, Config, options
# outputs: Distill.Result

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from cortex.ai_router import get_router

from skills.living_truth_partner.config import Config
from skills.living_truth_partner.md_index import MarkdownIndex
from skills.living_truth_partner.project_store import ProjectStore

__all__ = ["Distill"]

_PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


def _load_prompt(name: str) -> str:
    path = _PROMPTS_DIR / name
    if not path.exists():
        raise FileNotFoundError(path)
    return path.read_text(encoding="utf-8").strip()


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _collect_notes(paths: Iterable[Path], limit: int) -> list[tuple[str, str]]:
    ordered = sorted(paths)
    selected = ordered[-limit:]
    out: list[tuple[str, str]] = []
    for path in selected:
        out.append((path.name, path.read_text(encoding="utf-8").strip()))
    return out


def _build_sections(doc_text: str) -> list[dict[str, Any]]:
    index = MarkdownIndex.build(doc_text)
    sections = []
    for section in index.sections():
        portion = index.slice(doc_text, section.id)
        sections.append({
            "id": section.id,
            "path": f"#/{section.id}",
            "h": section.title,
            "tokens": len(portion.split())
        })
    return sections


def _format_notes(notes: list[tuple[str, str]]) -> str:
    parts = []
    for name, text in notes:
        parts.append(name)
        parts.append(text)
    return "\n\n".join(parts)


def _build_messages(store: ProjectStore, config: Config, max_notes: int) -> list[dict[str, str]]:
    doc_text = store.doc_path.read_text(encoding="utf-8")
    summary = _load_json(store.summary_path)
    notes = _collect_notes(store.history_root.glob("*_notes.md"), max_notes)
    system = _load_prompt("distill_system.txt")
    user_template = _load_prompt("distill_user.txt")
    payload = user_template.format(
        title=summary.get("title") or store.title or store.slug,
        existing_summary=summary.get("high_level_context", ""),
        notes=_format_notes(notes),
        doc=doc_text
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": payload}
    ]


def _persist_summary(store: ProjectStore, doc_text: str, payload: dict[str, Any]) -> None:
    base = _load_json(store.summary_path)
    base["id"] = store.slug
    base["title"] = payload.get("title") or base.get("title") or store.title or store.slug
    base["owners"] = payload.get("owners") or base.get("owners") or []
    base["tags"] = payload.get("tags") or base.get("tags") or []
    base["high_level_context"] = payload.get("high_level_context", base.get("high_level_context", ""))
    base["constraints"] = payload.get("constraints", base.get("constraints", []))
    base["acceptance_criteria"] = payload.get("acceptance_criteria", base.get("acceptance_criteria", []))
    base["mentions"] = payload.get("mentions", base.get("mentions", []))
    base["related"] = payload.get("related", base.get("related", []))
    base["sections"] = _build_sections(doc_text)
    store.summary_path.write_text(json.dumps(base, indent=2), encoding="utf-8")


def _persist_prompts(store: ProjectStore, prompts: list[str]) -> None:
    data = {"prompts": prompts}
    store.prompts_path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _persist_links(store: ProjectStore, links: list[dict[str, Any]]) -> None:
    lines = []
    for link in links:
        lines.append(json.dumps(link))
    store.links_path.write_text("\n".join(lines), encoding="utf-8")


def _persist_action_items(store: ProjectStore, items: list[dict[str, Any]] | list[str]) -> None:
    if items and isinstance(items[0], str):
        converted = [{"title": item, "done": False} for item in items]
    else:
        converted = []
        for item in items or []:
            if isinstance(item, dict):
                converted.append({
                    "title": item.get("title") or item.get("text") or "",
                    "done": bool(item.get("done", False))
                })
    store.action_items_path.write_text(json.dumps({"action_items": converted}, indent=2), encoding="utf-8")


class Distill:
    @dataclass(frozen=True)
    class Result:
        summary_path: Path
        links_path: Path
        prompts_path: Path
        action_items_path: Path
        raw_text: str

    @staticmethod
    def run(store: ProjectStore, config: Config, max_notes: int = 5) -> Result:
        messages = _build_messages(store, config, max_notes)
        router = get_router()
        reply = router.chat(messages, model=config.prose_model)
        payload = json.loads(reply)
        doc_text = store.doc_path.read_text(encoding="utf-8")
        _persist_summary(store, doc_text, payload)
        _persist_prompts(store, payload.get("prompts", []))
        _persist_links(store, payload.get("links", []))
        _persist_action_items(store, payload.get("action_items", []))
        return Distill.Result(store.summary_path, store.links_path, store.prompts_path, store.action_items_path, reply)
