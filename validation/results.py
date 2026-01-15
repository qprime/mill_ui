
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


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
