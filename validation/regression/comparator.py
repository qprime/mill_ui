# validation/regression/comparator.py - Metric delta comparison
#
# Compares current metrics against golden baselines with tolerance-based verdicts.
# See docs/cam_validation_plan.md Section 6 for strategy.

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any

from validation.core import Verdict, RegressionResult, RegressionSummary


# Metric categories for comparison strategy
# These paths use exact matching (counts, booleans, enums)
EXACT_MATCH_PATHS = frozenset({
    # SVG
    "svg.layers.count",
    # Note: svg.layers.names is in STRUCTURAL_MATCH_PATHS (order-independent)
    "svg.paths.total_count",
    "svg.paths.closed_count",
    "svg.paths.open_count",
    "svg.circles.count",
    "svg.rects.count",
    "svg.text_elements.count",
    # STL
    "stl.mesh.vertex_count",
    "stl.mesh.face_count",
    "stl.mesh.is_watertight",
    "stl.mesh.is_manifold",
    "stl.mesh.is_volume",
    "stl.mesh.euler_number",
    "stl.mesh.connected_components",
    "stl.z_statistics.z_level_count",
    # G-code
    "gcode.summary.total_lines",
    "gcode.summary.comment_lines",
    "gcode.summary.motion_lines",
    "gcode.summary.tool_change_lines",
    "gcode.summary.spindle_lines",
    "gcode.motion.g0_count",
    "gcode.motion.g1_count",
    "gcode.motion.g2_count",
    "gcode.motion.g3_count",
    "gcode.z_profile.depth_count",
    "gcode.tools.tool_numbers",
    "gcode.tools.tool_changes",
    "gcode.operations.total_passes",
})

# These paths compare as sets (order-independent)
STRUCTURAL_MATCH_PATHS = frozenset({
    "svg.layers.names",
    "gcode.tools.tool_numbers",
    "gcode.tools.spindle_speeds",
    "gcode.feeds.feed_rates_used",
    "gcode.z_profile.unique_cutting_depths",
    "stl.z_statistics.unique_z_levels",
})

# These paths are checksums (hash comparison)
CHECKSUM_PATHS = frozenset({
    "stl.heightmap.checksum",
})

# These paths are excluded from comparison (non-deterministic metadata)
EXCLUDED_PATHS = frozenset({
    "svg.extraction_time_ms",
    "stl.extraction_time_ms",
    "gcode.extraction_time_ms",
    "svg.version",
    "stl.version",
    "gcode.version",
})

# Prefix patterns to exclude (metadata wrappers)
EXCLUDED_PREFIXES = (
    "golden.",  # Golden store metadata wrapper
)

# Default tolerances by metric category (percent)
DEFAULT_TOLERANCES: dict[str, float] = {
    # Position/dimension metrics (0.01mm tolerance = 0.01% for typical 100mm parts)
    "position": 0.01,
    # Area/volume metrics (per plan section 5.3)
    "area": 0.1,
    "volume": 0.1,
    # Distance metrics
    "distance": 0.1,
    # Time estimates (higher tolerance due to machine-specific variability)
    "time": 1.0,
    # Default for unlisted metrics
    "default": 0.1,
}

# Mapping of metric path patterns to tolerance categories
TOLERANCE_CATEGORIES: dict[str, str] = {
    # Position/dimension
    "bounds": "position",
    "x_min": "position",
    "x_max": "position",
    "y_min": "position",
    "y_max": "position",
    "z_min": "position",
    "z_max": "position",
    "width": "position",
    "height": "position",
    "thickness": "position",
    "radii": "position",
    "dimensions": "position",
    "center": "position",
    "safe_z": "position",
    "max_plunge": "position",
    "max_single_plunge": "position",
    # Area/volume
    "volume": "volume",
    "surface_area": "area",
    "area": "area",
    # Distance
    "distance": "distance",
    "length": "distance",
    "total_rapid": "distance",
    "total_feed": "distance",
    # Time
    "time_": "time",
    "_time_s": "time",
}


