

from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any

from validation.core import InvariantResult, Verdict
from validation.metrics.gcode_metrics import (
    GCodeMetrics,
    TabMetrics,
    extract_gcode_metrics,
    detect_tabs_from_content,
    G_CODE_PATTERN,
    M_CODE_PATTERN,
    X_PATTERN,
    Y_PATTERN,
    Z_PATTERN,
    F_PATTERN,
    T_PATTERN,
)


GCODE_INVARIANT_IDS = [
    "GCODE_PARSEABLE",
    "GCODE_SAFE_Z_RESPECTED",
    "GCODE_NO_NEGATIVE_FEED",
    "GCODE_Z_MONOTONIC_PLUNGE",
    "GCODE_MAX_STEPDOWN",
    "GCODE_XY_WITHIN_BOUNDS",
    "GCODE_SPINDLE_BEFORE_CUT",
    "GCODE_TOOL_DECLARED",
    "GCODE_ENDS_AT_SAFE",
    "GCODE_CONTINUOUS_PATH",
    "GCODE_TAB_PATTERN",
]


DEFAULT_SAFE_Z_MM = 5.0
DEFAULT_MAX_STEPDOWN_MM = 25.0
DEFAULT_SHEET_WIDTH_MM = 1220.0
DEFAULT_SHEET_HEIGHT_MM = 2440.0
DEFAULT_MARGIN_MM = 50.0
DEFAULT_JUMP_TOLERANCE_MM = 0.1


DEFAULT_JUMP_WARN_THRESHOLD_MM = 2750.0
DEFAULT_JUMP_FAIL_THRESHOLD_MM = 5000.0


def check_gcode_invariants(
    gcode_path: str | Path,
    metrics: GCodeMetrics | None = None,
    safe_z_mm: float | None = None,
    max_stepdown_mm: float = DEFAULT_MAX_STEPDOWN_MM,
    sheet_width_mm: float = DEFAULT_SHEET_WIDTH_MM,
    sheet_height_mm: float = DEFAULT_SHEET_HEIGHT_MM,
    margin_mm: float = DEFAULT_MARGIN_MM,
    jump_tolerance_mm: float = DEFAULT_JUMP_TOLERANCE_MM,
    jump_warn_threshold_mm: float = DEFAULT_JUMP_WARN_THRESHOLD_MM,
    jump_fail_threshold_mm: float = DEFAULT_JUMP_FAIL_THRESHOLD_MM,
) -> list[InvariantResult]:
    results: list[InvariantResult] = []
    gcode_path = Path(gcode_path)


    parse_result, lines = _check_parseable(gcode_path)
    results.append(parse_result)

    if parse_result.status == Verdict.FAIL:

        for inv_id in GCODE_INVARIANT_IDS[1:]:
            results.append(
                InvariantResult(
                    id=inv_id,
                    category="safety" if "SAFE" in inv_id or "SPINDLE" in inv_id else "structural",
                    artifact="gcode",
                    description=_get_invariant_description(inv_id),
                    status=Verdict.WARN,
                    details={"skipped": True, "reason": "G-code file not parseable"},
                )
            )
        return results


    if metrics is None:
        try:
            metrics = extract_gcode_metrics(gcode_path)
        except Exception as e:
            results.append(InvariantResult(
                id="GCODE_METRICS_ERROR",
                category="structural",
                artifact="gcode",
                description="Metrics extraction failed",
                status=Verdict.FAIL,
                details={"error": str(e)},
            ))
            return results


    if safe_z_mm is None:
        safe_z_mm = metrics.z_profile.safe_z_mm if metrics.z_profile.safe_z_mm > 0 else DEFAULT_SAFE_Z_MM


    results.append(_check_safe_z_respected(lines, safe_z_mm))


    results.append(_check_no_negative_feed(lines, metrics))


    results.append(_check_z_monotonic_plunge(lines))


    results.append(_check_max_stepdown(lines, max_stepdown_mm))


    results.append(_check_xy_within_bounds(
        metrics, sheet_width_mm, sheet_height_mm, margin_mm
    ))


    results.append(_check_spindle_before_cut(lines))


    results.append(_check_tool_declared(lines))


    results.append(_check_ends_at_safe(lines, safe_z_mm))


    results.append(_check_continuous_path(
        lines, jump_tolerance_mm, jump_warn_threshold_mm, jump_fail_threshold_mm
    ))


    results.append(_check_tab_pattern(metrics.tabs))

    return results


