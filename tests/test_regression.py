# tests/test_regression.py - Tests for the regression comparator
#
# Tests metric delta comparison against a baseline.
# See docs/cam_validation_plan.md Section 6 for strategy.

from __future__ import annotations

from validation.core import Verdict
from validation.regression.comparator import (
    ComparisonConfig,
    _compare_exact,
    _compare_numeric,
    _compare_structural,
    _flatten_dict,
    _get_tolerance,
    compare_metrics,
)

# ============================================================================
# Test fixtures
# ============================================================================


def make_sample_metrics() -> dict:
    """Sample metrics for testing."""
    return {
        "svg": {
            "document": {
                "width_mm": 450.0,
                "height_mm": 650.0,
                "viewbox": [0, 0, 450, 650],
            },
            "layers": {
                "count": 6,
                "names": ["SHEET_OUTLINE", "PROFILE_CUTS", "POCKET_REGIONS", "HOLES", "DIMENSIONS", "NOTES"],
            },
            "paths": {
                "total_count": 15,
                "closed_count": 12,
                "open_count": 3,
            },
            "circles": {
                "count": 2,
                "radii_mm": [5.0, 5.0],
            },
        },
        "gcode": {
            "summary": {
                "total_lines": 1250,
                "motion_lines": 1180,
            },
            "motion": {
                "g0_count": 85,
                "g1_count": 1095,
                "total_rapid_distance_mm": 1250.5,
                "total_feed_distance_mm": 4580.2,
            },
            "z_profile": {
                "safe_z_mm": 25.0,
                "max_plunge_z_mm": -19.0,
                "unique_cutting_depths": [-6.0, -12.0, -19.0],
            },
            "tools": {
                "tool_numbers": [1, 2],
                "spindle_speeds": [10000, 14000],
            },
        },
    }


# ============================================================================
# Comparator unit tests
# ============================================================================


def test_flatten_dict_simple():
    """Flattening a simple nested dict."""
    d = {"a": {"b": {"c": 1}}}
    flat = _flatten_dict(d)
    assert flat["a.b.c"] == 1


def test_flatten_dict_with_list():
    """Flattening handles lists."""
    d = {"items": [1, 2, 3], "nested": {"values": [4, 5]}}
    flat = _flatten_dict(d)
    assert flat["items"] == [1, 2, 3]
    assert flat["nested.values"] == [4, 5]


def test_compare_numeric_within_tolerance():
    """Numeric comparison passes within tolerance."""
    config = ComparisonConfig(default_tolerance_percent=0.1)
    result = _compare_numeric("test.value", 100.05, 100.0, config)
    assert result.status == Verdict.PASS
    assert result.delta == 0.05
    assert result.delta_percent is not None
    assert result.delta_percent < 0.1


def test_compare_numeric_exceeds_tolerance():
    """Numeric comparison warns when exceeding tolerance but under fail threshold."""
    config = ComparisonConfig(default_tolerance_percent=0.1, fail_multiplier=2.0)
    # 0.15% delta > 0.1% tolerance, but < 0.2% (2x tolerance) = WARN
    result = _compare_numeric("test.value", 100.15, 100.0, config)
    assert result.delta_percent is not None
    assert result.status == Verdict.WARN, f"Expected WARN, got {result.status} ({result.delta_percent}%)"
    assert result.delta_percent > 0.1
    assert result.delta_percent < 0.2


def test_compare_numeric_fail_on_large_delta():
    """Numeric comparison fails on large delta."""
    config = ComparisonConfig(default_tolerance_percent=0.01, fail_multiplier=2.0)
    # 5% delta >> 0.01% tolerance = FAIL
    result = _compare_numeric("test.value", 105.0, 100.0, config)
    assert result.status == Verdict.FAIL


def test_compare_exact_match():
    """Exact comparison passes on equal values."""
    result = _compare_exact("test.count", 42, 42)
    assert result.status == Verdict.PASS


def test_compare_exact_mismatch():
    """Exact comparison fails on unequal values."""
    result = _compare_exact("test.count", 42, 43)
    assert result.status == Verdict.FAIL
    assert "expected 43" in result.message


def test_compare_structural_match():
    """Structural comparison passes on same set (order-independent)."""
    result = _compare_structural("test.names", ["b", "a", "c"], ["a", "b", "c"])
    assert result.status == Verdict.PASS


def test_compare_structural_mismatch():
    """Structural comparison fails on different sets."""
    result = _compare_structural("test.names", ["a", "b"], ["a", "b", "c"])
    assert result.status == Verdict.FAIL
    assert "removed" in result.message


def test_get_tolerance_default():
    """Default tolerance is used for unknown paths."""
    config = ComparisonConfig(default_tolerance_percent=0.5)
    tol = _get_tolerance("unknown.metric.path", config)
    assert tol == 0.5


def test_get_tolerance_category():
    """Tolerance category is used for matching paths."""
    config = ComparisonConfig(default_tolerance_percent=0.5)
    # Distance paths use position tolerance (0.01%)
    tol = _get_tolerance("gcode.motion.total_rapid_distance_mm", config)
    assert tol == 0.1


def test_get_tolerance_override():
    """Explicit override takes precedence."""
    config = ComparisonConfig(
        default_tolerance_percent=0.5,
        tolerance_overrides={"gcode.motion.total_rapid_distance_mm": 1.0},
    )
    tol = _get_tolerance("gcode.motion.total_rapid_distance_mm", config)
    assert tol == 1.0