@dataclass
class ComparisonConfig:
    """Configuration for metric comparison."""

    default_tolerance_percent: float = 0.1
    tolerance_overrides: dict[str, float] = field(default_factory=dict)
    # Warn if delta exceeds tolerance but < fail_multiplier * tolerance
    # Fail if delta >= fail_multiplier * tolerance
    fail_multiplier: float = 2.0
    # Absolute tolerance for near-zero values (avoids 0 -> 0.001 = 100% delta)
    # When abs(golden) < near_zero_threshold, use absolute tolerance instead of percent
    near_zero_threshold: float = 0.01  # Values below this use absolute tolerance
    absolute_tolerance: float = 0.01   # Absolute tolerance for near-zero values (mm)


def compare_metrics(
    current: dict[str, Any],
    golden: dict[str, Any],
    config: ComparisonConfig | None = None,
    golden_file: str | None = None,
) -> RegressionSummary:
    """
    Compare current metrics against golden baseline.

    Args:
        current: Current metrics dict
        golden: Golden baseline metrics dict
        config: Optional comparison configuration
        golden_file: Optional path to golden file (for reporting)

    Returns a RegressionSummary with all comparison results.
    """
    if config is None:
        config = ComparisonConfig()

    summary = RegressionSummary(compared=True, golden_file=golden_file)

    # Flatten both dicts for comparison
    current_flat = _flatten_dict(current)
    golden_flat = _flatten_dict(golden)

    all_paths = set(current_flat.keys()) | set(golden_flat.keys())

    for path in sorted(all_paths):
        # Skip excluded paths
        if _is_excluded(path):
            continue

        current_value = current_flat.get(path)
        golden_value = golden_flat.get(path)

        result = _compare_values(path, current_value, golden_value, config)
        summary.add(result)

    return summary


def _flatten_dict(
    d: dict[str, Any],
    parent_key: str = "",
    sep: str = ".",
) -> dict[str, Any]:
    """Flatten a nested dict into dot-separated paths."""
    items: list[tuple[str, Any]] = []

    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k

        if isinstance(v, dict):
            items.extend(_flatten_dict(v, new_key, sep).items())
        elif isinstance(v, list):
            # Handle lists: store as-is for structural comparison
            # Also flatten indexed access for individual elements
            items.append((new_key, v))
            for i, item in enumerate(v):
                if isinstance(item, dict):
                    items.extend(_flatten_dict(item, f"{new_key}[{i}]", sep).items())
                else:
                    items.append((f"{new_key}[{i}]", item))
        else:
            items.append((new_key, v))

    return dict(items)


def _is_excluded(path: str) -> bool:
    """Check if a path should be excluded from comparison."""
    # Check exact paths
    for excluded in EXCLUDED_PATHS:
        if path == excluded or path.startswith(excluded + "."):
            return True
    # Check prefix patterns (e.g., "golden.*" metadata)
    for prefix in EXCLUDED_PREFIXES:
        if path.startswith(prefix):
            return True
    # Exclude array index paths that are redundant with list comparison
    if "[" in path and "]" in path:
        return True
    return False


def _compare_values(
    path: str,
    current: Any,
    golden: Any,
    config: ComparisonConfig,
) -> RegressionResult:
    """Compare two values and return a RegressionResult."""

    # Handle missing metrics
    if golden is None:
        return RegressionResult(
            metric_path=path,
            golden_value=None,
            current_value=current,
            delta=None,
            delta_percent=None,
            tolerance_percent=0,
            status=Verdict.PASS,  # New metrics don't fail
            message="New metric (not in golden baseline)",
        )

    if current is None:
        return RegressionResult(
            metric_path=path,
            golden_value=golden,
            current_value=None,
            delta=None,
            delta_percent=None,
            tolerance_percent=0,
            status=Verdict.WARN,  # Missing metrics warn
            message="Missing metric (was in golden baseline)",
        )

    # Structural match paths take precedence (set comparison, order-independent)
    if path in STRUCTURAL_MATCH_PATHS or _is_structural_path(path):
        return _compare_structural(path, current, golden)

    # Exact match paths (counts, booleans)
    if path in EXACT_MATCH_PATHS or _is_exact_match_path(path):
        return _compare_exact(path, current, golden)

    # Checksum paths
    if path in CHECKSUM_PATHS:
        return _compare_checksum(path, current, golden)

    # Boolean comparison
    if isinstance(golden, bool) or isinstance(current, bool):
        return _compare_exact(path, current, golden)

    # String comparison
    if isinstance(golden, str) or isinstance(current, str):
        return _compare_exact(path, current, golden)

    # List comparison (if not structural)
    if isinstance(golden, list) or isinstance(current, list):
        return _compare_lists(path, current, golden, config)

    # Numeric comparison with tolerance
    if isinstance(golden, (int, float)) and isinstance(current, (int, float)):
        return _compare_numeric(path, current, golden, config)

    # Fall back to exact match for unknown types
    return _compare_exact(path, current, golden)


