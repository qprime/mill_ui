# tests/test_stl_invariants.py - Unit tests for STL invariant checking
#
# Tests verify:
# 1. All 9 STL invariants are checked correctly
# 2. Valid STLs pass all invariants
# 3. Invalid STLs fail the appropriate invariants
# 4. No false positives on recipe outputs
# 5. Clear failure messages

from __future__ import annotations

import os
import sys
import tempfile

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from validation.invariants.stl_invariants import (
    check_stl_invariants,
    STL_INVARIANT_IDS,
)
from validation.core import Verdict


# Path to recipe outputs
RECIPE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "docs",
    "recipes",
)


def get_recipe_stl_path(recipe_num: int, recipe_name: str, filename: str) -> str:
    """Get path to a recipe's STL output."""
    return os.path.join(
        RECIPE_DIR,
        f"{recipe_num:02d}_{recipe_name}",
        "output",
        filename,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Test: Valid STL Invariants
# ─────────────────────────────────────────────────────────────────────────────


def test_valid_simple_profile_stl():
    """Test that simple profile STL passes all invariants."""
    stl_path = get_recipe_stl_path(1, "simple_profile", "example.stl")

    if not os.path.exists(stl_path):
        print(f"SKIP: {stl_path} not found")
        return

    results = check_stl_invariants(stl_path)

    # Should check all expected invariants
    result_ids = [r.id for r in results]
    for inv_id in STL_INVARIANT_IDS:
        assert inv_id in result_ids, f"Missing invariant check: {inv_id}"

    # All should pass (or warn, which is acceptable)
    for r in results:
        assert r.status in (Verdict.PASS, Verdict.WARN), (
            f"{r.id} failed: {r.details}"
        )

    print("PASS: test_valid_simple_profile_stl")


def test_valid_shaker_door_stl():
    """Test that shaker door STL (with pockets) passes all invariants."""
    stl_path = get_recipe_stl_path(3, "shaker_door_template", "example.stl")

    if not os.path.exists(stl_path):
        print(f"SKIP: {stl_path} not found")
        return

    results = check_stl_invariants(stl_path)

    # All should pass (or warn)
    failures = [r for r in results if r.status == Verdict.FAIL]
    assert len(failures) == 0, (
        f"Unexpected failures: {[(f.id, f.details) for f in failures]}"
    )

    print("PASS: test_valid_shaker_door_stl")


def test_valid_multiple_depths_stl():
    """Test that multiple depths STL passes all invariants."""
    stl_path = get_recipe_stl_path(6, "multiple_depths", "example.stl")

    if not os.path.exists(stl_path):
        print(f"SKIP: {stl_path} not found")
        return

    results = check_stl_invariants(stl_path)

    failures = [r for r in results if r.status == Verdict.FAIL]
    assert len(failures) == 0, (
        f"Unexpected failures: {[(f.id, f.details) for f in failures]}"
    )

    print("PASS: test_valid_multiple_depths_stl")


# ─────────────────────────────────────────────────────────────────────────────
# Test: Invalid STL File
# ─────────────────────────────────────────────────────────────────────────────


def test_invalid_stl_file():
    """Test that invalid STL file fails STL_VALID_FILE invariant."""
    # Create a temp file with invalid content
    with tempfile.NamedTemporaryFile(suffix=".stl", delete=False) as f:
        f.write(b"not a valid stl file content")
        temp_path = f.name

    try:
        results = check_stl_invariants(temp_path)

        # First invariant should fail
        assert results[0].id == "STL_VALID_FILE"
        assert results[0].status == Verdict.FAIL

        # All other invariants should be skipped
        for r in results[1:]:
            assert r.details.get("skipped") is True, f"{r.id} was not skipped"

        print("PASS: test_invalid_stl_file")
    finally:
        os.unlink(temp_path)


def test_nonexistent_stl_file():
    """Test that nonexistent file fails STL_VALID_FILE."""
    results = check_stl_invariants("/nonexistent/path/to/file.stl")

    assert results[0].id == "STL_VALID_FILE"
    assert results[0].status == Verdict.FAIL
    # Error message could say "not found" or "is not a file"
    error_msg = str(results[0].details).lower()
    assert "not found" in error_msg or "not a file" in error_msg

    print("PASS: test_nonexistent_stl_file")


def test_empty_stl_file():
    """Test that empty STL file fails STL_VALID_FILE."""
    with tempfile.NamedTemporaryFile(suffix=".stl", delete=False) as f:
        # Write empty file
        temp_path = f.name

    try:
        results = check_stl_invariants(temp_path)

        assert results[0].id == "STL_VALID_FILE"
        assert results[0].status == Verdict.FAIL

        print("PASS: test_empty_stl_file")
    finally:
        os.unlink(temp_path)


# ─────────────────────────────────────────────────────────────────────────────
# Test: STL Metrics Properties
# ─────────────────────────────────────────────────────────────────────────────


def test_positive_volume_pass():
    """Test that valid STL has positive volume."""
    stl_path = get_recipe_stl_path(1, "simple_profile", "example.stl")

    if not os.path.exists(stl_path):
        print(f"SKIP: {stl_path} not found")
        return

    results = check_stl_invariants(stl_path)

    volume_result = next(r for r in results if r.id == "STL_POSITIVE_VOLUME")
    assert volume_result.status == Verdict.PASS
    assert volume_result.details.get("volume_mm3", 0) > 0

    print("PASS: test_positive_volume_pass")


def test_is_watertight_pass():
    """Test that valid STL is watertight."""
    stl_path = get_recipe_stl_path(1, "simple_profile", "example.stl")

    if not os.path.exists(stl_path):
        print(f"SKIP: {stl_path} not found")
        return

    results = check_stl_invariants(stl_path)

    watertight_result = next(r for r in results if r.id == "STL_IS_WATERTIGHT")
    assert watertight_result.status == Verdict.PASS
    assert watertight_result.details.get("is_watertight") is True

    print("PASS: test_is_watertight_pass")


def test_is_manifold_pass():
    """Test that valid STL is manifold."""
    stl_path = get_recipe_stl_path(1, "simple_profile", "example.stl")

    if not os.path.exists(stl_path):
        print(f"SKIP: {stl_path} not found")
        return

    results = check_stl_invariants(stl_path)

    manifold_result = next(r for r in results if r.id == "STL_IS_MANIFOLD")
    assert manifold_result.status == Verdict.PASS
    assert manifold_result.details.get("is_manifold") is True

    print("PASS: test_is_manifold_pass")


def test_consistent_normals_pass():
    """Test that valid STL has consistent normals."""
    stl_path = get_recipe_stl_path(1, "simple_profile", "example.stl")

    if not os.path.exists(stl_path):
        print(f"SKIP: {stl_path} not found")
        return

    results = check_stl_invariants(stl_path)

    normals_result = next(r for r in results if r.id == "STL_CONSISTENT_NORMALS")
    assert normals_result.status == Verdict.PASS

    print("PASS: test_consistent_normals_pass")


def test_no_degenerate_faces_pass():
    """Test that valid STL has no degenerate faces."""
    stl_path = get_recipe_stl_path(1, "simple_profile", "example.stl")

    if not os.path.exists(stl_path):
        print(f"SKIP: {stl_path} not found")
        return

    results = check_stl_invariants(stl_path)

    degen_result = next(r for r in results if r.id == "STL_NO_DEGENERATE_FACES")
    assert degen_result.status == Verdict.PASS
    assert degen_result.details.get("degenerate_count") == 0

    print("PASS: test_no_degenerate_faces_pass")


def test_bounds_positive_pass():
    """Test that valid STL has positive bounds."""
    stl_path = get_recipe_stl_path(1, "simple_profile", "example.stl")

    if not os.path.exists(stl_path):
        print(f"SKIP: {stl_path} not found")
        return

    results = check_stl_invariants(stl_path)

    bounds_result = next(r for r in results if r.id == "STL_BOUNDS_POSITIVE")
    assert bounds_result.status == Verdict.PASS
    assert bounds_result.details.get("width_mm", 0) > 0
    assert bounds_result.details.get("height_mm", 0) > 0
    assert bounds_result.details.get("thickness_mm", 0) > 0

    print("PASS: test_bounds_positive_pass")


def test_z_within_sheet_pass():
    """Test that valid STL has Z within sheet bounds."""
    stl_path = get_recipe_stl_path(1, "simple_profile", "example.stl")

    if not os.path.exists(stl_path):
        print(f"SKIP: {stl_path} not found")
        return

    results = check_stl_invariants(stl_path, sheet_thickness_mm=19.0)

    z_result = next(r for r in results if r.id == "STL_Z_WITHIN_SHEET")
    assert z_result.status == Verdict.PASS
    assert z_result.details.get("min_z", -1) >= 0
    assert z_result.details.get("max_z", 100) <= 19.0

    print("PASS: test_z_within_sheet_pass")


def test_connected_single_component():
    """Test that valid STL has single connected component."""
    stl_path = get_recipe_stl_path(1, "simple_profile", "example.stl")

    if not os.path.exists(stl_path):
        print(f"SKIP: {stl_path} not found")
        return

    results = check_stl_invariants(stl_path, expected_components=1)

    conn_result = next(r for r in results if r.id == "STL_CONNECTED")
    assert conn_result.status == Verdict.PASS
    assert conn_result.details.get("connected_components") == 1

    print("PASS: test_connected_single_component")


# ─────────────────────────────────────────────────────────────────────────────
# Test: Z Within Sheet Failure
# ─────────────────────────────────────────────────────────────────────────────


def test_z_within_sheet_fail_undersized():
    """Test that Z within sheet fails for undersized sheet."""
    stl_path = get_recipe_stl_path(1, "simple_profile", "example.stl")

    if not os.path.exists(stl_path):
        print(f"SKIP: {stl_path} not found")
        return

    # Sheet thickness smaller than mesh Z range should fail
    results = check_stl_invariants(stl_path, sheet_thickness_mm=10.0)

    z_result = next(r for r in results if r.id == "STL_Z_WITHIN_SHEET")
    # This depends on the actual STL - if max_z > 10, it should fail
    # Most recipe STLs are 19mm thick, so this should fail
    if z_result.details.get("max_z", 0) > 10.0:
        assert z_result.status == Verdict.FAIL
        assert "max_z" in str(z_result.details.get("issues", []))

    print("PASS: test_z_within_sheet_fail_undersized")


# ─────────────────────────────────────────────────────────────────────────────
# Test: Connected Component Warnings
# ─────────────────────────────────────────────────────────────────────────────


def test_connected_wrong_count_warns():
    """Test that unexpected component count produces appropriate verdict."""
    stl_path = get_recipe_stl_path(1, "simple_profile", "example.stl")

    if not os.path.exists(stl_path):
        print(f"SKIP: {stl_path} not found")
        return

    # Expect 5 components when there's only 1 - should warn
    results = check_stl_invariants(stl_path, expected_components=5)

    conn_result = next(r for r in results if r.id == "STL_CONNECTED")
    # Having fewer components than expected is a FAIL
    assert conn_result.status == Verdict.FAIL
    assert "expected" in str(conn_result.details)

    print("PASS: test_connected_wrong_count_warns")


# ─────────────────────────────────────────────────────────────────────────────
# Test: Recipe STL Validation (No False Positives)
# ─────────────────────────────────────────────────────────────────────────────


def test_all_recipe_stls_pass():
    """Test that all recipe STLs pass invariants (no false positives)."""
    recipe_stls = [
        (1, "simple_profile", "example.stl"),
        (2, "pocket_with_cleanup", "example.stl"),
        (3, "shaker_door_template", "example.stl"),
        (4, "custom_template", "example.stl"),
        (5, "validation_workflow", "example.stl"),
        (6, "multiple_depths", "example.stl"),
        (7, "json_generation", "example.stl"),
        (8, "svg_visualization", "example.stl"),
        (9, "config_tuning", "example.stl"),
        # Recipe 10 (hole_patterns_grid) does not produce STL
        (11, "keepout_islands", "example.stl"),
        (12, "edge_treatment_intent", "example.stl"),
        (13, "split_layout_french_door", "example.stl"),
        (14, "corner_cleanup_multi_tool", "example.stl"),
        (15, "profile_with_tabs", "simple_cutout_with_tabs.stl"),
        (16, "sheet_layout_nesting", "example.stl"),
        # Recipes 17-18 (nesting) do not produce STL
    ]

    passed = 0
    skipped = 0
    failed_stls = []

    for recipe_num, recipe_name, filename in recipe_stls:
        stl_path = get_recipe_stl_path(recipe_num, recipe_name, filename)

        if not os.path.exists(stl_path):
            skipped += 1
            continue

        results = check_stl_invariants(stl_path)

        failures = [r for r in results if r.status == Verdict.FAIL]
        if failures:
            failed_stls.append(
                (f"{recipe_num:02d}_{recipe_name}/{filename}",
                 [(f.id, f.details.get("message", str(f.details))) for f in failures])
            )
        else:
            passed += 1

    if failed_stls:
        print(f"FAIL: {len(failed_stls)} recipe STLs failed invariants:")
        for filename, fails in failed_stls:
            print(f"  {filename}: {fails}")
        assert False, f"{len(failed_stls)} recipe STLs failed invariants"

    print(f"PASS: test_all_recipe_stls_pass ({passed} passed, {skipped} skipped)")


# ─────────────────────────────────────────────────────────────────────────────
# Test: Invariant Result Structure
# ─────────────────────────────────────────────────────────────────────────────


def test_invariant_result_to_dict():
    """Test that invariant results serialize correctly."""
    stl_path = get_recipe_stl_path(1, "simple_profile", "example.stl")

    if not os.path.exists(stl_path):
        print(f"SKIP: {stl_path} not found")
        return

    results = check_stl_invariants(stl_path)

    for r in results:
        d = r.to_dict()
        assert "invariant" in d
        assert "id" in d["invariant"]
        assert "category" in d["invariant"]
        assert "artifact" in d["invariant"]
        assert "description" in d["invariant"]
        assert "status" in d["invariant"]
        assert "details" in d["invariant"]

    print("PASS: test_invariant_result_to_dict")


def test_all_invariant_ids_present():
    """Test that all expected invariant IDs are returned."""
    stl_path = get_recipe_stl_path(1, "simple_profile", "example.stl")

    if not os.path.exists(stl_path):
        print(f"SKIP: {stl_path} not found")
        return

    results = check_stl_invariants(stl_path)
    result_ids = [r.id for r in results]

    for expected_id in STL_INVARIANT_IDS:
        assert expected_id in result_ids, f"Missing invariant: {expected_id}"

    print("PASS: test_all_invariant_ids_present")


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────


def run_all_tests():
    """Run all STL invariant tests."""
    tests = [
        # Valid STL tests
        test_valid_simple_profile_stl,
        test_valid_shaker_door_stl,
        test_valid_multiple_depths_stl,
        # Invalid file tests
        test_invalid_stl_file,
        test_nonexistent_stl_file,
        test_empty_stl_file,
        # Individual invariant tests
        test_positive_volume_pass,
        test_is_watertight_pass,
        test_is_manifold_pass,
        test_consistent_normals_pass,
        test_no_degenerate_faces_pass,
        test_bounds_positive_pass,
        test_z_within_sheet_pass,
        test_connected_single_component,
        # Failure cases
        test_z_within_sheet_fail_undersized,
        test_connected_wrong_count_warns,
        # Recipe validation tests
        test_all_recipe_stls_pass,
        # Result structure tests
        test_invariant_result_to_dict,
        test_all_invariant_ids_present,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"FAIL: {test.__name__}: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print(f"\n{'='*60}")
    print(f"STL Invariant Tests: {passed} passed, {failed} failed")
    print(f"{'='*60}")

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
