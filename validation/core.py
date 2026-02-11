

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, TypeAlias


MetricValue: TypeAlias = int | float | str | bool | list | dict | None


class Verdict(Enum):

    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"

    def __lt__(self, other: Verdict) -> bool:
        order = {Verdict.PASS: 0, Verdict.WARN: 1, Verdict.FAIL: 2}
        return order[self] < order[other]

    @classmethod
    def aggregate(cls, verdicts: list[Verdict]) -> Verdict:
        if not verdicts:
            return cls.PASS
        return max(verdicts)


@dataclass(frozen=True)
class InvariantResult:

    id: str
    category: str
    artifact: str
    description: str
    status: Verdict
    checked: int = 0
    passed: int = 0
    failed: int = 0
    failures: tuple[str, ...] = ()
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "invariant": {
                "id": self.id,
                "category": self.category,
                "artifact": self.artifact,
                "description": self.description,
                "status": self.status.value,
                "details": {
                    "checked": self.checked,
                    "passed": self.passed,
                    "failed": self.failed,
                    "failures": list(self.failures),
                    **self.details,
                },
            }
        }


@dataclass(frozen=True)
class AssertionResult:

    id: str
    source: str
    intent: str
    expected: dict[str, Any]
    actual: dict[str, Any]
    status: Verdict
    tolerance: float = 0.01
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "assertion": {
                "id": self.id,
                "source": self.source,
                "intent": self.intent,
                "expected": self.expected,
                "actual": self.actual,
                "status": self.status.value,
                "tolerance": self.tolerance,
                "message": self.message,
            }
        }


@dataclass(frozen=True)
class RegressionResult:

    metric_path: str
    golden_value: MetricValue
    current_value: MetricValue
    delta: float | None
    delta_percent: float | None
    tolerance_percent: float
    status: Verdict
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "regression": {
                "metric_path": self.metric_path,
                "golden_value": self.golden_value,
                "current_value": self.current_value,
                "delta": self.delta,
                "delta_percent": self.delta_percent,
                "tolerance_percent": self.tolerance_percent,
                "status": self.status.value,
                "message": self.message,
            }
        }


@dataclass
class InvariantSummary:

    total: int = 0
    passed: int = 0
    warned: int = 0
    failed: int = 0
    results: list[InvariantResult] = field(default_factory=list)

    def add(self, result: InvariantResult) -> None:
        self.results.append(result)
        self.total += 1
        if result.status == Verdict.PASS:
            self.passed += 1
        elif result.status == Verdict.WARN:
            self.warned += 1
        else:
            self.failed += 1

    def verdict(self) -> Verdict:
        if self.failed > 0:
            return Verdict.FAIL
        if self.warned > 0:
            return Verdict.WARN
        return Verdict.PASS

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "passed": self.passed,
            "warned": self.warned,
            "failed": self.failed,
            "results": [r.to_dict() for r in self.results],
        }


@dataclass
class AssertionSummary:

    total: int = 0
    passed: int = 0
    failed: int = 0
    results: list[AssertionResult] = field(default_factory=list)

    def add(self, result: AssertionResult) -> None:
        self.results.append(result)
        self.total += 1
        if result.status == Verdict.PASS:
            self.passed += 1
        else:
            self.failed += 1

    def verdict(self) -> Verdict:
        return Verdict.FAIL if self.failed > 0 else Verdict.PASS

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "passed": self.passed,
            "failed": self.failed,
            "results": [r.to_dict() for r in self.results],
        }


@dataclass
class RegressionSummary:

    compared: bool = False
    golden_file: str | None = None
    total: int = 0
    within_tolerance: int = 0
    exceeded_tolerance: int = 0
    results: list[RegressionResult] = field(default_factory=list)

    def add(self, result: RegressionResult) -> None:
        self.results.append(result)
        self.total += 1
        if result.status == Verdict.PASS:
            self.within_tolerance += 1
        else:
            self.exceeded_tolerance += 1

    def verdict(self) -> Verdict:
        if not self.compared:
            return Verdict.PASS
        verdicts = [r.status for r in self.results]
        return Verdict.aggregate(verdicts)

    def to_dict(self) -> dict[str, Any]:
        return {
            "compared": self.compared,
            "golden_file": self.golden_file,
            "total": self.total,
            "within_tolerance": self.within_tolerance,
            "exceeded_tolerance": self.exceeded_tolerance,
            "results": [r.to_dict() for r in self.results],
        }