def check_gcode_invariants_from_content(
    gcode_content: str,
    metrics: GCodeMetrics | None = None,
    safe_z_mm: float | None = None,
    max_stepdown_mm: float = DEFAULT_MAX_STEPDOWN_MM,
    sheet_width_mm: float = DEFAULT_SHEET_WIDTH_MM,
    sheet_height_mm: float = DEFAULT_SHEET_HEIGHT_MM,
    margin_mm: float = DEFAULT_MARGIN_MM,
    jump_tolerance_mm: float = DEFAULT_JUMP_TOLERANCE_MM,
    jump_warn_threshold_mm: float = DEFAULT_JUMP_WARN_THRESHOLD_MM,
    jump_fail_threshold_mm: float = DEFAULT_JUMP_FAIL_THRESHOLD_MM,
) -> list[InvariantResult]:
    results: list[InvariantResult] = []


    parse_result, lines = _check_parseable_content(gcode_content)
    results.append(parse_result)

    if parse_result.status == Verdict.FAIL:

        for inv_id in GCODE_INVARIANT_IDS[1:]:
            results.append(
                InvariantResult(
                    id=inv_id,
                    category="safety" if "SAFE" in inv_id or "SPINDLE" in inv_id else "structural",
                    artifact="gcode",
                    description=_get_invariant_description(inv_id),
                    status=Verdict.WARN,
                    details={"skipped": True, "reason": "G-code content not parseable"},
                )
            )
        return results


    if metrics is None:
        try:
            from validation.metrics.gcode_metrics import extract_gcode_metrics_from_content
            metrics = extract_gcode_metrics_from_content(gcode_content)
        except Exception as e:
            results.append(InvariantResult(
                id="GCODE_METRICS_ERROR",
                category="structural",
                artifact="gcode",
                description="Metrics extraction failed",
                status=Verdict.FAIL,
                details={"error": str(e)},
            ))
            return results


    if safe_z_mm is None:
        safe_z_mm = metrics.z_profile.safe_z_mm if metrics.z_profile.safe_z_mm > 0 else DEFAULT_SAFE_Z_MM


    results.append(_check_safe_z_respected(lines, safe_z_mm))


    results.append(_check_no_negative_feed(lines, metrics))


    results.append(_check_z_monotonic_plunge(lines))


    results.append(_check_max_stepdown(lines, max_stepdown_mm))


    results.append(_check_xy_within_bounds(
        metrics, sheet_width_mm, sheet_height_mm, margin_mm
    ))


    results.append(_check_spindle_before_cut(lines))


    results.append(_check_tool_declared(lines))


    results.append(_check_ends_at_safe(lines, safe_z_mm))


    results.append(_check_continuous_path(
        lines, jump_tolerance_mm, jump_warn_threshold_mm, jump_fail_threshold_mm
    ))


    results.append(_check_tab_pattern(metrics.tabs))

    return results


def _get_invariant_description(inv_id: str) -> str:
    descriptions = {
        "GCODE_PARSEABLE": "All lines parse as valid G-code",
        "GCODE_SAFE_Z_RESPECTED": "Rapids (G0) only at or above safe_z",
        "GCODE_NO_NEGATIVE_FEED": "Feed rates always positive",
        "GCODE_Z_MONOTONIC_PLUNGE": "Z decreases monotonically during plunge",
        "GCODE_MAX_STEPDOWN": "Single Z step never exceeds max_stepdown",
        "GCODE_XY_WITHIN_BOUNDS": "All XY positions within sheet + margin",
        "GCODE_SPINDLE_BEFORE_CUT": "Spindle on (M3/M4) before any G1 at negative Z",
        "GCODE_TOOL_DECLARED": "Tool number declared before use",
        "GCODE_ENDS_AT_SAFE": "Program ends with Z at safe height",
        "GCODE_CONTINUOUS_PATH": "No discontinuous jumps during cutting moves",
        "GCODE_TAB_PATTERN": "Tabs occur at max cutting depth with consistent heights",
    }
    return descriptions.get(inv_id, inv_id)


