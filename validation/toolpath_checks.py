from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from shapely.geometry import LineString, Point, box

from cam.moves import CutMove, Move, XYMove
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
    rapid_crossings: tuple[KeepoutViolation, ...] = ()
    final_xy: tuple[float | None, float | None] = (None, None)

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

    def format_warnings(self, safe_z_mm: float) -> list[str]:
        counts = Counter(v.keepout_reason for v in self.rapid_crossings)
        return [
            f"{count} rapid moves cross keepout '{reason}' at safe Z {safe_z_mm} mm; "
            "confirm the clamp is lower than safe Z"
            for reason, count in counts.items()
        ]

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
    *,
    initial_xy: tuple[float | None, float | None] = (None, None),
) -> ToolpathVerificationResult:
    if not keepouts:
        return ToolpathVerificationResult(keepout_violations=())

    keepout_regions = [_keepout_dict_to_region(k) for k in keepouts]

    expanded_regions = []
    for bounds, reason in keepout_regions:
        expanded = box(
            bounds.x_min - tool_radius_mm,
            bounds.y_min - tool_radius_mm,
            bounds.x_max + tool_radius_mm,
            bounds.y_max + tool_radius_mm,
        )
        expanded_regions.append((expanded, bounds, reason))

    violations: list[KeepoutViolation] = []
    rapid_crossings: list[KeepoutViolation] = []
    x, y = initial_xy

    for i, move in enumerate(moves):
        if not isinstance(move, XYMove):
            continue

        next_x = move.x if move.x is not None else x
        next_y = move.y if move.y is not None else y
        if next_x is None or next_y is None:
            if isinstance(move, CutMove):
                raise ValueError(f"Keepout verification: cutting move {i} has unknown XY position")
            x, y = next_x, next_y
            continue
        target = (next_x, next_y)
        segment = Point(target) if x is None or y is None or (x, y) == target else LineString([(x, y), target])

        for expanded, original, reason in expanded_regions:
            if segment.intersects(expanded):
                crossing = segment.intersection(expanded).representative_point()
                collection = violations if isinstance(move, CutMove) else rapid_crossings
                collection.append(
                    KeepoutViolation(
                        move_index=i,
                        x=crossing.x,
                        y=crossing.y,
                        keepout_reason=reason,
                        keepout_bounds=original,
                    )
                )
        x, y = target

    return ToolpathVerificationResult(tuple(violations), tuple(rapid_crossings), (x, y))


def verify_passes_avoid_keepouts(
    passes: Sequence[PassRecord],
    keepouts: Sequence[Mapping[str, Any]],
) -> ToolpathVerificationResult:
    if not keepouts:
        return ToolpathVerificationResult(keepout_violations=())

    all_violations: list[KeepoutViolation] = []
    all_rapid_crossings: list[KeepoutViolation] = []
    xy: tuple[float | None, float | None] = (None, None)

    for p in passes:
        tool_radius = p.setup.tool.diameter / 2.0
        result = verify_toolpath_avoids_keepouts(p.moves, keepouts, tool_radius, initial_xy=xy)
        all_violations.extend(result.keepout_violations)
        all_rapid_crossings.extend(result.rapid_crossings)
        xy = result.final_xy

    return ToolpathVerificationResult(tuple(all_violations), tuple(all_rapid_crossings), xy)
