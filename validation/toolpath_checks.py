from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from cam.moves import Move, XYMove
from ir.removal_intent import Bounds2D
from validation.core import InvariantResult, Verdict

if TYPE_CHECKING:
    from cam.planner.passes import PassRecord


@dataclass(frozen=True)
class KeepoutViolation:
    move_index: int
    x: float
    y: float
    keepout_reason: str
    keepout_bounds: Bounds2D


@dataclass(frozen=True)
class ToolpathVerificationResult:
    keepout_violations: tuple[KeepoutViolation, ...]

    def has_violations(self) -> bool:
        return len(self.keepout_violations) > 0

    def format_errors(self) -> list[str]:
        errors = []
        for v in self.keepout_violations:
            errors.append(
                f"Toolpath enters keepout region '{v.keepout_reason}' at "
                f"({v.x:.2f}, {v.y:.2f}). Keepout bounds: "
                f"X[{v.keepout_bounds.x_min:.2f}, {v.keepout_bounds.x_max:.2f}], "
                f"Y[{v.keepout_bounds.y_min:.2f}, {v.keepout_bounds.y_max:.2f}]"
            )
        return errors

    def to_invariant_result(self) -> InvariantResult:
        n = len(self.keepout_violations)
        return InvariantResult(
            id="KEEPOUT-001",
            category="toolpath",
            artifact="gcode",
            description="Toolpath must not enter keepout regions",
            status=Verdict.FAIL if n > 0 else Verdict.PASS,
            checked=max(n, 1),
            passed=0 if n > 0 else 1,
            failed=n,
            failures=tuple(self.format_errors()),
        )


def _point_in_bounds(x: float, y: float, bounds: Bounds2D) -> bool:
    return bounds.x_min <= x <= bounds.x_max and bounds.y_min <= y <= bounds.y_max


def _keepout_dict_to_region(keepout: Mapping[str, Any]) -> tuple[Bounds2D, str]:
    bounds = Bounds2D(
        x_min=float(keepout.get("x_min", 0.0)),
        x_max=float(keepout.get("x_max", 0.0)),
        y_min=float(keepout.get("y_min", 0.0)),
        y_max=float(keepout.get("y_max", 0.0)),
    )
    reason = str(keepout.get("reason", "keepout"))
    return bounds, reason


def verify_toolpath_avoids_keepouts(
    moves: Sequence[Move],
    keepouts: Sequence[Mapping[str, Any]],
    tool_radius_mm: float = 0.0,
) -> ToolpathVerificationResult:
    if not keepouts:
        return ToolpathVerificationResult(keepout_violations=())

    keepout_regions = [_keepout_dict_to_region(k) for k in keepouts]

    expanded_regions = []
    for bounds, reason in keepout_regions:
        expanded = Bounds2D(
            x_min=bounds.x_min - tool_radius_mm,
            x_max=bounds.x_max + tool_radius_mm,
            y_min=bounds.y_min - tool_radius_mm,
            y_max=bounds.y_max + tool_radius_mm,
        )
        expanded_regions.append((expanded, bounds, reason))

    violations: list[KeepoutViolation] = []

    for i, move in enumerate(moves):
        if not isinstance(move, XYMove):
            continue

        x = move.x
        y = move.y

        if x is None or y is None:
            continue

        x = float(x)
        y = float(y)

        for expanded, original, reason in expanded_regions:
            if _point_in_bounds(x, y, expanded):
                violations.append(
                    KeepoutViolation(
                        move_index=i,
                        x=x,
                        y=y,
                        keepout_reason=reason,
                        keepout_bounds=original,
                    )
                )
                break

    return ToolpathVerificationResult(keepout_violations=tuple(violations))


def verify_passes_avoid_keepouts(
    passes: Sequence[PassRecord],
    keepouts: Sequence[Mapping[str, Any]],
) -> ToolpathVerificationResult:
    if not keepouts:
        return ToolpathVerificationResult(keepout_violations=())

    all_violations: list[KeepoutViolation] = []

    for p in passes:
        tool_radius = p.setup.tool.diameter / 2.0
        result = verify_toolpath_avoids_keepouts(p.moves, keepouts, tool_radius)
        all_violations.extend(result.keepout_violations)

    return ToolpathVerificationResult(keepout_violations=tuple(all_violations))
