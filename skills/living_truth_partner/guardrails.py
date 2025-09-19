# name: guardrails.py
# path: skills/living_truth_partner/guardrails.py
# role: Analyze sections for tone, length, and structure guidance
# deps: dataclasses, typing, math, skills.living_truth_partner.md_index, skills.living_truth_partner.project_store
# inputs: ProjectStore
# outputs: analyze function results

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from skills.living_truth_partner.md_index import MarkdownIndex
from skills.living_truth_partner.project_store import ProjectStore

__all__ = ["analyze"]

_MAX_WORDS = 300
_HYPE_WORDS = {"revolutionary", "game-changing", "incredible", "amazing", "unprecedented"}
_WEAK_PHRASES = {"maybe", "might", "hope", "hopefully"}


@dataclass(frozen=True)
class SectionInsight:
    section_id: str
    title: str
    word_count: int
    snippet: str
    issues: List[Dict[str, List[str] | str]]
    quick_actions: List[Dict[str, List[str] | str]]


def _snippet(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return ""
    return lines[0][:240]


def _word_count(text: str) -> int:
    return len([w for w in text.split() if w.strip()])


def _count_matches(words: List[str], targets: set[str]) -> int:
    return sum(1 for w in words if w.lower().strip(".,!?") in targets)


def _issues_for_section(title: str, body: str) -> List[Dict[str, List[str] | str]]:
    words = body.split()
    issues: List[Dict[str, List[str] | str]] = []
    count = len(words)
    hype = _count_matches(words, _HYPE_WORDS)
    weak = _count_matches(words, _WEAK_PHRASES)
    if count > _MAX_WORDS:
        issues.append({
            "message": f"Section length {count} words; trim to ≤{_MAX_WORDS}.",
            "intent": "Trim section to stay concise (≤300 words).",
            "constraints": ["Preserve key facts."]
        })
    if hype > 2:
        issues.append({
            "message": "Tone leans hypey; dial back marketing language.",
            "intent": "Revise tone to stay factual and grounded.",
            "constraints": ["Avoid hype words."]
        })
    if weak > 3:
        issues.append({
            "message": "Many tentative phrases; increase confidence.",
            "intent": "Strengthen statements; reduce hedging words.",
            "constraints": ["Remove 'maybe', 'might', 'hopefully'."]
        })
    if not issues and "market" in title.lower():
        issues.append({
            "message": "Add 2-3 crisp buyer personas to clarify ICP.",
            "intent": "Add buyer personas with goals and pains.",
            "constraints": ["Keep ≤200 words."]
        })
    return issues


def _quick_actions(title: str, issues: List[Dict[str, List[str] | str]]) -> List[Dict[str, List[str] | str]]:
    actions: List[Dict[str, List[str] | str]] = []
    for issue in issues:
        actions.append({
            "label": issue["intent"],
            "intent": issue["intent"],
            "constraints": issue.get("constraints", [])
        })
    lowered = title.lower()
    if "exec" in lowered:
        actions.append({
            "label": "Clarify main ask",
            "intent": "Clarify the primary business ask in 3 sentences.",
            "constraints": ["Keep tone calm."]
        })
    if "financial" in lowered:
        actions.append({
            "label": "Summarize key metrics",
            "intent": "Summarize revenue, margin, and CAC/LTV in bullets.",
            "constraints": ["Include current numbers."]
        })
    return actions


def analyze(store: ProjectStore) -> List[SectionInsight]:
    text = store.doc_path.read_text(encoding="utf-8")
    index = MarkdownIndex.build(text)
    insights: List[SectionInsight] = []
    for section in index.sections():
        body = index.slice(text, section.id)
        word_count = _word_count(body)
        issues = _issues_for_section(section.title, body)
        quick = _quick_actions(section.title, issues)
        insights.append(SectionInsight(section.id, section.title, word_count, _snippet(body), issues, quick))
    return insights