def _is_exact_match_path(path: str) -> bool:
    """Check if path should use exact matching based on patterns."""
    # Count fields are exact match
    if "_count" in path or "count" == path.split(".")[-1]:
        return True
    # Boolean fields
    if path.split(".")[-1].startswith("is_"):
        return True
    return False


def _is_structural_path(path: str) -> bool:
    """Check if path should use structural (set) matching."""
    # List of unique values
    if "unique_" in path:
        return True
    if "_names" in path:
        return True
    if "_used" in path:
        return True
    return False


def _normalize_for_comparison(value: Any) -> Any:
    """Normalize values for comparison (tuples -> lists, recursively)."""
    if isinstance(value, tuple):
        return [_normalize_for_comparison(v) for v in value]
    if isinstance(value, list):
        return [_normalize_for_comparison(v) for v in value]
    return value


def _compare_exact(
    path: str,
    current: Any,
    golden: Any,
) -> RegressionResult:
    """Compare values for exact equality."""
    # Normalize tuples to lists for comparison (JSON doesn't distinguish)
    current_norm = _normalize_for_comparison(current)
    golden_norm = _normalize_for_comparison(golden)
    matches = current_norm == golden_norm

    return RegressionResult(
        metric_path=path,
        golden_value=golden,
        current_value=current,
        delta=None,
        delta_percent=None,
        tolerance_percent=0,
        status=Verdict.PASS if matches else Verdict.FAIL,
        message="Exact match" if matches else f"Value mismatch: expected {golden}, got {current}",
    )


def _compare_structural(
    path: str,
    current: Any,
    golden: Any,
) -> RegressionResult:
    """Compare values as sets (order-independent)."""
    try:
        current_set = set(current) if isinstance(current, list) else {current}
        golden_set = set(golden) if isinstance(golden, list) else {golden}
    except TypeError:
        # Unhashable types fall back to exact match
        return _compare_exact(path, current, golden)

    matches = current_set == golden_set

    if matches:
        return RegressionResult(
            metric_path=path,
            golden_value=golden,
            current_value=current,
            delta=None,
            delta_percent=None,
            tolerance_percent=0,
            status=Verdict.PASS,
            message="Structural match (sets equal)",
        )
    else:
        added = current_set - golden_set
        removed = golden_set - current_set
        msg_parts = []
        if added:
            msg_parts.append(f"added: {sorted(added)}")
        if removed:
            msg_parts.append(f"removed: {sorted(removed)}")
        return RegressionResult(
            metric_path=path,
            golden_value=golden,
            current_value=current,
            delta=None,
            delta_percent=None,
            tolerance_percent=0,
            status=Verdict.FAIL,
            message=f"Structural mismatch: {'; '.join(msg_parts)}",
        )


def _compare_checksum(
    path: str,
    current: Any,
    golden: Any,
) -> RegressionResult:
    """Compare checksum values."""
    matches = current == golden

    return RegressionResult(
        metric_path=path,
        golden_value=golden,
        current_value=current,
        delta=None,
        delta_percent=None,
        tolerance_percent=0,
        status=Verdict.PASS if matches else Verdict.FAIL,
        message="Checksum match" if matches else "Checksum mismatch (content changed)",
    )


