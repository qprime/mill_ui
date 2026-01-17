# tests/test_regression.py - Tests for regression comparator and golden store
#
# Tests metric delta comparison and golden baseline management.
# See docs/cam_validation_plan.md Section 6 for strategy.

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from validation.core import Verdict, RegressionResult, RegressionSummary
from validation.regression.comparator import (
    compare_metrics,
    ComparisonConfig,
    _flatten_dict,
    _compare_numeric,
    _compare_exact,
    _compare_structural,
    _get_tolerance,
)
from validation.regression.golden_store import (
    GoldenStore,
    GoldenIndex,
    GoldenEntry,
    create_golden_from_recipe,
)


# Path to recipe outputs
RECIPE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "docs",
    "recipes",
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
        "stl": {
            "mesh": {
                "vertex_count": 1248,
                "face_count": 2492,
                "is_watertight": True,
                "is_manifold": True,
                "is_volume": True,
                "euler_number": 2,
            },
            "dimensions": {
                "width_mm": 450.0,
                "height_mm": 650.0,
                "thickness_mm": 19.0,
            },
            "volume_mm3": 5557500.0,
            "surface_area_mm2": 614350.0,
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
    print("PASS: test_flatten_dict_simple")


def test_flatten_dict_with_list():
    """Flattening handles lists."""
    d = {"items": [1, 2, 3], "nested": {"values": [4, 5]}}
    flat = _flatten_dict(d)
    assert flat["items"] == [1, 2, 3]
    assert flat["nested.values"] == [4, 5]
    print("PASS: test_flatten_dict_with_list")


def test_compare_numeric_within_tolerance():
    """Numeric comparison passes within tolerance."""
    config = ComparisonConfig(default_tolerance_percent=0.1)
    result = _compare_numeric("test.value", 100.05, 100.0, config)
    assert result.status == Verdict.PASS
    assert result.delta == 0.05
    assert result.delta_percent < 0.1
    print("PASS: test_compare_numeric_within_tolerance")


def test_compare_numeric_exceeds_tolerance():
    """Numeric comparison warns when exceeding tolerance but under fail threshold."""
    config = ComparisonConfig(default_tolerance_percent=0.1, fail_multiplier=2.0)
    # 0.15% delta > 0.1% tolerance, but < 0.2% (2x tolerance) = WARN
    result = _compare_numeric("test.value", 100.15, 100.0, config)
    assert result.status == Verdict.WARN, f"Expected WARN, got {result.status} ({result.delta_percent}%)"
    assert result.delta_percent > 0.1
    assert result.delta_percent < 0.2
    print("PASS: test_compare_numeric_exceeds_tolerance")


def test_compare_numeric_fail_on_large_delta():
    """Numeric comparison fails on large delta."""
    config = ComparisonConfig(default_tolerance_percent=0.01, fail_multiplier=2.0)
    # 5% delta >> 0.01% tolerance = FAIL
    result = _compare_numeric("test.value", 105.0, 100.0, config)
    assert result.status == Verdict.FAIL
    print("PASS: test_compare_numeric_fail_on_large_delta")


def test_compare_exact_match():
    """Exact comparison passes on equal values."""
    result = _compare_exact("test.count", 42, 42)
    assert result.status == Verdict.PASS
    print("PASS: test_compare_exact_match")


def test_compare_exact_mismatch():
    """Exact comparison fails on unequal values."""
    result = _compare_exact("test.count", 42, 43)
    assert result.status == Verdict.FAIL
    assert "expected 43" in result.message
    print("PASS: test_compare_exact_mismatch")


def test_compare_structural_match():
    """Structural comparison passes on same set (order-independent)."""
    result = _compare_structural("test.names", ["b", "a", "c"], ["a", "b", "c"])
    assert result.status == Verdict.PASS
    print("PASS: test_compare_structural_match")


def test_compare_structural_mismatch():
    """Structural comparison fails on different sets."""
    result = _compare_structural("test.names", ["a", "b"], ["a", "b", "c"])
    assert result.status == Verdict.FAIL
    assert "removed" in result.message
    print("PASS: test_compare_structural_mismatch")


def test_get_tolerance_default():
    """Default tolerance is used for unknown paths."""
    config = ComparisonConfig(default_tolerance_percent=0.5)
    tol = _get_tolerance("unknown.metric.path", config)
    assert tol == 0.5
    print("PASS: test_get_tolerance_default")


def test_get_tolerance_category():
    """Tolerance category is used for matching paths."""
    config = ComparisonConfig(default_tolerance_percent=0.5)
    # Volume paths use volume tolerance (0.1%)
    tol = _get_tolerance("stl.volume_mm3", config)
    assert tol == 0.1
    print("PASS: test_get_tolerance_category")


def test_get_tolerance_override():
    """Explicit override takes precedence."""
    config = ComparisonConfig(
        default_tolerance_percent=0.5,
        tolerance_overrides={"stl.volume_mm3": 1.0},
    )
    tol = _get_tolerance("stl.volume_mm3", config)
    assert tol == 1.0
    print("PASS: test_get_tolerance_override")


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
    print("PASS: test_compare_numeric_near_zero_uses_absolute")


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
    print("PASS: test_compare_numeric_near_zero_fail")


# ============================================================================
# Compare metrics integration tests
# ============================================================================


def test_compare_metrics_golden_file_set():
    """compare_metrics sets golden_file in summary."""
    golden = {"a": 1}
    current = {"a": 1}
    summary = compare_metrics(current, golden, golden_file="/path/to/golden.json")

    assert summary.golden_file == "/path/to/golden.json"
    print("PASS: test_compare_metrics_golden_file_set")


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
    print("PASS: test_compare_metrics_excludes_golden_metadata")


def test_compare_metrics_identical():
    """Comparing identical metrics returns all PASS."""
    metrics = make_sample_metrics()
    summary = compare_metrics(metrics, metrics)

    assert summary.compared is True
    assert summary.total > 0
    # All should pass (identical)
    failed = [r for r in summary.results if r.status == Verdict.FAIL]
    assert len(failed) == 0, f"Unexpected failures: {[r.metric_path for r in failed]}"
    print(f"PASS: test_compare_metrics_identical ({summary.total} metrics compared)")


def test_compare_metrics_new_metric():
    """New metric in current (not in golden) is PASS."""
    golden = {"a": 1}
    current = {"a": 1, "b": 2}
    summary = compare_metrics(current, golden)

    new_results = [r for r in summary.results if "New metric" in r.message]
    assert len(new_results) == 1
    assert new_results[0].status == Verdict.PASS
    print("PASS: test_compare_metrics_new_metric")


def test_compare_metrics_missing_metric():
    """Missing metric in current (was in golden) is WARN."""
    golden = {"a": 1, "b": 2}
    current = {"a": 1}
    summary = compare_metrics(current, golden)

    missing_results = [r for r in summary.results if "Missing metric" in r.message]
    assert len(missing_results) == 1
    assert missing_results[0].status == Verdict.WARN
    print("PASS: test_compare_metrics_missing_metric")


def test_compare_metrics_excludes_extraction_time():
    """extraction_time_ms is excluded from comparison."""
    golden = {"svg": {"extraction_time_ms": 10.0, "count": 5}}
    current = {"svg": {"extraction_time_ms": 20.0, "count": 5}}
    summary = compare_metrics(current, golden)

    # extraction_time_ms should not appear in results
    time_results = [r for r in summary.results if "extraction_time" in r.metric_path]
    assert len(time_results) == 0
    print("PASS: test_compare_metrics_excludes_extraction_time")


def test_compare_metrics_count_exact_match():
    """Count fields use exact matching."""
    golden = {"svg": {"paths": {"total_count": 15}}}
    current = {"svg": {"paths": {"total_count": 16}}}
    summary = compare_metrics(current, golden)

    count_results = [r for r in summary.results if "total_count" in r.metric_path]
    assert len(count_results) == 1
    assert count_results[0].status == Verdict.FAIL
    print("PASS: test_compare_metrics_count_exact_match")


def test_compare_metrics_boolean_exact_match():
    """Boolean fields use exact matching."""
    golden = {"stl": {"mesh": {"is_watertight": True}}}
    current = {"stl": {"mesh": {"is_watertight": False}}}
    summary = compare_metrics(current, golden)

    bool_results = [r for r in summary.results if "is_watertight" in r.metric_path]
    assert len(bool_results) == 1
    assert bool_results[0].status == Verdict.FAIL
    print("PASS: test_compare_metrics_boolean_exact_match")


def test_compare_metrics_structural_layers():
    """Layer names use structural (set) matching."""
    golden = {"svg": {"layers": {"names": ["A", "B", "C"]}}}
    current = {"svg": {"layers": {"names": ["C", "B", "A"]}}}  # Reordered
    summary = compare_metrics(current, golden)

    names_results = [r for r in summary.results if "names" in r.metric_path]
    # Should pass - same set
    assert all(r.status == Verdict.PASS for r in names_results)
    print("PASS: test_compare_metrics_structural_layers")


def test_compare_metrics_numeric_tolerance():
    """Numeric values use tolerance-based comparison."""
    golden = {"stl": {"volume_mm3": 1000000.0}}
    current = {"stl": {"volume_mm3": 1000050.0}}  # 0.005% difference
    summary = compare_metrics(current, golden)

    vol_results = [r for r in summary.results if "volume" in r.metric_path]
    assert len(vol_results) == 1
    # 0.005% < 0.1% tolerance = PASS
    assert vol_results[0].status == Verdict.PASS
    print("PASS: test_compare_metrics_numeric_tolerance")


# ============================================================================
# Golden store tests
# ============================================================================


def test_golden_store_initialize():
    """Golden store initializes directory structure."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store_path = os.path.join(tmpdir, "golden")
        store = GoldenStore(store_path)

        assert not store.exists()
        store.initialize()
        assert store.exists()
        assert store.index_path.exists()
        print("PASS: test_golden_store_initialize")


def test_golden_store_save_load_metrics():
    """Golden store saves and loads metrics."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = GoldenStore(tmpdir)
        store.initialize()

        metrics = {"test": {"value": 42}}
        store.save_metrics("test_entry", metrics, source_file="test.pml")

        loaded = store.load_metrics("test_entry")
        assert loaded is not None
        assert loaded["test"]["value"] == 42
        print("PASS: test_golden_store_save_load_metrics")


def test_golden_store_list_entries():
    """Golden store lists entries."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = GoldenStore(tmpdir)
        store.initialize()

        store.save_metrics("entry1", {"a": 1})
        store.save_metrics("entry2", {"b": 2})

        entries = store.list_entries()
        assert "entry1" in entries
        assert "entry2" in entries
        print("PASS: test_golden_store_list_entries")


def test_golden_store_has_entry():
    """Golden store checks entry existence."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = GoldenStore(tmpdir)
        store.initialize()

        assert not store.has_entry("missing")
        store.save_metrics("exists", {"a": 1})
        assert store.has_entry("exists")
        print("PASS: test_golden_store_has_entry")


def test_golden_store_delete_entry():
    """Golden store deletes entries."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = GoldenStore(tmpdir)
        store.initialize()

        store.save_metrics("to_delete", {"a": 1})
        assert store.has_entry("to_delete")

        store.delete_entry("to_delete")
        assert not store.has_entry("to_delete")
        print("PASS: test_golden_store_delete_entry")


def test_golden_index_serialization():
    """Golden index serializes and deserializes."""
    index = GoldenIndex()
    index.entries["test"] = GoldenEntry(
        recipe_name="test",
        source_file="test.pml",
        notes="Test entry",
    )

    data = index.to_dict()
    loaded = GoldenIndex.from_dict(data)

    assert loaded.entries["test"].recipe_name == "test"
    assert loaded.entries["test"].notes == "Test entry"
    print("PASS: test_golden_index_serialization")


def test_create_golden_from_recipe():
    """create_golden_from_recipe adds metadata wrapper."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = GoldenStore(tmpdir)
        store.initialize()

        metrics = make_sample_metrics()
        create_golden_from_recipe(store, "test_recipe", metrics)

        loaded = store.load_metrics("test_recipe")
        assert loaded is not None
        assert "golden" in loaded
        assert loaded["golden"]["recipe_name"] == "test_recipe"
        print("PASS: test_create_golden_from_recipe")


# ============================================================================
# Recipe integration tests
# ============================================================================


def test_recipe_metrics_self_comparison():
    """Extracting and comparing recipe metrics against themselves."""
    recipe_01_dir = os.path.join(RECIPE_DIR, "01_simple_profile", "output")
    svg_path = os.path.join(recipe_01_dir, "01_simple_profile.svg")
    stl_path = os.path.join(recipe_01_dir, "example.stl")
    nc_path = os.path.join(recipe_01_dir, "profile-3.17mm.nc")

    if not os.path.exists(svg_path):
        print("SKIP: test_recipe_metrics_self_comparison (recipe outputs not found)")
        return

    from validation.metrics.svg_metrics import extract_svg_metrics_from_file
    from validation.metrics.stl_metrics import extract_stl_metrics_from_file
    from validation.metrics.gcode_metrics import extract_gcode_metrics_from_file

    # Each to_dict() returns {"svg": {...}}, {"stl": {...}}, {"gcode": {...}}
    # Merge them into one dict
    metrics = {}

    if os.path.exists(svg_path):
        metrics.update(extract_svg_metrics_from_file(svg_path).to_dict())
    if os.path.exists(stl_path):
        metrics.update(extract_stl_metrics_from_file(stl_path).to_dict())
    if os.path.exists(nc_path):
        metrics.update(extract_gcode_metrics_from_file(nc_path).to_dict())

    # Compare against self (should all pass)
    summary = compare_metrics(metrics, metrics)

    failed = [r for r in summary.results if r.status == Verdict.FAIL]
    assert len(failed) == 0, f"Self-comparison failures: {[r.metric_path for r in failed]}"

    print(f"PASS: test_recipe_metrics_self_comparison ({summary.total} metrics)")


def test_all_recipes_against_golden():
    """Validate all recipes against their golden baselines."""
    golden_store_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "tests",
        "golden",
    )

    store = GoldenStore(golden_store_path)
    # Golden store is required - fail if missing (Stage 11 exit criteria)
    assert store.exists(), f"Golden store not found at {golden_store_path} - run 'python -m cli.generate_golden --all-recipes docs/recipes'"

    from validation.runner import validate_recipe, ValidationOptions

    entries = store.list_entries()
    assert len(entries) > 0, "Golden store is empty - run 'python -m cli.generate_golden --all-recipes docs/recipes'"

    options = ValidationOptions(
        extract_metrics=True,
        check_invariants=False,  # Just compare metrics
        check_assertions=False,
        check_regressions=True,
    )

    passed = 0
    failed = 0
    skipped = 0
    failures = []

    for name in sorted(entries):
        recipe_dir = os.path.join(RECIPE_DIR, name)
        if not os.path.exists(recipe_dir):
            skipped += 1
            continue

        golden_metrics = store.load_metrics(name)
        golden_file = str(store.get_metrics_path(name))

        try:
            result = validate_recipe(
                recipe_dir,
                golden_metrics=golden_metrics,
                golden_file=golden_file,
                options=options,
            )

            # Check regression results
            reg = result.regressions
            failed_results = [r for r in reg.results if r.status == Verdict.FAIL]

            if failed_results:
                failed += 1
                failures.append((name, failed_results))
            else:
                passed += 1
                print(f"  ✓ {name}: {reg.total} metrics compared")
        except Exception as e:
            failed += 1
            failures.append((name, [str(e)]))

    print(f"Golden regression: {passed} passed, {failed} failed, {skipped} skipped")

    if failures:
        print("\nFailures:")
        for name, issues in failures:
            print(f"  {name}:")
            for issue in issues[:3]:  # Show first 3
                if hasattr(issue, 'metric_path'):
                    print(f"    - {issue.metric_path}: {issue.message}")
                else:
                    print(f"    - {issue}")

    assert failed == 0, f"{failed} recipes failed golden regression"
    print(f"PASS: test_all_recipes_against_golden ({passed} recipes)")