def _check_parseable(gcode_path: Path) -> tuple[InvariantResult, list[str]]:
    try:
        if not gcode_path.exists():
            return (
                InvariantResult(
                    id="GCODE_PARSEABLE",
                    category="structural",
                    artifact="gcode",
                    description="All lines parse as valid G-code",
                    status=Verdict.FAIL,
                    checked=1,
                    failed=1,
                    failures=(f"File not found: {gcode_path}",),
                ),
                [],
            )

        with open(gcode_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        if not lines:
            return (
                InvariantResult(
                    id="GCODE_PARSEABLE",
                    category="structural",
                    artifact="gcode",
                    description="All lines parse as valid G-code",
                    status=Verdict.FAIL,
                    checked=1,
                    failed=1,
                    failures=("File is empty",),
                ),
                [],
            )


        invalid_lines: list[str] = []
        checked = 0


        token_pattern = re.compile(
            r"[GMXYZIJKRABCFSTNOQPLHDEUVW]\s*[+-]?\d*\.?\d+",
            re.IGNORECASE
        )

        for i, line in enumerate(lines, 1):
            line = line.strip()
            if not line:
                continue

            checked += 1


            if line.startswith("(") and line.endswith(")"):
                continue
            if line.startswith(";"):
                continue
            if line == "%":
                continue


            line_no_comment = line
            if "(" in line:
                line_no_comment = line[:line.index("(")].strip()
            if ";" in line_no_comment:
                line_no_comment = line_no_comment[:line_no_comment.index(";")].strip()


            if not token_pattern.search(line_no_comment):
                if len(invalid_lines) < 5:
                    invalid_lines.append(f"Line {i}: No valid G-code token: {line[:50]}")
                continue


            valid_chars = re.compile(
                r"^[GMTFSXYZIJKRABCDEHLNOPQRUVW\d.\-+\s()]+$",
                re.IGNORECASE
            )
            if not valid_chars.match(line_no_comment):
                if len(invalid_lines) < 5:
                    invalid_lines.append(f"Line {i}: Invalid characters: {line[:50]}")

        if invalid_lines:
            return (
                InvariantResult(
                    id="GCODE_PARSEABLE",
                    category="structural",
                    artifact="gcode",
                    description="All lines parse as valid G-code",
                    status=Verdict.FAIL,
                    checked=checked,
                    passed=checked - len(invalid_lines),
                    failed=len(invalid_lines),
                    failures=tuple(invalid_lines),
                ),
                lines,
            )

        return (
            InvariantResult(
                id="GCODE_PARSEABLE",
                category="structural",
                artifact="gcode",
                description="All lines parse as valid G-code",
                status=Verdict.PASS,
                checked=checked,
                passed=checked,
            ),
            lines,
        )

    except Exception as e:
        return (
            InvariantResult(
                id="GCODE_PARSEABLE",
                category="structural",
                artifact="gcode",
                description="All lines parse as valid G-code",
                status=Verdict.FAIL,
                checked=1,
                failed=1,
                failures=(f"Read error: {e}",),
            ),
            [],
        )


def _check_parseable_content(gcode_content: str) -> tuple[InvariantResult, list[str]]:
    try:
        lines = gcode_content.splitlines(keepends=True)

        if not lines:
            return (
                InvariantResult(
                    id="GCODE_PARSEABLE",
                    category="structural",
                    artifact="gcode",
                    description="All lines parse as valid G-code",
                    status=Verdict.FAIL,
                    checked=1,
                    failed=1,
                    failures=("Content is empty",),
                ),
                [],
            )


        invalid_lines: list[str] = []
        checked = 0


        token_pattern = re.compile(
            r"[GMXYZIJKRABCFSTNOQPLHDEUVW]\s*[+-]?\d*\.?\d+",
            re.IGNORECASE
        )

        for i, line in enumerate(lines, 1):
            line = line.strip()
            if not line:
                continue

            checked += 1


            if line.startswith("(") and line.endswith(")"):
                continue
            if line.startswith(";"):
                continue
            if line == "%":
                continue


            line_no_comment = line
            if "(" in line:
                line_no_comment = line[:line.index("(")].strip()
            if ";" in line_no_comment:
                line_no_comment = line_no_comment[:line_no_comment.index(";")].strip()


            if not token_pattern.search(line_no_comment):
                if len(invalid_lines) < 5:
                    invalid_lines.append(f"Line {i}: No valid G-code token: {line[:50]}")
                continue


            valid_chars = re.compile(
                r"^[GMTFSXYZIJKRABCDEHLNOPQRUVW\d.\-+\s()]+$",
                re.IGNORECASE
            )
            if not valid_chars.match(line_no_comment):
                if len(invalid_lines) < 5:
                    invalid_lines.append(f"Line {i}: Invalid characters: {line[:50]}")

        if invalid_lines:
            return (
                InvariantResult(
                    id="GCODE_PARSEABLE",
                    category="structural",
                    artifact="gcode",
                    description="All lines parse as valid G-code",
                    status=Verdict.FAIL,
                    checked=checked,
                    passed=checked - len(invalid_lines),
                    failed=len(invalid_lines),
                    failures=tuple(invalid_lines),
                ),
                lines,
            )

        return (
            InvariantResult(
                id="GCODE_PARSEABLE",
                category="structural",
                artifact="gcode",
                description="All lines parse as valid G-code",
                status=Verdict.PASS,
                checked=checked,
                passed=checked,
            ),
            lines,
        )

    except Exception as e:
        return (
            InvariantResult(
                id="GCODE_PARSEABLE",
                category="structural",
                artifact="gcode",
                description="All lines parse as valid G-code",
                status=Verdict.FAIL,
                checked=1,
                failed=1,
                failures=(f"Parse error: {e}",),
            ),
            [],
        )


def _check_safe_z_respected(lines: list[str], safe_z_mm: float) -> InvariantResult:
    checked = 0
    failures: list[str] = []
    current_z = 0.0
    motion_mode = 0

    for i, line in enumerate(lines, 1):
        line = line.strip()
        if not line or line.startswith("(") or line.startswith(";"):
            continue


        g_match = G_CODE_PATTERN.search(line)
        if g_match:
            g_code = int(g_match.group(1))
            if g_code in (0, 1, 2, 3):
                motion_mode = g_code


        z_match = Z_PATTERN.search(line)
        if z_match:
            current_z = float(z_match.group(1))


        has_motion = (
            z_match is not None or
            X_PATTERN.search(line) is not None or
            Y_PATTERN.search(line) is not None
        )

        is_rapid_line = (g_match and int(g_match.group(1)) == 0) or \
                        (motion_mode == 0 and has_motion and not g_match)

        if is_rapid_line:
            checked += 1

            if current_z < safe_z_mm - 0.001:
                if len(failures) < 5:
                    failures.append(
                        f"Line {i}: G0 rapid at Z={current_z:.3f} (safe_z={safe_z_mm})"
                    )

    if checked == 0:
        return InvariantResult(
            id="GCODE_SAFE_Z_RESPECTED",
            category="safety",
            artifact="gcode",
            description="Rapids (G0) only at or above safe_z",
            status=Verdict.PASS,
            checked=0,
            passed=0,
            details={"note": "No G0 rapids found"},
        )

    status = Verdict.PASS if not failures else Verdict.FAIL
    return InvariantResult(
        id="GCODE_SAFE_Z_RESPECTED",
        category="safety",
        artifact="gcode",
        description="Rapids (G0) only at or above safe_z",
        status=status,
        checked=checked,
        passed=checked - len(failures),
        failed=len(failures),
        failures=tuple(failures),
        details={"safe_z_mm": safe_z_mm},
    )


def _check_no_negative_feed(lines: list[str], metrics: GCodeMetrics) -> InvariantResult:
    checked = 0
    failures: list[str] = []

    for i, line in enumerate(lines, 1):
        line = line.strip()
        if not line or line.startswith("(") or line.startswith(";"):
            continue

        f_match = F_PATTERN.search(line)
        if f_match:
            checked += 1
            feed = float(f_match.group(1))
            if feed <= 0:
                if len(failures) < 5:
                    failures.append(f"Line {i}: Invalid feed rate F{feed}")

    if checked == 0:
        return InvariantResult(
            id="GCODE_NO_NEGATIVE_FEED",
            category="structural",
            artifact="gcode",
            description="Feed rates always positive",
            status=Verdict.PASS,
            checked=0,
            passed=0,
            details={"note": "No feed rates found"},
        )

    status = Verdict.PASS if not failures else Verdict.FAIL
    return InvariantResult(
        id="GCODE_NO_NEGATIVE_FEED",
        category="structural",
        artifact="gcode",
        description="Feed rates always positive",
        status=status,
        checked=checked,
        passed=checked - len(failures),
        failed=len(failures),
        failures=tuple(failures),
        details={"feed_rates_used": metrics.feeds.feed_rates_used},
    )


def _check_z_monotonic_plunge(lines: list[str]) -> InvariantResult:
    checked = 0
    failures: list[str] = []

    current_z = 0.0
    plunge_start_z: float | None = None
    last_plunge_z: float | None = None
    in_plunge = False

    for i, line in enumerate(lines, 1):
        line = line.strip()
        if not line or line.startswith("(") or line.startswith(";"):
            continue


        g_match = G_CODE_PATTERN.search(line)
        is_feed_move = g_match and int(g_match.group(1)) in (1, 2, 3)

        z_match = Z_PATTERN.search(line)
        if z_match:
            new_z = float(z_match.group(1))


            if is_feed_move:
                if new_z < current_z:

                    if not in_plunge:
                        in_plunge = True
                        plunge_start_z = current_z
                        last_plunge_z = new_z
                        checked += 1
                    else:

                        if new_z > last_plunge_z:
                            if len(failures) < 5:
                                failures.append(
                                    f"Line {i}: Non-monotonic plunge Z={new_z:.3f} "
                                    f"(previous Z={last_plunge_z:.3f})"
                                )
                        last_plunge_z = new_z
                elif new_z > current_z:

                    in_plunge = False
                    plunge_start_z = None
                    last_plunge_z = None


            elif g_match and int(g_match.group(1)) == 0:
                in_plunge = False
                plunge_start_z = None
                last_plunge_z = None

            current_z = new_z

    if checked == 0:
        return InvariantResult(
            id="GCODE_Z_MONOTONIC_PLUNGE",
            category="structural",
            artifact="gcode",
            description="Z decreases monotonically during plunge",
            status=Verdict.PASS,
            checked=0,
            passed=0,
            details={"note": "No plunge sequences detected"},
        )

    status = Verdict.PASS if not failures else Verdict.FAIL
    return InvariantResult(
        id="GCODE_Z_MONOTONIC_PLUNGE",
        category="structural",
        artifact="gcode",
        description="Z decreases monotonically during plunge",
        status=status,
        checked=checked,
        passed=checked if not failures else checked - len(failures),
        failed=len(failures),
        failures=tuple(failures),
    )


def _check_max_stepdown(lines: list[str], max_stepdown_mm: float) -> InvariantResult:
    checked = 0
    failures: list[str] = []
    current_z = 0.0
    max_observed_stepdown = 0.0

    for i, line in enumerate(lines, 1):
        line = line.strip()
        if not line or line.startswith("(") or line.startswith(";"):
            continue


        g_match = G_CODE_PATTERN.search(line)
        is_feed_move = g_match and int(g_match.group(1)) == 1

        z_match = Z_PATTERN.search(line)
        if z_match:
            new_z = float(z_match.group(1))
            stepdown = current_z - new_z


            if stepdown > 0 and is_feed_move:
                checked += 1
                max_observed_stepdown = max(max_observed_stepdown, stepdown)

                if stepdown > max_stepdown_mm + 0.001:
                    if len(failures) < 5:
                        failures.append(
                            f"Line {i}: Stepdown {stepdown:.3f}mm exceeds max {max_stepdown_mm}mm"
                        )

            current_z = new_z

    if checked == 0:
        return InvariantResult(
            id="GCODE_MAX_STEPDOWN",
            category="safety",
            artifact="gcode",
            description="Single Z step never exceeds max_stepdown",
            status=Verdict.PASS,
            checked=0,
            passed=0,
            details={"note": "No downward Z moves found"},
        )

    status = Verdict.PASS if not failures else Verdict.FAIL
    return InvariantResult(
        id="GCODE_MAX_STEPDOWN",
        category="safety",
        artifact="gcode",
        description="Single Z step never exceeds max_stepdown",
        status=status,
        checked=checked,
        passed=checked - len(failures),
        failed=len(failures),
        failures=tuple(failures),
        details={
            "max_stepdown_mm": max_stepdown_mm,
            "max_observed_stepdown_mm": round(max_observed_stepdown, 4),
        },
    )


def _check_xy_within_bounds(
    metrics: GCodeMetrics,
    sheet_width_mm: float,
    sheet_height_mm: float,
    margin_mm: float,
) -> InvariantResult:
    bounds = metrics.xy_bounds
    failures: list[str] = []


    x_min_allowed = -margin_mm
    x_max_allowed = sheet_width_mm + margin_mm
    y_min_allowed = -margin_mm
    y_max_allowed = sheet_height_mm + margin_mm


    if (bounds.x_min == float("inf") or bounds.x_max == float("-inf") or
        bounds.y_min == float("inf") or bounds.y_max == float("-inf")):
        return InvariantResult(
            id="GCODE_XY_WITHIN_BOUNDS",
            category="safety",
            artifact="gcode",
            description="All XY positions within sheet + margin",
            status=Verdict.PASS,
            checked=0,
            passed=0,
            details={"note": "No XY coordinates found"},
        )


    if bounds.x_min < x_min_allowed:
        failures.append(f"X_min ({bounds.x_min:.2f}) < allowed ({x_min_allowed:.2f})")
    if bounds.x_max > x_max_allowed:
        failures.append(f"X_max ({bounds.x_max:.2f}) > allowed ({x_max_allowed:.2f})")
    if bounds.y_min < y_min_allowed:
        failures.append(f"Y_min ({bounds.y_min:.2f}) < allowed ({y_min_allowed:.2f})")
    if bounds.y_max > y_max_allowed:
        failures.append(f"Y_max ({bounds.y_max:.2f}) > allowed ({y_max_allowed:.2f})")

    status = Verdict.PASS if not failures else Verdict.FAIL
    return InvariantResult(
        id="GCODE_XY_WITHIN_BOUNDS",
        category="safety",
        artifact="gcode",
        description="All XY positions within sheet + margin",
        status=status,
        checked=4,
        passed=4 - len(failures),
        failed=len(failures),
        failures=tuple(failures),
        details={
            "sheet_width_mm": sheet_width_mm,
            "sheet_height_mm": sheet_height_mm,
            "margin_mm": margin_mm,
            "xy_bounds": {
                "x_min": bounds.x_min if bounds.x_min != float("inf") else None,
                "x_max": bounds.x_max if bounds.x_max != float("-inf") else None,
                "y_min": bounds.y_min if bounds.y_min != float("inf") else None,
                "y_max": bounds.y_max if bounds.y_max != float("-inf") else None,
            },
        },
    )


def _check_spindle_before_cut(lines: list[str]) -> InvariantResult:
    checked = 0
    failures: list[str] = []
    spindle_on = False
    current_z = 0.0

    for i, line in enumerate(lines, 1):
        line_upper = line.strip().upper()
        if not line_upper or line_upper.startswith("(") or line_upper.startswith(";"):
            continue


        m_match = M_CODE_PATTERN.search(line_upper)
        if m_match:
            m_code = int(m_match.group(1))
            if m_code in (3, 4):
                spindle_on = True
            elif m_code == 5:
                spindle_on = False


        z_match = Z_PATTERN.search(line_upper)
        if z_match:
            current_z = float(z_match.group(1))


        g_match = G_CODE_PATTERN.search(line_upper)
        if g_match and int(g_match.group(1)) == 1:

            if current_z < -0.001:
                checked += 1
                if not spindle_on:
                    if len(failures) < 5:
                        failures.append(
                            f"Line {i}: G1 cutting move at Z={current_z:.3f} without spindle on"
                        )

    if checked == 0:
        return InvariantResult(
            id="GCODE_SPINDLE_BEFORE_CUT",
            category="safety",
            artifact="gcode",
            description="Spindle on (M3/M4) before any G1 at negative Z",
            status=Verdict.PASS,
            checked=0,
            passed=0,
            details={"note": "No cutting moves at negative Z found"},
        )

    status = Verdict.PASS if not failures else Verdict.FAIL
    return InvariantResult(
        id="GCODE_SPINDLE_BEFORE_CUT",
        category="safety",
        artifact="gcode",
        description="Spindle on (M3/M4) before any G1 at negative Z",
        status=status,
        checked=checked,
        passed=checked - len(failures),
        failed=len(failures),
        failures=tuple(failures),
    )


def _check_tool_declared(lines: list[str]) -> InvariantResult:
    checked = 0
    failures: list[str] = []
    declared_tools: set[int] = set()
    current_tool: int | None = None

    for i, line in enumerate(lines, 1):
        line = line.strip()
        if not line or line.startswith("(") or line.startswith(";"):
            continue


        t_match = T_PATTERN.search(line)
        if t_match:
            tool_num = int(t_match.group(1))
            declared_tools.add(tool_num)
            current_tool = tool_num
            checked += 1


        m_match = M_CODE_PATTERN.search(line)
        if m_match and int(m_match.group(1)) == 6:
            checked += 1
            if current_tool is None:
                if len(failures) < 5:
                    failures.append(f"Line {i}: M6 tool change without prior tool declaration")

    if checked == 0:
        return InvariantResult(
            id="GCODE_TOOL_DECLARED",
            category="structural",
            artifact="gcode",
            description="Tool number declared before use",
            status=Verdict.PASS,
            checked=0,
            passed=0,
            details={"note": "No tool commands found"},
        )

    status = Verdict.PASS if not failures else Verdict.FAIL
    return InvariantResult(
        id="GCODE_TOOL_DECLARED",
        category="structural",
        artifact="gcode",
        description="Tool number declared before use",
        status=status,
        checked=checked,
        passed=checked - len(failures),
        failed=len(failures),
        failures=tuple(failures),
        details={"declared_tools": sorted(declared_tools)},
    )


def _check_ends_at_safe(lines: list[str], safe_z_mm: float) -> InvariantResult:
    final_z: float | None = None


    for line in lines:
        line = line.strip()
        if not line or line.startswith("(") or line.startswith(";"):
            continue

        z_match = Z_PATTERN.search(line)
        if z_match:
            final_z = float(z_match.group(1))

    if final_z is None:
        return InvariantResult(
            id="GCODE_ENDS_AT_SAFE",
            category="safety",
            artifact="gcode",
            description="Program ends with Z at safe height",
            status=Verdict.WARN,
            checked=1,
            failed=1,
            failures=("No Z position found in file",),
        )

    if final_z >= safe_z_mm - 0.001:
        return InvariantResult(
            id="GCODE_ENDS_AT_SAFE",
            category="safety",
            artifact="gcode",
            description="Program ends with Z at safe height",
            status=Verdict.PASS,
            checked=1,
            passed=1,
            details={
                "final_z_mm": round(final_z, 4),
                "safe_z_mm": safe_z_mm,
            },
        )
    else:
        return InvariantResult(
            id="GCODE_ENDS_AT_SAFE",
            category="safety",
            artifact="gcode",
            description="Program ends with Z at safe height",
            status=Verdict.FAIL,
            checked=1,
            failed=1,
            failures=(f"Final Z={final_z:.3f} is below safe_z={safe_z_mm}",),
            details={
                "final_z_mm": round(final_z, 4),
                "safe_z_mm": safe_z_mm,
            },
        )


def _check_continuous_path(
    lines: list[str],
    jump_tolerance_mm: float,
    warn_threshold_mm: float,
    fail_threshold_mm: float,
) -> InvariantResult:
    checked = 0
    failures: list[str] = []
    warnings: list[str] = []

    current_x = 0.0
    current_y = 0.0
    current_z = 0.0
    in_cut = False
    max_jump = 0.0

    for i, line in enumerate(lines, 1):
        line = line.strip()
        if not line or line.startswith("(") or line.startswith(";"):
            continue


        x_match = X_PATTERN.search(line)
        y_match = Y_PATTERN.search(line)
        z_match = Z_PATTERN.search(line)
        g_match = G_CODE_PATTERN.search(line)

        new_x = float(x_match.group(1)) if x_match else current_x
        new_y = float(y_match.group(1)) if y_match else current_y
        new_z = float(z_match.group(1)) if z_match else current_z


        is_feed_move = g_match and int(g_match.group(1)) in (1, 2, 3)
        is_rapid = g_match and int(g_match.group(1)) == 0


        if is_rapid:
            in_cut = False
            current_x = new_x
            current_y = new_y
            current_z = new_z
            continue


        was_in_cut = in_cut
        if is_feed_move and new_z < -0.001:
            in_cut = True
        elif new_z >= -0.001:
            in_cut = False


        if in_cut and was_in_cut and is_feed_move:

            has_xy_motion = x_match is not None or y_match is not None
            has_z_motion = z_match is not None and abs(new_z - current_z) > 0.001


            if has_xy_motion and not has_z_motion:
                xy_distance = math.sqrt((new_x - current_x)**2 + (new_y - current_y)**2)


                is_arc = g_match and int(g_match.group(1)) in (2, 3)

                if not is_arc and xy_distance > jump_tolerance_mm:
                    checked += 1
                    max_jump = max(max_jump, xy_distance)


                    if xy_distance > fail_threshold_mm:
                        if len(failures) < 5:
                            failures.append(
                                f"Line {i}: XY jump of {xy_distance:.2f}mm during cut (exceeds {fail_threshold_mm}mm)"
                            )
                    elif xy_distance > warn_threshold_mm:
                        if len(warnings) < 5:
                            warnings.append(
                                f"Line {i}: Large XY move of {xy_distance:.2f}mm during cut"
                            )

        current_x = new_x
        current_y = new_y
        current_z = new_z

    if checked == 0 and not failures and not warnings:
        return InvariantResult(
            id="GCODE_CONTINUOUS_PATH",
            category="structural",
            artifact="gcode",
            description="No discontinuous jumps during cutting moves",
            status=Verdict.PASS,
            checked=0,
            passed=0,
            details={"note": "No cutting move sequences to check"},
        )


    if failures:
        status = Verdict.FAIL
    elif warnings:
        status = Verdict.WARN
    else:
        status = Verdict.PASS

    return InvariantResult(
        id="GCODE_CONTINUOUS_PATH",
        category="structural",
        artifact="gcode",
        description="No discontinuous jumps during cutting moves",
        status=status,
        checked=max(checked, 1),
        passed=max(checked, 1) - len(failures) - len(warnings),
        failed=len(failures),
        failures=tuple(failures + warnings),
        details={
            "jump_tolerance_mm": jump_tolerance_mm,
            "warn_threshold_mm": warn_threshold_mm,
            "fail_threshold_mm": fail_threshold_mm,
            "max_observed_jump_mm": round(max_jump, 4) if max_jump > 0 else None,
            "warning_count": len(warnings),
            "failure_count": len(failures),
        },
    )


def _check_tab_pattern(
    tabs: TabMetrics,
    height_tolerance_mm: float = 0.5,
) -> InvariantResult:
    if tabs.detected_count == 0:
        return InvariantResult(
            id="GCODE_TAB_PATTERN",
            category="structural",
            artifact="gcode",
            description="Tabs occur at max cutting depth with consistent heights",
            status=Verdict.PASS,
            checked=0,
            passed=0,
            details={
                "detected_count": 0,
                "note": "No tabs detected in G-code",
            },
        )

    failures: list[str] = []
    warnings: list[str] = []
    checked = 0

    checked += 1
    if not tabs.tabs_at_max_depth:
        failures.append("Tabs detected on non-final passes (not at max cutting depth)")

    if tabs.tab_heights_mm:
        checked += 1
        min_height = min(tabs.tab_heights_mm)
        max_height = max(tabs.tab_heights_mm)

        if max_height - min_height > height_tolerance_mm:
            warnings.append(
                f"Inconsistent tab heights: min={min_height:.2f}mm, max={max_height:.2f}mm"
            )

        checked += 1
        avg_height = sum(tabs.tab_heights_mm) / len(tabs.tab_heights_mm)
        if avg_height <= 0:
            failures.append(f"Invalid tab height: {avg_height:.2f}mm (must be positive)")
        elif avg_height > 20.0:
            warnings.append(f"Unusually large tab height: {avg_height:.2f}mm")

    if failures:
        status = Verdict.FAIL
    elif warnings:
        status = Verdict.WARN
    else:
        status = Verdict.PASS

    return InvariantResult(
        id="GCODE_TAB_PATTERN",
        category="structural",
        artifact="gcode",
        description="Tabs occur at max cutting depth with consistent heights",
        status=status,
        checked=checked,
        passed=checked - len(failures) - len(warnings),
        failed=len(failures),
        failures=tuple(failures + warnings),
        details={
            "detected_count": tabs.detected_count,
            "tab_heights_mm": tabs.tab_heights_mm,
            "max_cutting_depth_mm": tabs.max_cutting_depth_mm,
            "tabs_at_max_depth": tabs.tabs_at_max_depth,
            "height_tolerance_mm": height_tolerance_mm,
        },
    )