def _compare_lists(
    path: str,
    current: Any,
    golden: Any,
    config: ComparisonConfig,
) -> RegressionResult:
    """Compare lists element by element."""
    if not isinstance(current, list):
        current = [current] if current is not None else []
    if not isinstance(golden, list):
        golden = [golden] if golden is not None else []

    # Check length first
    if len(current) != len(golden):
        return RegressionResult(
            metric_path=path,
            golden_value=golden,
            current_value=current,
            delta=float(len(current) - len(golden)),
            delta_percent=None,
            tolerance_percent=0,
            status=Verdict.FAIL,
            message=f"List length mismatch: expected {len(golden)}, got {len(current)}",
        )

    # Compare elements (numeric lists get tolerance comparison)
    if all(isinstance(x, (int, float)) for x in current + golden):
        # Numeric list - compare with tolerance
        max_delta_pct = 0.0
        for c, g in zip(current, golden):
            if g != 0:
                delta_pct = abs((c - g) / g) * 100
            elif c != 0:
                delta_pct = 100.0
            else:
                delta_pct = 0.0
            max_delta_pct = max(max_delta_pct, delta_pct)

        tolerance = _get_tolerance(path, config)

        if max_delta_pct <= tolerance:
            status = Verdict.PASS
            msg = f"Numeric list within tolerance ({max_delta_pct:.4f}% <= {tolerance}%)"
        elif max_delta_pct <= tolerance * config.fail_multiplier:
            status = Verdict.WARN
            msg = f"Numeric list exceeds tolerance ({max_delta_pct:.4f}% > {tolerance}%)"
        else:
            status = Verdict.FAIL
            msg = f"Numeric list significantly exceeds tolerance ({max_delta_pct:.4f}% >> {tolerance}%)"

        return RegressionResult(
            metric_path=path,
            golden_value=golden,
            current_value=current,
            delta=None,
            delta_percent=max_delta_pct,
            tolerance_percent=tolerance,
            status=status,
            message=msg,
        )
    else:
        # Non-numeric list - exact comparison
        return _compare_exact(path, current, golden)


def _compare_numeric(
    path: str,
    current: float,
    golden: float,
    config: ComparisonConfig,
) -> RegressionResult:
    """Compare numeric values with tolerance."""
    delta = current - golden
    abs_delta = abs(delta)

    # For near-zero values, use absolute tolerance to avoid huge percent deltas
    # (e.g., 0 -> 0.001 would be 100% but is actually tiny)
    use_absolute = abs(golden) < config.near_zero_threshold

    if use_absolute:
        # Use absolute tolerance comparison
        tolerance = config.absolute_tolerance
        delta_percent = None  # Not meaningful for near-zero values

        if abs_delta <= tolerance:
            status = Verdict.PASS
            msg = f"Within absolute tolerance ({abs_delta:.6f}mm <= {tolerance}mm)"
        elif abs_delta <= tolerance * config.fail_multiplier:
            status = Verdict.WARN
            msg = f"Exceeds absolute tolerance ({abs_delta:.6f}mm > {tolerance}mm)"
        else:
            status = Verdict.FAIL
            msg = f"Significantly exceeds absolute tolerance ({abs_delta:.6f}mm >> {tolerance}mm)"
    else:
        # Use percent tolerance comparison
        delta_percent = abs(delta / golden) * 100
        tolerance = _get_tolerance(path, config)

        if delta_percent <= tolerance:
            status = Verdict.PASS
            msg = f"Within tolerance ({delta_percent:.4f}% <= {tolerance}%)"
        elif delta_percent <= tolerance * config.fail_multiplier:
            status = Verdict.WARN
            msg = f"Exceeds tolerance ({delta_percent:.4f}% > {tolerance}%)"
        else:
            status = Verdict.FAIL
            msg = f"Significantly exceeds tolerance ({delta_percent:.4f}% >> {tolerance}%)"

    return RegressionResult(
        metric_path=path,
        golden_value=golden,
        current_value=current,
        delta=round(delta, 6),
        delta_percent=round(delta_percent, 6) if delta_percent is not None else None,
        tolerance_percent=tolerance if not use_absolute else 0,
        status=status,
        message=msg,
    )


def _get_tolerance(path: str, config: ComparisonConfig) -> float:
    """Get tolerance for a metric path."""
    # Check explicit overrides first
    if path in config.tolerance_overrides:
        return config.tolerance_overrides[path]

    # Check category patterns
    path_lower = path.lower()
    for pattern, category in TOLERANCE_CATEGORIES.items():
        if pattern in path_lower:
            return DEFAULT_TOLERANCES.get(category, config.default_tolerance_percent)

    return config.default_tolerance_percent


def metrics_to_comparable_dict(metrics: Any) -> dict[str, Any]:
    """
    Convert metrics (dataclass or dict) to a dict suitable for comparison.

    Handles SVGMetrics, STLMetrics, GCodeMetrics dataclasses.
    """
    if hasattr(metrics, "to_dict"):
        return metrics.to_dict()
    if isinstance(metrics, dict):
        return metrics
    raise TypeError(f"Cannot convert {type(metrics)} to dict")