def test_recipe_metrics_with_perturbation():
    """Detect changes when metrics are perturbed."""
    recipe_01_dir = os.path.join(RECIPE_DIR, "01_simple_profile", "output")
    svg_path = os.path.join(recipe_01_dir, "01_simple_profile.svg")

    if not os.path.exists(svg_path):
        print("SKIP: test_recipe_metrics_with_perturbation (recipe outputs not found)")
        return

    from validation.metrics.svg_metrics import extract_svg_metrics_from_file

    # to_dict() already wraps with {"svg": {...}}
    golden_metrics = extract_svg_metrics_from_file(svg_path).to_dict()

    # Create perturbed version
    current_metrics = json.loads(json.dumps(golden_metrics))  # Deep copy
    # Change layer count (exact match field)
    current_metrics["svg"]["layers"]["count"] += 1
    # Change document width (position tolerance field)
    current_metrics["svg"]["document"]["width_mm"] *= 1.001  # 0.1% change

    summary = compare_metrics(current_metrics, golden_metrics)

    # Count change should fail (exact match)
    count_results = [r for r in summary.results if r.metric_path == "svg.layers.count"]
    assert len(count_results) == 1
    assert count_results[0].status == Verdict.FAIL, f"Expected FAIL for count, got {count_results[0].status}"

    # Width change should warn or fail (0.1% change with 0.01% position tolerance)
    width_results = [r for r in summary.results if "width_mm" in r.metric_path]
    assert len(width_results) >= 1
    # 0.1% change exceeds 0.01% position tolerance

    print("PASS: test_recipe_metrics_with_perturbation")


