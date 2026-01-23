# validation/invariants/gcode_invariants.py - G-code invariant checks
#
# Implements safety and structural invariants for G-code files.
# See docs/cam_validation_plan.md Section 4.3 for invariant definitions.

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


# Invariant IDs
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


# Default configuration values
DEFAULT_SAFE_Z_MM = 5.0  # Default safe Z height
DEFAULT_MAX_STEPDOWN_MM = 25.0  # Default max single plunge depth (accommodates 19mm sheets)
DEFAULT_SHEET_WIDTH_MM = 1220.0  # Default sheet width (4' panel)
DEFAULT_SHEET_HEIGHT_MM = 2440.0  # Default sheet height (8' panel)
DEFAULT_MARGIN_MM = 50.0  # Default margin outside sheet bounds
DEFAULT_JUMP_TOLERANCE_MM = 0.1  # Tolerance for detecting path discontinuities
# Jump thresholds for continuity check (configurable)
# - warn_threshold: jumps above this emit a warning (default: sheet diagonal ~2750mm)
# - fail_threshold: jumps above this are considered failures (default: 5000mm, clearly broken)
DEFAULT_JUMP_WARN_THRESHOLD_MM = 2750.0  # Approx diagonal of 4x8 sheet
DEFAULT_JUMP_FAIL_THRESHOLD_MM = 5000.0  # Clearly impossible jump


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
    """
    Check all G-code invariants.

    Args:
        gcode_path: Path to the G-code file (.nc)
        metrics: Pre-computed GCodeMetrics (optional, will extract if not provided)
        safe_z_mm: Expected safe Z height (if None, uses detected safe_z from metrics)
        max_stepdown_mm: Maximum allowed single Z step
        sheet_width_mm: Sheet width for bounds checking
        sheet_height_mm: Sheet height for bounds checking
        margin_mm: Allowed margin outside sheet bounds
        jump_tolerance_mm: Minimum distance to consider as a "jump"
        jump_warn_threshold_mm: XY jump distance that triggers a warning
        jump_fail_threshold_mm: XY jump distance that triggers a failure

    Returns:
        List of InvariantResult for each check
    """
    results: list[InvariantResult] = []
    gcode_path = Path(gcode_path)

    # 1. GCODE_PARSEABLE - must parse without errors
    parse_result, lines = _check_parseable(gcode_path)
    results.append(parse_result)

    if parse_result.status == Verdict.FAIL:
        # Can't continue if file doesn't parse - add skipped results for remaining invariants
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

    # Extract metrics if not provided
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

    # Use detected safe_z if not provided
    if safe_z_mm is None:
        safe_z_mm = metrics.z_profile.safe_z_mm if metrics.z_profile.safe_z_mm > 0 else DEFAULT_SAFE_Z_MM

    # 2. GCODE_SAFE_Z_RESPECTED
    results.append(_check_safe_z_respected(lines, safe_z_mm))

    # 3. GCODE_NO_NEGATIVE_FEED
    results.append(_check_no_negative_feed(lines, metrics))

    # 4. GCODE_Z_MONOTONIC_PLUNGE
    results.append(_check_z_monotonic_plunge(lines))

    # 5. GCODE_MAX_STEPDOWN
    results.append(_check_max_stepdown(lines, max_stepdown_mm))

    # 6. GCODE_XY_WITHIN_BOUNDS
    results.append(_check_xy_within_bounds(
        metrics, sheet_width_mm, sheet_height_mm, margin_mm
    ))

    # 7. GCODE_SPINDLE_BEFORE_CUT
    results.append(_check_spindle_before_cut(lines))

    # 8. GCODE_TOOL_DECLARED
    results.append(_check_tool_declared(lines))

    # 9. GCODE_ENDS_AT_SAFE
    results.append(_check_ends_at_safe(lines, safe_z_mm))

    # 10. GCODE_CONTINUOUS_PATH
    results.append(_check_continuous_path(
        lines, jump_tolerance_mm, jump_warn_threshold_mm, jump_fail_threshold_mm
    ))

    # 11. GCODE_TAB_PATTERN (uses pre-computed tab metrics)
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
    """
    Check all G-code invariants from content string.

    Args:
        gcode_content: G-code content as string
        metrics: Pre-computed GCodeMetrics (optional, will extract if not provided)
        safe_z_mm: Expected safe Z height (if None, uses detected safe_z from metrics)
        max_stepdown_mm: Maximum allowed single Z step
        sheet_width_mm: Sheet width for bounds checking
        sheet_height_mm: Sheet height for bounds checking
        margin_mm: Allowed margin outside sheet bounds
        jump_tolerance_mm: Minimum distance to consider as a "jump"
        jump_warn_threshold_mm: XY jump distance that triggers a warning
        jump_fail_threshold_mm: XY jump distance that triggers a failure

    Returns:
        List of InvariantResult for each check
    """
    results: list[InvariantResult] = []

    # 1. GCODE_PARSEABLE - must parse without errors
    parse_result, lines = _check_parseable_content(gcode_content)
    results.append(parse_result)

    if parse_result.status == Verdict.FAIL:
        # Can't continue if content doesn't parse - add skipped results for remaining invariants
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

    # Extract metrics if not provided
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

    # Use detected safe_z if not provided
    if safe_z_mm is None:
        safe_z_mm = metrics.z_profile.safe_z_mm if metrics.z_profile.safe_z_mm > 0 else DEFAULT_SAFE_Z_MM

    # 2. GCODE_SAFE_Z_RESPECTED
    results.append(_check_safe_z_respected(lines, safe_z_mm))

    # 3. GCODE_NO_NEGATIVE_FEED
    results.append(_check_no_negative_feed(lines, metrics))

    # 4. GCODE_Z_MONOTONIC_PLUNGE
    results.append(_check_z_monotonic_plunge(lines))

    # 5. GCODE_MAX_STEPDOWN
    results.append(_check_max_stepdown(lines, max_stepdown_mm))

    # 6. GCODE_XY_WITHIN_BOUNDS
    results.append(_check_xy_within_bounds(
        metrics, sheet_width_mm, sheet_height_mm, margin_mm
    ))

    # 7. GCODE_SPINDLE_BEFORE_CUT
    results.append(_check_spindle_before_cut(lines))

    # 8. GCODE_TOOL_DECLARED
    results.append(_check_tool_declared(lines))

    # 9. GCODE_ENDS_AT_SAFE
    results.append(_check_ends_at_safe(lines, safe_z_mm))

    # 10. GCODE_CONTINUOUS_PATH
    results.append(_check_continuous_path(
        lines, jump_tolerance_mm, jump_warn_threshold_mm, jump_fail_threshold_mm
    ))

    # 11. GCODE_TAB_PATTERN (uses pre-computed tab metrics)
    results.append(_check_tab_pattern(metrics.tabs))

    return results


