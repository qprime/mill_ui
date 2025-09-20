from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Sequence

from .models import Action
from .policies import PolicyStore
from .utils import MAX_DIFF_SLOC

__all__ = ["GuardrailReport", "analyze_action", "count_diff_sloc"]


@dataclass
class GuardrailReport:
    action_id: str
    requires_human: bool
    escalation_reasons: List[str] = field(default_factory=list)
    required_tests: List[str] = field(default_factory=list)
    delta_sloc: int = 0
    notes: Dict[str, str] = field(default_factory=dict)

    def merge_escalation(self, reason: str) -> None:
        if reason not in self.escalation_reasons:
            self.escalation_reasons.append(reason)
        self.requires_human = True


def count_diff_sloc(diff_text: str) -> int:
    total = 0
    current_suffix = ""
    for line in diff_text.splitlines():
        if line.startswith("+++"):
            path = line[4:].strip()
            if path.startswith("b/"):
                path = path[2:]
            current_suffix = Path(path).suffix.lower()
            continue
        if not line or line.startswith("@@") or line.startswith("+++") or line.startswith("---"):
            continue
        if line.startswith("+") or line.startswith("-"):
            body = line[1:].strip()
            if not body:
                continue
            if current_suffix == ".py" and body.startswith("#"):
                continue
            total += 1
    return total


def analyze_action(
    action: Action,
    *,
    policy_store: PolicyStore,
    diff_texts: Sequence[str] | None = None,
    context: Dict[str, str] | None = None,
) -> GuardrailReport:
    context = context or {}
    diff_texts = diff_texts or []
    report = GuardrailReport(action_id=action.id, requires_human=False)

    paths = set(context.get("paths", []))
    metadata_visibility = context.get("visibility", "internal")
    sensitivity = context.get("sensitivity", "low")

    if metadata_visibility == "external" and action.intent == "doc.export":
        report.merge_escalation("guardrail_fail")
        report.notes["visibility"] = "External export requires explicit approval"

    if sensitivity in {"pii", "safety"}:
        report.merge_escalation("risk_flag")
        report.notes["sensitivity"] = f"Sensitivity {sensitivity}"

    safety_paths = policy_store.safety.get("safety_critical_paths", [])
    safety_hits = [p for p in paths if any(p.startswith(root.rstrip("*")) for root in safety_paths)]
    if safety_hits:
        report.merge_escalation("risk_flag")
        report.required_tests.extend(policy_store.safety.get("required_tests", []))
        report.notes["safety_paths"] = ",".join(sorted(set(safety_hits)))

    delta_total = sum(count_diff_sloc(text) for text in diff_texts)
    report.delta_sloc = delta_total
    if delta_total > MAX_DIFF_SLOC:
        report.merge_escalation("risk_flag")
        report.notes["delta_sloc"] = str(delta_total)

    return report