def test_compare_numeric_near_zero_uses_absolute():
    """Near-zero values use absolute tolerance instead of percent."""
    config = ComparisonConfig(
        near_zero_threshold=0.01,
        absolute_tolerance=0.01,
    )
    # Golden is 0, current is 0.005 - should pass with absolute tolerance
    result = _compare_numeric("test.x_min", 0.005, 0.0, config)
    assert result.status == Verdict.PASS, f"Expected PASS, got {result.status}"
    assert result.delta_percent is None  # Not meaningful for near-zero
    assert "absolute" in result.message.lower()


def test_compare_numeric_near_zero_fail():
    """Near-zero values fail when exceeding absolute tolerance."""
    config = ComparisonConfig(
        near_zero_threshold=0.01,
        absolute_tolerance=0.001,
        fail_multiplier=2.0,
    )
    # Golden is 0, current is 0.005 >> 0.001 absolute tolerance
    result = _compare_numeric("test.x_min", 0.005, 0.0, config)
    assert result.status == Verdict.FAIL, f"Expected FAIL, got {result.status}"


# ============================================================================
# Compare metrics integration tests
# ============================================================================


def test_compare_metrics_golden_file_set():
    """compare_metrics sets golden_file in summary."""
    golden = {"a": 1}
    current = {"a": 1}
    summary = compare_metrics(current, golden, golden_file="/path/to/golden.json")

    assert summary.golden_file == "/path/to/golden.json"


def test_compare_metrics_excludes_golden_metadata():
    """Golden metadata wrapper is excluded from comparison."""
    golden = {"golden": {"recipe_name": "test", "created_at": "2026-01-01"}, "a": 1}
    current = {"a": 1}  # No golden wrapper

    summary = compare_metrics(current, golden)

    # Should not have any results for golden.* paths
    golden_results = [r for r in summary.results if r.metric_path.startswith("golden.")]
    assert len(golden_results) == 0, f"Unexpected golden.* results: {golden_results}"
    # Should pass overall (a matches)
    assert summary.verdict() == Verdict.PASS


def test_compare_metrics_identical():
    """Comparing identical metrics returns all PASS."""
    metrics = make_sample_metrics()
    summary = compare_metrics(metrics, metrics)

    assert summary.compared is True
    assert summary.total > 0
    # All should pass (identical)
    failed = [r for r in summary.results if r.status == Verdict.FAIL]
    assert len(failed) == 0, f"Unexpected failures: {[r.metric_path for r in failed]}"


def test_compare_metrics_new_metric():
    """New metric in current (not in golden) is PASS."""
    golden = {"a": 1}
    current = {"a": 1, "b": 2}
    summary = compare_metrics(current, golden)

    new_results = [r for r in summary.results if "New metric" in r.message]
    assert len(new_results) == 1
    assert new_results[0].status == Verdict.PASS


def test_compare_metrics_missing_metric():
    """Missing metric in current (was in golden) is WARN."""
    golden = {"a": 1, "b": 2}
    current = {"a": 1}
    summary = compare_metrics(current, golden)

    missing_results = [r for r in summary.results if "Missing metric" in r.message]
    assert len(missing_results) == 1
    assert missing_results[0].status == Verdict.WARN


def test_compare_metrics_excludes_extraction_time():
    """extraction_time_ms is excluded from comparison."""
    golden = {"svg": {"extraction_time_ms": 10.0, "count": 5}}
    current = {"svg": {"extraction_time_ms": 20.0, "count": 5}}
    summary = compare_metrics(current, golden)

    # extraction_time_ms should not appear in results
    time_results = [r for r in summary.results if "extraction_time" in r.metric_path]
    assert len(time_results) == 0


def test_compare_metrics_count_exact_match():
    """Count fields use exact matching."""
    golden = {"svg": {"paths": {"total_count": 15}}}
    current = {"svg": {"paths": {"total_count": 16}}}
    summary = compare_metrics(current, golden)

    count_results = [r for r in summary.results if "total_count" in r.metric_path]
    assert len(count_results) == 1
    assert count_results[0].status == Verdict.FAIL


def test_compare_metrics_boolean_exact_match():
    """Boolean fields use exact matching."""
    golden = {"svg": {"paths": {"has_closed": True}}}
    current = {"svg": {"paths": {"has_closed": False}}}
    summary = compare_metrics(current, golden)

    bool_results = [r for r in summary.results if "has_closed" in r.metric_path]
    assert len(bool_results) == 1
    assert bool_results[0].status == Verdict.FAIL


def test_compare_metrics_structural_layers():
    """Layer names use structural (set) matching."""
    golden = {"svg": {"layers": {"names": ["A", "B", "C"]}}}
    current = {"svg": {"layers": {"names": ["C", "B", "A"]}}}  # Reordered
    summary = compare_metrics(current, golden)

    names_results = [r for r in summary.results if "names" in r.metric_path]
    # Should pass - same set
    assert all(r.status == Verdict.PASS for r in names_results)


def test_compare_metrics_numeric_tolerance():
    """Numeric values use tolerance-based comparison."""
    golden = {"gcode": {"motion": {"total_feed_distance_mm": 1000000.0}}}
    current = {"gcode": {"motion": {"total_feed_distance_mm": 1000050.0}}}  # 0.005% difference
    summary = compare_metrics(current, golden)

    dist_results = [r for r in summary.results if "total_feed_distance" in r.metric_path]
    assert len(dist_results) == 1
    # 0.005% < 0.1% tolerance = PASS
    assert dist_results[0].status == Verdict.PASS