@dataclass
class CAMValidationResult:

    version: str = "1.0.0"
    timestamp: str = ""
    input_file: str = ""
    verdict: Verdict = Verdict.PASS


    metrics: dict[str, dict[str, Any]] = field(default_factory=dict)


    invariants: InvariantSummary = field(default_factory=InvariantSummary)
    assertions: AssertionSummary = field(default_factory=AssertionSummary)
    regressions: RegressionSummary = field(default_factory=RegressionSummary)


    execution_time_ms: float = 0.0
    verdict_reason: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def compute_verdict(self) -> Verdict:
        verdicts = [
            self.invariants.verdict(),
            self.assertions.verdict(),
            self.regressions.verdict(),
        ]
        self.verdict = Verdict.aggregate(verdicts)
        self._set_verdict_reason()
        return self.verdict

    def _set_verdict_reason(self) -> None:
        if self.verdict == Verdict.PASS:
            self.verdict_reason = "All checks passed"
        elif self.verdict == Verdict.WARN:
            reasons = []
            if self.invariants.warned > 0:
                reasons.append(f"{self.invariants.warned} invariant warning(s)")
            if self.regressions.exceeded_tolerance > 0:
                reasons.append(f"{self.regressions.exceeded_tolerance} regression warning(s)")
            self.verdict_reason = "; ".join(reasons) if reasons else "Warnings detected"
        else:
            reasons = []
            if self.invariants.failed > 0:
                reasons.append(f"{self.invariants.failed} invariant failure(s)")
            if self.assertions.failed > 0:
                reasons.append(f"{self.assertions.failed} assertion failure(s)")
            if self.regressions.exceeded_tolerance > 0:
                reasons.append(f"{self.regressions.exceeded_tolerance} regression failure(s)")
            self.verdict_reason = "; ".join(reasons) if reasons else "Failures detected"

    def to_dict(self) -> dict[str, Any]:
        return {
            "validation_result": {
                "version": self.version,
                "timestamp": self.timestamp,
                "input_file": self.input_file,
                "verdict": self.verdict.value,
                "metrics": self.metrics,
                "invariants": self.invariants.to_dict(),
                "assertions": self.assertions.to_dict(),
                "regressions": self.regressions.to_dict(),
                "summary": {
                    "verdict_reason": self.verdict_reason,
                    "execution_time_ms": round(self.execution_time_ms, 2),
                },
            }
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CAMValidationResult:
        vr = data.get("validation_result", data)
        result = cls(
            version=vr.get("version", "1.0.0"),
            timestamp=vr.get("timestamp", ""),
            input_file=vr.get("input_file", ""),
            verdict=Verdict(vr.get("verdict", "pass")),
        )
        result.metrics = vr.get("metrics", {})
        result.execution_time_ms = vr.get("summary", {}).get("execution_time_ms", 0.0)
        result.verdict_reason = vr.get("summary", {}).get("verdict_reason", "")
        return result


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


def round_metric(value: float, precision: int = 4) -> float:
    return round(value, precision)


def normalize_metric_dict(d: dict[str, Any], precision: int = 4) -> dict[str, Any]:
    result = {}
    for k, v in d.items():
        if isinstance(v, float):
            result[k] = round_metric(v, precision)
        elif isinstance(v, dict):
            result[k] = normalize_metric_dict(v, precision)
        elif isinstance(v, list):
            result[k] = [
                round_metric(x, precision) if isinstance(x, float)
                else normalize_metric_dict(x, precision) if isinstance(x, dict)
                else x
                for x in v
            ]
        else:
            result[k] = v
    return result