def _get_invariant_description(inv_id: str) -> str:
    """Get human-readable description for an invariant ID."""
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
    """Check that G-code file exists and contains valid G-code.

    A valid G-code line must either be:
    - A comment: (text), ;text, or %
    - A command line containing at least one recognized token:
      G/M commands, coordinates (X/Y/Z/I/J/K/R/A/B/C), feed (F),
      spindle (S), tool (T), line number (N), or program number (O)
    """
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

        # Check for basic G-code structure
        invalid_lines: list[str] = []
        checked = 0

        # Pattern for recognized G-code tokens (letter followed by number)
        # G/M = commands, X/Y/Z/I/J/K/R/A/B/C = coordinates, F = feed, S = spindle,
        # T = tool, N = line number, O = program number, P/Q/L/H/D/E = parameters
        token_pattern = re.compile(
            r"[GMXYZIJKRABCFSTNOQPLHDEUVW]\s*[+-]?\d*\.?\d+",
            re.IGNORECASE
        )

        for i, line in enumerate(lines, 1):
            line = line.strip()
            if not line:
                continue  # Empty lines are OK

            checked += 1

            # Check for comments and program delimiters
            if line.startswith("(") and line.endswith(")"):
                continue  # Comment
            if line.startswith(";"):
                continue  # Comment
            if line == "%":
                continue  # Program delimiter

            # Strip inline comments for token checking
            line_no_comment = line
            if "(" in line:
                line_no_comment = line[:line.index("(")].strip()
            if ";" in line_no_comment:
                line_no_comment = line_no_comment[:line_no_comment.index(";")].strip()

            # Must contain at least one recognized G-code token
            if not token_pattern.search(line_no_comment):
                if len(invalid_lines) < 5:
                    invalid_lines.append(f"Line {i}: No valid G-code token: {line[:50]}")
                continue

            # Also check that line only contains valid characters
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
    """Check that G-code content string contains valid G-code.

    A valid G-code line must either be:
    - A comment: (text), ;text, or %
    - A command line containing at least one recognized token:
      G/M commands, coordinates (X/Y/Z/I/J/K/R/A/B/C), feed (F),
      spindle (S), tool (T), line number (N), or program number (O)
    """
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

        # Check for basic G-code structure
        invalid_lines: list[str] = []
        checked = 0

        # Pattern for recognized G-code tokens (letter followed by number)
        token_pattern = re.compile(
            r"[GMXYZIJKRABCFSTNOQPLHDEUVW]\s*[+-]?\d*\.?\d+",
            re.IGNORECASE
        )

        for i, line in enumerate(lines, 1):
            line = line.strip()
            if not line:
                continue  # Empty lines are OK

            checked += 1

            # Check for comments and program delimiters
            if line.startswith("(") and line.endswith(")"):
                continue  # Comment
            if line.startswith(";"):
                continue  # Comment
            if line == "%":
                continue  # Program delimiter

            # Strip inline comments for token checking
            line_no_comment = line
            if "(" in line:
                line_no_comment = line[:line.index("(")].strip()
            if ";" in line_no_comment:
                line_no_comment = line_no_comment[:line_no_comment.index(";")].strip()

            # Must contain at least one recognized G-code token
            if not token_pattern.search(line_no_comment):
                if len(invalid_lines) < 5:
                    invalid_lines.append(f"Line {i}: No valid G-code token: {line[:50]}")
                continue

            # Also check that line only contains valid characters
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
    """Check that rapid moves (G0) only occur at or above safe_z.

    Uses modal state tracking: G0 sets rapid mode which persists until
    another motion command (G1/G2/G3). Lines with only X/Y/Z coordinates
    use the current modal motion mode.
    """
    checked = 0
    failures: list[str] = []
    current_z = 0.0
    motion_mode = 0  # 0=rapid, 1=linear, 2=cw arc, 3=ccw arc (start assuming rapid)

    for i, line in enumerate(lines, 1):
        line = line.strip()
        if not line or line.startswith("(") or line.startswith(";"):
            continue

        # Check for motion mode changes (G0/G1/G2/G3)
        g_match = G_CODE_PATTERN.search(line)
        if g_match:
            g_code = int(g_match.group(1))
            if g_code in (0, 1, 2, 3):
                motion_mode = g_code

        # Track Z position
        z_match = Z_PATTERN.search(line)
        if z_match:
            current_z = float(z_match.group(1))

        # Check if this line is a rapid move (explicit G0 or modal rapid with motion)
        has_motion = (
            z_match is not None or
            X_PATTERN.search(line) is not None or
            Y_PATTERN.search(line) is not None
        )

        is_rapid_line = (g_match and int(g_match.group(1)) == 0) or \
                        (motion_mode == 0 and has_motion and not g_match)

        if is_rapid_line:
            checked += 1
            # Check if below safe_z
            if current_z < safe_z_mm - 0.001:  # Small tolerance
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
    """Check that all feed rates are positive."""
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
    """Check that Z decreases monotonically during plunge sequences.

    A plunge is a sequence of downward Z moves. During a plunge, Z should
    only decrease (never increase) until the target depth is reached.
    """
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

        # Get motion type
        g_match = G_CODE_PATTERN.search(line)
        is_feed_move = g_match and int(g_match.group(1)) in (1, 2, 3)

        z_match = Z_PATTERN.search(line)
        if z_match:
            new_z = float(z_match.group(1))

            # Check for plunge (Z decreasing during feed move)
            if is_feed_move:
                if new_z < current_z:
                    # Starting or continuing a plunge
                    if not in_plunge:
                        in_plunge = True
                        plunge_start_z = current_z
                        last_plunge_z = new_z
                        checked += 1
                    else:
                        # Continuing plunge - Z should still be decreasing
                        if new_z > last_plunge_z:
                            if len(failures) < 5:
                                failures.append(
                                    f"Line {i}: Non-monotonic plunge Z={new_z:.3f} "
                                    f"(previous Z={last_plunge_z:.3f})"
                                )
                        last_plunge_z = new_z
                elif new_z > current_z:
                    # Retracting - end of plunge
                    in_plunge = False
                    plunge_start_z = None
                    last_plunge_z = None

            # G0 rapid ends plunge sequence
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
    """Check that no single feed move plunges more than max_stepdown.

    This checks for excessive single-move plunge depths during feed moves (G1),
    not total depth change across retract-plunge sequences. A typical multi-pass
    pattern (cut at -1mm, retract to +6mm, plunge to -2mm) is fine because each
    individual plunge is within limits.
    """
    checked = 0
    failures: list[str] = []
    current_z = 0.0
    max_observed_stepdown = 0.0

    for i, line in enumerate(lines, 1):
        line = line.strip()
        if not line or line.startswith("(") or line.startswith(";"):
            continue

        # Only check feed moves (G1), not rapids (G0)
        g_match = G_CODE_PATTERN.search(line)
        is_feed_move = g_match and int(g_match.group(1)) == 1

        z_match = Z_PATTERN.search(line)
        if z_match:
            new_z = float(z_match.group(1))
            stepdown = current_z - new_z  # Positive when going down

            # Only check downward Z moves during feed moves (G1)
            if stepdown > 0 and is_feed_move:
                checked += 1
                max_observed_stepdown = max(max_observed_stepdown, stepdown)

                if stepdown > max_stepdown_mm + 0.001:  # Small tolerance
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
    """Check that all XY positions are within sheet bounds + margin.

    This checks ALL motion (both rapids and cutting moves) to ensure the machine
    never moves outside the allowed work envelope. This is a machine safety check
    to prevent crashes, not a geometric accuracy check.

    Note: The margin parameter allows for reposition moves slightly outside the
    stock material, which is common in CNC operations. If you need to check only
    cutting bounds, extract cutting-only bounds from the G-code separately.
    """
    bounds = metrics.xy_bounds
    failures: list[str] = []

    # Calculate allowed bounds
    x_min_allowed = -margin_mm
    x_max_allowed = sheet_width_mm + margin_mm
    y_min_allowed = -margin_mm
    y_max_allowed = sheet_height_mm + margin_mm

    # Check if bounds were computed
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

    # Check each bound
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
    """Check that spindle is on before any cutting moves (G1 at negative Z)."""
    checked = 0
    failures: list[str] = []
    spindle_on = False
    current_z = 0.0

    for i, line in enumerate(lines, 1):
        line_upper = line.strip().upper()
        if not line_upper or line_upper.startswith("(") or line_upper.startswith(";"):
            continue

        # Check for spindle on/off commands
        m_match = M_CODE_PATTERN.search(line_upper)
        if m_match:
            m_code = int(m_match.group(1))
            if m_code in (3, 4):  # M3 = spindle CW, M4 = spindle CCW
                spindle_on = True
            elif m_code == 5:  # M5 = spindle off
                spindle_on = False

        # Track Z position
        z_match = Z_PATTERN.search(line_upper)
        if z_match:
            current_z = float(z_match.group(1))

        # Check for G1 feed move at negative Z (cutting)
        g_match = G_CODE_PATTERN.search(line_upper)
        if g_match and int(g_match.group(1)) == 1:
            # Check if we're at cutting depth (negative Z)
            if current_z < -0.001:  # Below surface
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
    """Check that tool numbers are declared before use."""
    checked = 0
    failures: list[str] = []
    declared_tools: set[int] = set()
    current_tool: int | None = None

    for i, line in enumerate(lines, 1):
        line = line.strip()
        if not line or line.startswith("(") or line.startswith(";"):
            continue

        # Check for tool declaration (Tn)
        t_match = T_PATTERN.search(line)
        if t_match:
            tool_num = int(t_match.group(1))
            declared_tools.add(tool_num)
            current_tool = tool_num
            checked += 1

        # Check for M6 (tool change) - requires previous T command
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
    """Check that program ends with Z at or above safe height.

    Tracks the modal Z position through the entire file to find the
    final Z position (which may be set many lines before the end if
    subsequent lines only have X/Y motion).
    """
    final_z: float | None = None

    # Track Z position through the entire file (modal tracking)
    # The final Z is the last Z value encountered, regardless of where it appears
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

    if final_z >= safe_z_mm - 0.001:  # Small tolerance
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
    """Check for discontinuous jumps during cutting moves.

    During cutting (Z < 0 and feed moves), the tool should follow a continuous
    path. Large XY jumps without a retract indicate a broken toolpath.

    A typical multi-pass pattern is:
      G1 Z-1.587  (plunge)
      G1 X... Y... (cut)
      G0 Z6.000   (retract - this exits cut mode)
      G0 X... Y... (reposition while retracted)
      G1 Z-3.175  (plunge to next depth)

    We only check for discontinuities during continuous cutting moves, not
    across retract/reposition cycles.

    Args:
        lines: G-code lines to check
        jump_tolerance_mm: Minimum distance to consider as a jump
        warn_threshold_mm: Distance above which to emit warnings (sheet diagonal)
        fail_threshold_mm: Distance above which to emit failures (clearly broken)
    """
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

        # Parse coordinates
        x_match = X_PATTERN.search(line)
        y_match = Y_PATTERN.search(line)
        z_match = Z_PATTERN.search(line)
        g_match = G_CODE_PATTERN.search(line)

        new_x = float(x_match.group(1)) if x_match else current_x
        new_y = float(y_match.group(1)) if y_match else current_y
        new_z = float(z_match.group(1)) if z_match else current_z

        # Determine motion type
        is_feed_move = g_match and int(g_match.group(1)) in (1, 2, 3)
        is_rapid = g_match and int(g_match.group(1)) == 0

        # A rapid move (G0) always exits cut mode, regardless of Z
        if is_rapid:
            in_cut = False
            current_x = new_x
            current_y = new_y
            current_z = new_z
            continue

        # Track cutting state: we enter cut mode when doing a feed move at negative Z
        was_in_cut = in_cut
        if is_feed_move and new_z < -0.001:
            in_cut = True
        elif new_z >= -0.001:
            in_cut = False

        # Check for jumps only during continuous cutting (both previous and current in cut)
        if in_cut and was_in_cut and is_feed_move:
            # Only check XY-only moves (not plunges which naturally have no XY motion)
            has_xy_motion = x_match is not None or y_match is not None
            has_z_motion = z_match is not None and abs(new_z - current_z) > 0.001

            # Skip pure Z moves (plunges) - we're checking XY continuity
            if has_xy_motion and not has_z_motion:
                xy_distance = math.sqrt((new_x - current_x)**2 + (new_y - current_y)**2)

                # For G2/G3 arcs, allow larger "jumps" since the arc path is continuous
                is_arc = g_match and int(g_match.group(1)) in (2, 3)

                if not is_arc and xy_distance > jump_tolerance_mm:
                    checked += 1
                    max_jump = max(max_jump, xy_distance)

                    # Tiered thresholds:
                    # - Above fail_threshold: definitely broken (FAIL)
                    # - Above warn_threshold: suspicious, may indicate issue (WARN)
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

    # Determine status: FAIL > WARN > PASS
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
        failures=tuple(failures + warnings),  # Include warnings in failures list for visibility
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
    """Check that detected tabs have valid patterns.

    Validates:
    1. Tabs occur at or near max cutting depth (final passes only)
    2. Tab heights are consistent (all within tolerance of each other)
    3. Tab heights are positive and reasonable (0 < height < 20mm)

    Args:
        tabs: TabMetrics from G-code metric extraction
        height_tolerance_mm: Tolerance for tab height consistency

    Returns:
        InvariantResult for tab pattern validation
    """
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
