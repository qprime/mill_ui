# name: target_patch.py
# path: skills/living_truth_partner/target_patch.py
# role: Update target code blocks using CodeX model responses
# deps: json, dataclasses, pathlib, typing, hashlib, difflib, cortex.ai_router, continuum.patcher
# inputs: ProjectStore, Config, target id, intent, constraints
# outputs: TargetPatch.Result

from __future__ import annotations

import difflib
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from cortex.ai_router import get_router

from continuum.patcher import replace_file_if_changed
from skills.living_truth_partner.config import Config
from skills.living_truth_partner.project_store import ProjectStore

__all__ = ["TargetPatch"]

_PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


def _load_prompt(name: str) -> str:
    path = _PROMPTS_DIR / name
    if not path.exists():
        raise FileNotFoundError(path)
    return path.read_text(encoding="utf-8").strip()


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _lines_changed(old: str, new: str) -> int:
    diff = difflib.ndiff(old.splitlines(), new.splitlines())
    return sum(1 for line in diff if line.startswith("- ") or line.startswith("+ "))


def _find_target(doc_text: str, target: str) -> tuple[str, str, str]:
    lines = doc_text.splitlines()
    start = None
    end = None
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith(":::target "):
            name = stripped.split(" ", 1)[1].strip()
            if name == target:
                start = idx + 1
                continue
        if start is not None and stripped == ":::":
            end = idx
            break
    if start is None or end is None:
        raise KeyError(target)
    header = "\n".join(lines[:start]) + "\n"
    footer = "\n".join(lines[end:])
    body = "\n".join(lines[start:end])
    return header, body, footer


def _build_messages(doc: str, target: str, body: str, intent: str, constraints: Iterable[str]) -> list[dict[str, str]]:
    system = _load_prompt("target_patch_system.txt")
    user_template = _load_prompt("target_patch_user.txt")
    payload = user_template.format(
        doc=doc,
        target=target,
        intent=intent,
        constraints="\n".join(constraints),
        current=body
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": payload}
    ]


def _log(store: ProjectStore, target: str, intent: str, before: str, after: str, model: str, constraints: Iterable[str]) -> Path:
    payload = {
        "doc": store.slug,
        "kind": "target",
        "id": target,
        "intent": intent,
        "constraints": list(constraints),
        "before_sha256": _hash(before),
        "after_sha256": _hash(after),
        "lines_changed": _lines_changed(before, after),
        "model": model,
        "risk_notes": [],
        "test_plan": []
    }
    path = store.new_history_patch_path()
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


class TargetPatch:
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
    def run(store: ProjectStore, config: Config, target: str, intent: str, constraints: Iterable[str], apply_changes: bool = True) -> Result:
        doc_text = store.doc_path.read_text(encoding="utf-8")
        header, body, footer = _find_target(doc_text, target)
        messages = _build_messages(store.slug, target, body, intent, constraints)
        router = get_router()
        raw = router.chat(messages, model=config.code_model)
        replacement = raw.strip() + "\n"
        updated = header + replacement + footer
        diff = "".join(difflib.unified_diff(body.splitlines(True), replacement.splitlines(True), fromfile="before", tofile="after"))
        changed = False
        patch_path = None
        if apply_changes:
            changed = replace_file_if_changed(str(store.doc_path), updated)
            if changed:
                patch_path = _log(store, target, intent, body, replacement, config.code_model, constraints)
        else:
            if body != replacement:
                changed = True
        return TargetPatch.Result(store.doc_path, patch_path, raw, changed, body, replacement, diff)
