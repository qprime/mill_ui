# name: persona_builder.py
# path: skills/living_truth_partner/persona_builder.py
# role: Append buyer personas into plan sections
# deps: typing, skills.living_truth_partner.md_index, skills.living_truth_partner.project_store
# inputs: ProjectStore, persona payload
# outputs: add_persona result boolean

from __future__ import annotations

from typing import Dict

from skills.living_truth_partner.md_index import MarkdownIndex
from skills.living_truth_partner.project_store import ProjectStore

__all__ = ["add_persona"]

_DEFAULT_SECTION = "market"


def _persona_block(payload: Dict[str, str]) -> str:
    name = payload.get("name", "Persona").strip() or "Persona"
    role = payload.get("role", "").strip()
    goals = payload.get("goals", "").strip()
    pains = payload.get("pains", "").strip()
    lines = [f"- **{name}**"]
    if role:
        lines[0] += f" — {role}"
    if goals:
        lines.append(f"  - Goals: {goals}")
    if pains:
        lines.append(f"  - Pain Points: {pains}")
    return "\n".join(lines) + "\n"


def _ensure_heading(body: str) -> tuple[str, bool]:
    if "### Buyer Personas" in body:
        return body, False
    updated = body.rstrip() + "\n\n### Buyer Personas\n\n"
    return updated, True


def add_persona(store: ProjectStore, payload: Dict[str, str]) -> bool:
    text = store.doc_path.read_text(encoding="utf-8")
    index = MarkdownIndex.build(text)
    target_id = payload.get("section_id", _DEFAULT_SECTION)
    section = index.section(target_id)
    if section is None:
        target_id = _DEFAULT_SECTION
        section = index.section(target_id)
    if section is None:
        return False
    body = index.slice(text, target_id)
    body, _ = _ensure_heading(body)
    body = body + _persona_block(payload) + "\n"
    updated = index.replace(text, target_id, body)
    store.doc_path.write_text(updated, encoding="utf-8")
    return True
