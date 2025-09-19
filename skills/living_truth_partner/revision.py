# name: revision.py
# path: skills/living_truth_partner/revision.py
# role: Provide guided revision suggestions and batch apply helpers
# deps: typing, dataclasses, skills.living_truth_partner.guardrails, skills.living_truth_partner.section_patch, skills.living_truth_partner.project_store, skills.living_truth_partner.config
# inputs: ProjectStore, Config, section ids
# outputs: prepare and apply helpers

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List

from skills.living_truth_partner.config import Config
from skills.living_truth_partner.guardrails import analyze
from skills.living_truth_partner.project_store import ProjectStore
from skills.living_truth_partner.section_patch import SectionPatch

__all__ = ["Suggestion", "prepare", "apply"]


@dataclass(frozen=True)
class Suggestion:
    section_id: str
    title: str
    intent: str
    constraints: List[str]
    reason: str


def prepare(store: ProjectStore, section_ids: Iterable[str] | None = None) -> List[Suggestion]:
    selected = set(section_ids or [])
    suggestions: List[Suggestion] = []
    for insight in analyze(store):
        if selected and insight.section_id not in selected:
            continue
        for issue in insight.issues:
            reason = issue["message"]
            intent = issue["intent"]
            constraints = [c for c in issue.get("constraints", [])]
            suggestions.append(Suggestion(insight.section_id, insight.title, intent, constraints, reason))
    return suggestions


def apply(store: ProjectStore, config: Config, suggestions: Iterable[Suggestion], apply_changes: bool) -> List[SectionPatch.Result]:
    results: List[SectionPatch.Result] = []
    for suggestion in suggestions:
        result = SectionPatch.run(store, config, suggestion.section_id, suggestion.intent, suggestion.constraints, apply_changes)
        results.append(result)
    return results
