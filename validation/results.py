
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from validation.core import InvariantResult, Verdict


@dataclass
class ValidationIssue:

    message: str
    region_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationResult:

    errors: list[ValidationIssue] = field(default_factory=list)
    warnings: list[ValidationIssue] = field(default_factory=list)
    suggestions: list[ValidationIssue] = field(default_factory=list)

    def add_error(self, message: str, region_id: str | None = None, **metadata: Any) -> None:
        self.errors.append(ValidationIssue(message, region_id, metadata))

    def add_warning(self, message: str, region_id: str | None = None, **metadata: Any) -> None:
        self.warnings.append(ValidationIssue(message, region_id, metadata))

    def add_suggestion(self, message: str, region_id: str | None = None, **metadata: Any) -> None:
        self.suggestions.append(ValidationIssue(message, region_id, metadata))

    def is_valid(self) -> bool:
        return len(self.errors) == 0

    def has_issues(self) -> bool:
        return len(self.errors) > 0 or len(self.warnings) > 0 or len(self.suggestions) > 0

    @property
    def verdict(self) -> Verdict:
        from validation.core import Verdict
        if self.errors:
            return Verdict.FAIL
        if self.warnings:
            return Verdict.WARN
        return Verdict.PASS

    def summary(self) -> str:
        if not self.has_issues():
            return "Validation passed with no issues"

        parts = []
        if self.errors:
            parts.append(f"{len(self.errors)} error(s)")
        if self.warnings:
            parts.append(f"{len(self.warnings)} warning(s)")
        if self.suggestions:
            parts.append(f"{len(self.suggestions)} suggestion(s)")

        return f"Validation: {', '.join(parts)}"

    def to_invariant_result(
        self,
        invariant_id: str,
        category: str = "removal_intent",
        artifact: str = "ir",
        description: str = "",
    ) -> InvariantResult:
        from validation.core import InvariantResult, Verdict

        failures = tuple(
            f"{e.message}" + (f" (region: {e.region_id})" if e.region_id else "")
            for e in self.errors
        )
        failures += tuple(
            f"[WARN] {w.message}" + (f" (region: {w.region_id})" if w.region_id else "")
            for w in self.warnings
        )

        checked = len(self.errors) + len(self.warnings) + len(self.suggestions)
        if checked == 0:
            checked = 1

        return InvariantResult(
            id=invariant_id,
            category=category,
            artifact=artifact,
            description=description or invariant_id,
            status=self.verdict,
            checked=checked,
            passed=checked - len(self.errors) - len(self.warnings),
            failed=len(self.errors),
            failures=failures,
            details={
                "error_count": len(self.errors),
                "warning_count": len(self.warnings),
                "suggestion_count": len(self.suggestions),
            },
        )