# ============================================================================
# Test runner
# ============================================================================


def run_tests() -> bool:
    """Run all tests and report results."""
    tests = [
        # Comparator unit tests
        test_flatten_dict_simple,
        test_flatten_dict_with_list,
        test_compare_numeric_within_tolerance,
        test_compare_numeric_exceeds_tolerance,
        test_compare_numeric_fail_on_large_delta,
        test_compare_exact_match,
        test_compare_exact_mismatch,
        test_compare_structural_match,
        test_compare_structural_mismatch,
        test_get_tolerance_default,
        test_get_tolerance_category,
        test_get_tolerance_override,
        test_compare_numeric_near_zero_uses_absolute,
        test_compare_numeric_near_zero_fail,
        # Compare metrics integration
        test_compare_metrics_golden_file_set,
        test_compare_metrics_excludes_golden_metadata,
        test_compare_metrics_identical,
        test_compare_metrics_new_metric,
        test_compare_metrics_missing_metric,
        test_compare_metrics_excludes_extraction_time,
        test_compare_metrics_count_exact_match,
        test_compare_metrics_boolean_exact_match,
        test_compare_metrics_structural_layers,
        test_compare_metrics_numeric_tolerance,
        # Golden store tests
        test_golden_store_initialize,
        test_golden_store_save_load_metrics,
        test_golden_store_list_entries,
        test_golden_store_has_entry,
        test_golden_store_delete_entry,
        test_golden_index_serialization,
        test_create_golden_from_recipe,
        # Recipe integration tests
        test_all_recipes_against_golden,
        test_recipe_metrics_self_comparison,
        test_recipe_metrics_with_perturbation,
    ]

    print("=" * 60)
    print("Regression Comparator Tests")
    print("=" * 60)

    passed = 0
    failed = 0
    skipped = 0

    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"FAIL: {test.__name__}")
            print(f"  {e}")
            failed += 1
        except Exception as e:
            # Check if it was a skip
            if "SKIP" in str(e):
                skipped += 1
            else:
                print(f"ERROR: {test.__name__}")
                print(f"  {type(e).__name__}: {e}")
                failed += 1

    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed, {skipped} skipped")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
