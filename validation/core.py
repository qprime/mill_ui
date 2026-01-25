# validation/core.py - Core types for CAM artifact validation
#
# This module defines the base types used throughout the CAM validation system.
# All types are designed to be JSON-serializable and deterministic.
#
# See docs/cam_validation_plan.md for architecture and schemas.

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, TypeAlias


# Type alias for metric values (must be JSON-serializable)
MetricValue: TypeAlias = int | float | str | bool | list | dict | None


class Verdict(Enum):
    """Validation verdict for a check or overall result."""

    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"

    def __lt__(self, other: Verdict) -> bool:
        """Allow sorting: PASS < WARN < FAIL."""
        order = {Verdict.PASS: 0, Verdict.WARN: 1, Verdict.FAIL: 2}
        return order[self] < order[other]

    @classmethod
    def aggregate(cls, verdicts: list[Verdict]) -> Verdict:
        """Return the worst verdict from a list."""
        if not verdicts:
            return cls.PASS
        return max(verdicts)


@dataclass(frozen=True)
class InvariantResult:
    """Result of a single invariant check."""

    id: str
    category: str  # "structural", "topological", "safety"
    artifact: str  # "svg", "gcode"
    description: str
    status: Verdict
    checked: int = 0
    passed: int = 0
    failed: int = 0
    failures: tuple[str, ...] = ()
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
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
    """Result of an intent-derived assertion."""

    id: str
    source: str  # e.g., "pml:line:5" or "ast:item:door_outer"
    intent: str  # Human-readable intent description
    expected: dict[str, Any]
    actual: dict[str, Any]
    status: Verdict
    tolerance: float = 0.01
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
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
    """Result of comparing a metric against a golden baseline."""

    metric_path: str  # e.g., "gcode.complexity.total_moves"
    golden_value: MetricValue
    current_value: MetricValue
    delta: float | None  # None for non-numeric comparisons
    delta_percent: float | None
    tolerance_percent: float
    status: Verdict
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
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
    """Summary of all invariant checks."""

    total: int = 0
    passed: int = 0
    warned: int = 0
    failed: int = 0
    results: list[InvariantResult] = field(default_factory=list)

    def add(self, result: InvariantResult) -> None:
        """Add an invariant result and update counts."""
        self.results.append(result)
        self.total += 1
        if result.status == Verdict.PASS:
            self.passed += 1
        elif result.status == Verdict.WARN:
            self.warned += 1
        else:
            self.failed += 1

    def verdict(self) -> Verdict:
        """Return aggregate verdict."""
        if self.failed > 0:
            return Verdict.FAIL
        if self.warned > 0:
            return Verdict.WARN
        return Verdict.PASS

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "total": self.total,
            "passed": self.passed,
            "warned": self.warned,
            "failed": self.failed,
            "results": [r.to_dict() for r in self.results],
        }


@dataclass
class AssertionSummary:
    """Summary of all intent assertions."""

    total: int = 0
    passed: int = 0
    failed: int = 0
    results: list[AssertionResult] = field(default_factory=list)

    def add(self, result: AssertionResult) -> None:
        """Add an assertion result and update counts."""
        self.results.append(result)
        self.total += 1
        if result.status == Verdict.PASS:
            self.passed += 1
        else:
            self.failed += 1

    def verdict(self) -> Verdict:
        """Return aggregate verdict."""
        return Verdict.FAIL if self.failed > 0 else Verdict.PASS

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "total": self.total,
            "passed": self.passed,
            "failed": self.failed,
            "results": [r.to_dict() for r in self.results],
        }


@dataclass
class RegressionSummary:
    """Summary of regression comparison."""

    compared: bool = False
    golden_file: str | None = None
    total: int = 0
    within_tolerance: int = 0
    exceeded_tolerance: int = 0
    results: list[RegressionResult] = field(default_factory=list)

    def add(self, result: RegressionResult) -> None:
        """Add a regression result and update counts."""
        self.results.append(result)
        self.total += 1
        if result.status == Verdict.PASS:
            self.within_tolerance += 1
        else:
            self.exceeded_tolerance += 1

    def verdict(self) -> Verdict:
        """Return aggregate verdict."""
        if not self.compared:
            return Verdict.PASS  # No regression test = pass
        verdicts = [r.status for r in self.results]
        return Verdict.aggregate(verdicts)

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
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
    """
    Complete validation result for a CAM artifact set.

    This is the top-level result type that aggregates all metrics,
    invariants, assertions, and regression results.

    Note: Named CAMValidationResult to avoid conflict with existing
    validation.results.ValidationResult (used for IR-level checks).
    """

    version: str = "1.0.0"
    timestamp: str = ""
    input_file: str = ""
    verdict: Verdict = Verdict.PASS

    # Metrics (populated by metric extractors)
    metrics: dict[str, dict[str, Any]] = field(default_factory=dict)

    # Validation results
    invariants: InvariantSummary = field(default_factory=InvariantSummary)
    assertions: AssertionSummary = field(default_factory=AssertionSummary)
    regressions: RegressionSummary = field(default_factory=RegressionSummary)

    # Execution metadata
    execution_time_ms: float = 0.0
    verdict_reason: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def compute_verdict(self) -> Verdict:
        """Compute aggregate verdict from all checks."""
        verdicts = [
            self.invariants.verdict(),
            self.assertions.verdict(),
            self.regressions.verdict(),
        ]
        self.verdict = Verdict.aggregate(verdicts)
        self._set_verdict_reason()
        return self.verdict

    def _set_verdict_reason(self) -> None:
        """Set human-readable verdict reason."""
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
        """Convert to JSON-serializable dict matching the schema."""
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
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CAMValidationResult:
        """Deserialize from dict (for loading saved results)."""
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


def round_metric(value: float, precision: int = 4) -> float:
    """Round a metric value to specified precision for stability."""
    return round(value, precision)


def normalize_metric_dict(d: dict[str, Any], precision: int = 4) -> dict[str, Any]:
    """Recursively round all float values in a dict for stable comparison."""
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
