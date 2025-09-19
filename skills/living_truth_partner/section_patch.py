# name: section_patch.py
# path: skills/living_truth_partner/section_patch.py
# role: Apply GPT-guided replacements to Markdown sections
# deps: json, dataclasses, pathlib, typing, hashlib, difflib, cortex.ai_router, continuum.patcher, skills.living_truth_partner.md_index
# inputs: ProjectStore, Config, section patch parameters
# outputs: SectionPatch.Result

from __future__ import annotations

import difflib
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from cortex.ai_router import get_router

from continuum.patcher import replace_file_if_changed
from skills.living_truth_partner.config import Config
from skills.living_truth_partner.md_index import MarkdownIndex
from skills.living_truth_partner.project_store import ProjectStore

__all__ = ["SectionPatch"]

_PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _load_prompt(name: str) -> str:
    path = _PROMPTS_DIR / name
    if not path.exists():
        raise FileNotFoundError(path)
    return path.read_text(encoding="utf-8").strip()


def _count_changes(before: str, after: str) -> int:
    diff = difflib.ndiff(before.splitlines(), after.splitlines())
    return sum(1 for line in diff if line.startswith("- ") or line.startswith("+ "))


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _normalize_output(output: str) -> str:
    cleaned = output.strip()
    if cleaned.startswith("```") and cleaned.endswith("```"):
        cleaned = cleaned.split("\n", 1)[1].rsplit("\n", 1)[0]
    return cleaned.strip() + "\n"


def _build_messages(store: ProjectStore, context: dict[str, Any], section_text: str, intent: str, constraints: Iterable[str]) -> list[dict[str, str]]:
    system = _load_prompt("section_patch_system.txt")
    user_template = _load_prompt("section_patch_user.txt")
    payload = user_template.format(
        doc=store.slug,
        section=context.get("title", section_text.splitlines()[0] if section_text else section_text),
        section_id=context.get("id"),
        intent=intent,
        constraints="\n".join(constraints),
        summary=json.dumps(context, indent=2),
        current=section_text
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": payload}
    ]


def _log_patch(store: ProjectStore, payload: dict[str, Any]) -> Path:
    path = store.new_history_patch_path()
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


class SectionPatch:
    @dataclass(frozen=True)
    class Result:
        doc_path: Path
        patch_path: Path | None
        model_output: str
        changed: bool
        before: str
        after: str
        diff: str

    @staticmethod
    def run(store: ProjectStore, config: Config, section_id: str, intent: str, constraints: Iterable[str], apply_changes: bool = True) -> Result:
        doc_text = store.doc_path.read_text(encoding="utf-8")
        index = MarkdownIndex.build(doc_text)
        section = index.section(section_id)
        if section is None:
            raise KeyError(section_id)
        current = index.slice(doc_text, section_id)
        summary = _load_json(store.summary_path)
        context = {
            "id": section.id,
            "title": section.title,
            "high_level_context": summary.get("high_level_context", ""),
            "constraints": summary.get("constraints", []),
            "acceptance_criteria": summary.get("acceptance_criteria", []),
            "mentions": summary.get("mentions", []),
            "related": summary.get("related", [])
        }
        messages = _build_messages(store, context, current, intent, constraints)
        router = get_router()
        raw = router.chat(messages, model=config.prose_model)
        replacement = _normalize_output(raw)
        updated = index.replace(doc_text, section_id, replacement)
        changed = False
        patch_path = None
        diff = "".join(difflib.unified_diff(current.splitlines(True), replacement.splitlines(True), fromfile="before", tofile="after"))
        if apply_changes:
            changed = replace_file_if_changed(str(store.doc_path), updated)
            patch_path = None
            if changed:
                payload = {
                    "doc": store.slug,
                    "kind": "section",
                    "id": section.id,
                    "intent": intent,
                    "constraints": list(constraints),
                    "before_sha256": _hash(current),
                    "after_sha256": _hash(replacement),
                    "lines_changed": _count_changes(current, replacement),
                    "model": config.prose_model,
                    "risk_notes": [],
                    "test_plan": []
                }
                patch_path = _log_patch(store, payload)
        else:
            if current != replacement:
                changed = True
            patch_path = None
        return SectionPatch.Result(store.doc_path, patch_path, raw, changed, current, replacement, diff)
