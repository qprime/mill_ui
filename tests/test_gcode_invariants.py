# tests/test_gcode_invariants.py - Unit tests for G-code invariant checking
#
# Tests verify:
# 1. All 10 G-code invariants are checked correctly
# 2. Valid G-code passes all invariants
# 3. Invalid G-code fails the appropriate invariants
# 4. No false positives on recipe outputs
# 5. Clear failure messages

from __future__ import annotations

import os
import sys
import tempfile

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from validation.core import Verdict
from validation.invariants.gcode_invariants import (
    GCODE_INVARIANT_IDS,
    check_gcode_invariants,
)

# Path to recipe outputs
RECIPE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "docs",
    "recipes",
)


def get_recipe_nc_path(recipe_num: int, recipe_name: str, filename: str) -> str:
    """Get path to a recipe's NC output."""
    return os.path.join(
        RECIPE_DIR,
        f"{recipe_num:02d}_{recipe_name}",
        "output",
        filename,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Test: Valid G-code Invariants
# ─────────────────────────────────────────────────────────────────────────────


def test_valid_simple_profile_gcode():
    """Test that simple profile G-code passes all invariants."""
    nc_path = get_recipe_nc_path(1, "simple_profile", "profile-3.17mm.nc")

    if not os.path.exists(nc_path):
        print(f"SKIP: {nc_path} not found")
        return

    results = check_gcode_invariants(nc_path)

    # Should check all expected invariants
    result_ids = [r.id for r in results]
    for inv_id in GCODE_INVARIANT_IDS:
        assert inv_id in result_ids, f"Missing invariant check: {inv_id}"

    # All should pass (or warn, which is acceptable)
    for r in results:
        assert r.status in (Verdict.PASS, Verdict.WARN), f"{r.id} failed: {r.failures} {r.details}"

    print("PASS: test_valid_simple_profile_gcode")


def test_valid_shaker_door_gcode():
    """Test that shaker door G-code (with pockets) passes all invariants."""
    nc_path = get_recipe_nc_path(3, "shaker_door_template", "pocket-9.53mm.nc")

    if not os.path.exists(nc_path):
        print(f"SKIP: {nc_path} not found")
        return

    results = check_gcode_invariants(nc_path)

    # All should pass (or warn)
    failures = [r for r in results if r.status == Verdict.FAIL]
    assert len(failures) == 0, f"Unexpected failures: {[(f.id, f.failures) for f in failures]}"

    print("PASS: test_valid_shaker_door_gcode")


def test_valid_multiple_depths_gcode():
    """Test that multiple depths G-code passes all invariants."""
    nc_path = get_recipe_nc_path(6, "multiple_depths", "pocket-9.53mm.nc")

    if not os.path.exists(nc_path):
        print(f"SKIP: {nc_path} not found")
        return

    results = check_gcode_invariants(nc_path)

    failures = [r for r in results if r.status == Verdict.FAIL]
    assert len(failures) == 0, f"Unexpected failures: {[(f.id, f.failures) for f in failures]}"

    print("PASS: test_valid_multiple_depths_gcode")


# ─────────────────────────────────────────────────────────────────────────────
# Test: Invalid G-code File
# ─────────────────────────────────────────────────────────────────────────────


def test_invalid_gcode_file():
    """Test that invalid G-code file fails GCODE_PARSEABLE invariant."""
    # Create a temp file with invalid content
    with tempfile.NamedTemporaryFile(mode="w", suffix=".nc", delete=False) as f:
        f.write("@#$%^& not valid gcode at all!\n")
        f.write("more garbage lines\n")
        temp_path = f.name

    try:
        results = check_gcode_invariants(temp_path)

        # First invariant should fail
        assert results[0].id == "GCODE_PARSEABLE"
        assert results[0].status == Verdict.FAIL

        # All other invariants should be skipped
        for r in results[1:]:
            assert r.details.get("skipped") is True, f"{r.id} was not skipped"

        print("PASS: test_invalid_gcode_file")
    finally:
        os.unlink(temp_path)


def test_nonexistent_gcode_file():
    """Test that nonexistent file fails GCODE_PARSEABLE."""
    results = check_gcode_invariants("/nonexistent/path/to/file.nc")

    assert results[0].id == "GCODE_PARSEABLE"
    assert results[0].status == Verdict.FAIL
    assert "not found" in str(results[0].failures).lower()

    print("PASS: test_nonexistent_gcode_file")


def test_empty_gcode_file():
    """Test that empty G-code file fails GCODE_PARSEABLE."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".nc", delete=False) as f:
        # Write empty file
        temp_path = f.name

    try:
        results = check_gcode_invariants(temp_path)

        assert results[0].id == "GCODE_PARSEABLE"
        assert results[0].status == Verdict.FAIL

        print("PASS: test_empty_gcode_file")
    finally:
        os.unlink(temp_path)


# ─────────────────────────────────────────────────────────────────────────────
# Test: Safe Z Violations
# ─────────────────────────────────────────────────────────────────────────────


def test_safe_z_violation():
    """Test that G0 rapid below safe_z fails GCODE_SAFE_Z_RESPECTED."""
    gcode = """
(Test program)
G21 G90
G0 Z5.0
G0 X0 Y0
G0 Z1.0
G0 X10 Y10
M30
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".nc", delete=False) as f:
        f.write(gcode)
        temp_path = f.name

    try:
        # Safe Z is 5.0, but we rapid at Z1.0
        results = check_gcode_invariants(temp_path, safe_z_mm=5.0)

        safe_z_result = next(r for r in results if r.id == "GCODE_SAFE_Z_RESPECTED")
        assert safe_z_result.status == Verdict.FAIL
        assert "Z=1.0" in str(safe_z_result.failures) or "Z=1" in str(safe_z_result.failures)

        print("PASS: test_safe_z_violation")
    finally:
        os.unlink(temp_path)


def test_safe_z_respected():
    """Test that G0 rapids at or above safe_z pass."""
    gcode = """
(Test program)
G21 G90
G0 Z10.0
G0 X0 Y0
G0 Z5.0
G0 X10 Y10
G0 Z10.0
M30
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".nc", delete=False) as f:
        f.write(gcode)
        temp_path = f.name

    try:
        results = check_gcode_invariants(temp_path, safe_z_mm=5.0)

        safe_z_result = next(r for r in results if r.id == "GCODE_SAFE_Z_RESPECTED")
        assert safe_z_result.status == Verdict.PASS

        print("PASS: test_safe_z_respected")
    finally:
        os.unlink(temp_path)


# ─────────────────────────────────────────────────────────────────────────────
# Test: Negative Feed Rate
# ─────────────────────────────────────────────────────────────────────────────


def test_negative_feed_rate():
    """Test that negative feed rate fails GCODE_NO_NEGATIVE_FEED."""
    gcode = """
(Test program)
G21 G90
G0 Z5.0
G0 X0 Y0
G1 Z-1.0 F0
G1 X10 Y10 F1000
M30
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".nc", delete=False) as f:
        f.write(gcode)
        temp_path = f.name

    try:
        results = check_gcode_invariants(temp_path)

        feed_result = next(r for r in results if r.id == "GCODE_NO_NEGATIVE_FEED")
        assert feed_result.status == Verdict.FAIL
        assert "F0" in str(feed_result.failures)

        print("PASS: test_negative_feed_rate")
    finally:
        os.unlink(temp_path)


# ─────────────────────────────────────────────────────────────────────────────
# Test: Max Stepdown
# ─────────────────────────────────────────────────────────────────────────────


def test_max_stepdown_exceeded():
    """Test that excessive stepdown fails GCODE_MAX_STEPDOWN."""
    gcode = """
(Test program)
G21 G90
G0 Z10.0
G0 X0 Y0
G1 Z-15.0 F1000
G1 X10 Y10
M30
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".nc", delete=False) as f:
        f.write(gcode)
        temp_path = f.name

    try:
        # 25mm stepdown (10 to -15) exceeds max of 10mm
        results = check_gcode_invariants(temp_path, max_stepdown_mm=10.0)

        stepdown_result = next(r for r in results if r.id == "GCODE_MAX_STEPDOWN")
        assert stepdown_result.status == Verdict.FAIL
        assert "25" in str(stepdown_result.failures)  # 25mm stepdown

        print("PASS: test_max_stepdown_exceeded")
    finally:
        os.unlink(temp_path)


def test_max_stepdown_respected():
    """Test that stepdowns within limit pass."""
    gcode = """
(Test program)
G21 G90
G0 Z10.0
G0 X0 Y0
G1 Z5.0 F1000
G1 Z0.0 F1000
G1 Z-5.0 F1000
G1 X10 Y10
M30
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".nc", delete=False) as f:
        f.write(gcode)
        temp_path = f.name

    try:
        results = check_gcode_invariants(temp_path, max_stepdown_mm=10.0)

        stepdown_result = next(r for r in results if r.id == "GCODE_MAX_STEPDOWN")
        assert stepdown_result.status == Verdict.PASS

        print("PASS: test_max_stepdown_respected")
    finally:
        os.unlink(temp_path)


# ─────────────────────────────────────────────────────────────────────────────
# Test: XY Bounds
# ─────────────────────────────────────────────────────────────────────────────


def test_xy_out_of_bounds():
    """Test that XY positions outside bounds fail GCODE_XY_WITHIN_BOUNDS."""
    gcode = """
(Test program)
G21 G90
G0 Z10.0
G0 X-100 Y0
G1 Z-5.0 F1000
G1 X500 Y500
M30
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".nc", delete=False) as f:
        f.write(gcode)
        temp_path = f.name

    try:
        # 100mm sheet with 10mm margin should fail for X=-100, X=500, Y=500
        results = check_gcode_invariants(temp_path, sheet_width_mm=100.0, sheet_height_mm=100.0, margin_mm=10.0)

        bounds_result = next(r for r in results if r.id == "GCODE_XY_WITHIN_BOUNDS")
        assert bounds_result.status == Verdict.FAIL

        print("PASS: test_xy_out_of_bounds")
    finally:
        os.unlink(temp_path)


# ─────────────────────────────────────────────────────────────────────────────
# Test: Spindle Before Cut
# ─────────────────────────────────────────────────────────────────────────────


def test_spindle_not_on_before_cut():
    """Test that cutting without spindle fails GCODE_SPINDLE_BEFORE_CUT."""
    gcode = """
(Test program)
G21 G90
G0 Z10.0
G0 X0 Y0
G1 Z-5.0 F1000
G1 X10 Y10 F1000
G0 Z10.0
M30
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".nc", delete=False) as f:
        f.write(gcode)
        temp_path = f.name

    try:
        results = check_gcode_invariants(temp_path)

        spindle_result = next(r for r in results if r.id == "GCODE_SPINDLE_BEFORE_CUT")
        assert spindle_result.status == Verdict.FAIL
        assert "without spindle" in str(spindle_result.failures).lower()

        print("PASS: test_spindle_not_on_before_cut")
    finally:
        os.unlink(temp_path)


def test_spindle_on_before_cut():
    """Test that proper spindle startup passes."""
    gcode = """
(Test program)
G21 G90
G0 Z10.0
G0 X0 Y0
M3 S12000
G1 Z-5.0 F1000
G1 X10 Y10 F1000
G0 Z10.0
M5
M30
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".nc", delete=False) as f:
        f.write(gcode)
        temp_path = f.name

    try:
        results = check_gcode_invariants(temp_path)

        spindle_result = next(r for r in results if r.id == "GCODE_SPINDLE_BEFORE_CUT")
        assert spindle_result.status == Verdict.PASS

        print("PASS: test_spindle_on_before_cut")
    finally:
        os.unlink(temp_path)


# ─────────────────────────────────────────────────────────────────────────────
# Test: Tool Declared
# ─────────────────────────────────────────────────────────────────────────────


def test_tool_change_without_declaration():
    """Test that M6 without prior T command fails GCODE_TOOL_DECLARED."""
    gcode = """
(Test program)
G21 G90
M6
G0 Z10.0
G0 X0 Y0
M30
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".nc", delete=False) as f:
        f.write(gcode)
        temp_path = f.name

    try:
        results = check_gcode_invariants(temp_path)

        tool_result = next(r for r in results if r.id == "GCODE_TOOL_DECLARED")
        assert tool_result.status == Verdict.FAIL
        assert "without" in str(tool_result.failures).lower()

        print("PASS: test_tool_change_without_declaration")
    finally:
        os.unlink(temp_path)


def test_tool_properly_declared():
    """Test that T before M6 passes."""
    gcode = """
(Test program)
G21 G90
T1 M6
G0 Z10.0
G0 X0 Y0
M30
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".nc", delete=False) as f:
        f.write(gcode)
        temp_path = f.name

    try:
        results = check_gcode_invariants(temp_path)

        tool_result = next(r for r in results if r.id == "GCODE_TOOL_DECLARED")
        assert tool_result.status == Verdict.PASS

        print("PASS: test_tool_properly_declared")
    finally:
        os.unlink(temp_path)


# ─────────────────────────────────────────────────────────────────────────────
# Test: Ends at Safe
# ─────────────────────────────────────────────────────────────────────────────


def test_ends_at_unsafe_z():
    """Test that ending at low Z fails GCODE_ENDS_AT_SAFE."""
    gcode = """
(Test program)
G21 G90
G0 Z10.0
G0 X0 Y0
M3 S12000
G1 Z-5.0 F1000
G1 X10 Y10 F1000
M5
M30
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".nc", delete=False) as f:
        f.write(gcode)
        temp_path = f.name

    try:
        results = check_gcode_invariants(temp_path, safe_z_mm=5.0)

        end_result = next(r for r in results if r.id == "GCODE_ENDS_AT_SAFE")
        assert end_result.status == Verdict.FAIL
        assert "-5" in str(end_result.failures)

        print("PASS: test_ends_at_unsafe_z")
    finally:
        os.unlink(temp_path)


def test_ends_at_safe_z():
    """Test that ending at safe Z passes."""
    gcode = """
(Test program)
G21 G90
G0 Z10.0
G0 X0 Y0
M3 S12000
G1 Z-5.0 F1000
G1 X10 Y10 F1000
G0 Z10.0
M5
M30
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".nc", delete=False) as f:
        f.write(gcode)
        temp_path = f.name

    try:
        results = check_gcode_invariants(temp_path, safe_z_mm=5.0)

        end_result = next(r for r in results if r.id == "GCODE_ENDS_AT_SAFE")
        assert end_result.status == Verdict.PASS

        print("PASS: test_ends_at_safe_z")
    finally:
        os.unlink(temp_path)


# ─────────────────────────────────────────────────────────────────────────────
# Test: Continuous Path
# ─────────────────────────────────────────────────────────────────────────────


def test_path_discontinuity():
    """Test that extremely large jumps during cutting are detected."""
    gcode = """
(Test program with discontinuous path - extreme teleportation)
G21 G90
G0 Z10.0
G0 X0 Y0
M3 S12000
G1 Z-5.0 F1000
G1 X10 Y10 F1000
G1 X6000 Y6000 F1000
G0 Z10.0
M5
M30
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".nc", delete=False) as f:
        f.write(gcode)
        temp_path = f.name

    try:
        results = check_gcode_invariants(temp_path)

        path_result = next(r for r in results if r.id == "GCODE_CONTINUOUS_PATH")
        # Very large jump (>5000mm fail threshold) should be flagged as FAIL
        assert path_result.status == Verdict.FAIL

        print("PASS: test_path_discontinuity")
    finally:
        os.unlink(temp_path)


def test_continuous_path():
    """Test that normal cutting path passes continuity check."""
    gcode = """
(Test program with continuous path)
G21 G90
G0 Z10.0
G0 X0 Y0
M3 S12000
G1 Z-5.0 F1000
G1 X10 Y10 F1000
G1 X20 Y10 F1000
G1 X20 Y20 F1000
G1 X10 Y20 F1000
G1 X10 Y10 F1000
G0 Z10.0
M5
M30
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".nc", delete=False) as f:
        f.write(gcode)
        temp_path = f.name

    try:
        results = check_gcode_invariants(temp_path)

        path_result = next(r for r in results if r.id == "GCODE_CONTINUOUS_PATH")
        assert path_result.status == Verdict.PASS

        print("PASS: test_continuous_path")
    finally:
        os.unlink(temp_path)


# ─────────────────────────────────────────────────────────────────────────────
# Test: Recipe G-code Validation (No False Positives)
# ─────────────────────────────────────────────────────────────────────────────


def test_all_recipe_gcodes_pass():
    """Test that all recipe G-code files pass invariants (no false positives)."""
    # Note: Actual recipe filenames use tool diameter suffix (profile-3.17mm.nc, pocket-9.53mm.nc)
    recipe_gcodes = [
        (1, "simple_profile", "profile-3.17mm.nc"),
        (2, "pocket_with_cleanup", "pocket-9.53mm.nc"),
        (3, "shaker_door_template", "pocket-9.53mm.nc"),
        (5, "validation_workflow", "profile-3.17mm.nc"),
        (6, "multiple_depths", "pocket-9.53mm.nc"),
        (7, "json_generation", "profile-3.17mm.nc"),
        (10, "hole_patterns_grid", "bore-3.17mm.nc"),
        (12, "edge_treatment_intent", "pocket-9.53mm.nc"),
        (13, "split_layout_french_door", "profile-3.17mm.nc"),
        (14, "corner_cleanup_multi_tool", "profile-3.17mm.nc"),
        (16, "sheet_layout_nesting", "profile-3.17mm.nc"),
        # Recipes 17-18 (nesting) produce multiple NC files with sheet prefix
    ]

    passed = 0
    skipped = 0
    failed_gcodes = []

    for recipe_num, recipe_name, filename in recipe_gcodes:
        nc_path = get_recipe_nc_path(recipe_num, recipe_name, filename)

        if not os.path.exists(nc_path):
            skipped += 1
            continue

        results = check_gcode_invariants(nc_path)

        failures = [r for r in results if r.status == Verdict.FAIL]
        if failures:
            failed_gcodes.append(
                (
                    f"{recipe_num:02d}_{recipe_name}/{filename}",
                    [(f.id, f.failures[:2] if f.failures else str(f.details)[:100]) for f in failures],
                )
            )
        else:
            passed += 1

    if failed_gcodes:
        print(f"FAIL: {len(failed_gcodes)} recipe G-codes failed invariants:")
        for filename, fails in failed_gcodes:
            print(f"  {filename}: {fails}")
        raise AssertionError(f"{len(failed_gcodes)} recipe G-codes failed invariants")

    print(f"PASS: test_all_recipe_gcodes_pass ({passed} passed, {skipped} skipped)")


# ─────────────────────────────────────────────────────────────────────────────
# Test: Invariant Result Structure
# ─────────────────────────────────────────────────────────────────────────────


def test_invariant_result_to_dict():
    """Test that invariant results serialize correctly."""
    nc_path = get_recipe_nc_path(1, "simple_profile", "profile-3.17mm.nc")

    if not os.path.exists(nc_path):
        print(f"SKIP: {nc_path} not found")
        return

    results = check_gcode_invariants(nc_path)

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
    nc_path = get_recipe_nc_path(1, "simple_profile", "profile-3.17mm.nc")

    if not os.path.exists(nc_path):
        print(f"SKIP: {nc_path} not found")
        return

    results = check_gcode_invariants(nc_path)
    result_ids = [r.id for r in results]

    for expected_id in GCODE_INVARIANT_IDS:
        assert expected_id in result_ids, f"Missing invariant: {expected_id}"

    print("PASS: test_all_invariant_ids_present")


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────


# ─────────────────────────────────────────────────────────────────────────────
# Test: Tab Pattern Detection
# ─────────────────────────────────────────────────────────────────────────────


def test_tab_pattern_detected():
    """Test that tabs are detected in G-code with lift-cross-plunge pattern."""
    gcode = """
(Profile with 4 tabs)
G21 G90
G0 Z6.0
G0 X0 Y0
M3 S18000
G1 Z-19.0 F500
G1 X100 Y0 F1500
G1 Z-16.0
G1 X120 Y0
G1 Z-19.0
G1 X200 Y0
G1 Z-16.0
G1 X220 Y0
G1 Z-19.0
G1 X300 Y0
G1 Z-16.0
G1 X320 Y0
G1 Z-19.0
G1 X400 Y0
G1 Z-16.0
G1 X420 Y0
G1 Z-19.0
G1 X500 Y0
G0 Z6.0
M5
M30
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".nc", delete=False) as f:
        f.write(gcode)
        temp_path = f.name

    try:
        results = check_gcode_invariants(temp_path)

        tab_result = next(r for r in results if r.id == "GCODE_TAB_PATTERN")
        assert tab_result.status == Verdict.PASS
        assert tab_result.details["detected_count"] == 4
        assert all(abs(h - 3.0) < 0.1 for h in tab_result.details["tab_heights_mm"])

        print("PASS: test_tab_pattern_detected")
    finally:
        os.unlink(temp_path)


def test_no_tabs_detected():
    """Test that G-code without tabs shows zero tab count."""
    gcode = """
(Simple profile without tabs)
G21 G90
G0 Z6.0
G0 X0 Y0
M3 S18000
G1 Z-19.0 F500
G1 X100 Y0 F1500
G1 X100 Y100
G1 X0 Y100
G1 X0 Y0
G0 Z6.0
M5
M30
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".nc", delete=False) as f:
        f.write(gcode)
        temp_path = f.name

    try:
        results = check_gcode_invariants(temp_path)

        tab_result = next(r for r in results if r.id == "GCODE_TAB_PATTERN")
        assert tab_result.status == Verdict.PASS
        assert tab_result.details["detected_count"] == 0

        print("PASS: test_no_tabs_detected")
    finally:
        os.unlink(temp_path)


def test_tabs_only_on_final_pass():
    """Test that tabs are only detected on the deepest cutting passes."""
    gcode = """
(Multi-pass profile - tabs only on final pass at Z-19)
G21 G90
G0 Z6.0
G0 X0 Y0
M3 S18000
; First pass at Z-6 (no tabs)
G1 Z-6.0 F500
G1 X100 Y0 F1500
G1 X100 Y100
G1 X0 Y100
G1 X0 Y0
G0 Z6.0
; Second pass at Z-12 (no tabs)
G0 X0 Y0
G1 Z-12.0 F500
G1 X100 Y0 F1500
G1 X100 Y100
G1 X0 Y100
G1 X0 Y0
G0 Z6.0
; Final pass at Z-19 with tabs
G0 X0 Y0
G1 Z-19.0 F500
G1 X50 Y0 F1500
G1 Z-16.0
G1 X60 Y0
G1 Z-19.0
G1 X100 Y0
G1 X100 Y50
G1 Z-16.0
G1 X100 Y60
G1 Z-19.0
G1 X100 Y100
G1 X0 Y100
G1 X0 Y0
G0 Z6.0
M5
M30
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".nc", delete=False) as f:
        f.write(gcode)
        temp_path = f.name

    try:
        results = check_gcode_invariants(temp_path)

        tab_result = next(r for r in results if r.id == "GCODE_TAB_PATTERN")
        assert tab_result.status == Verdict.PASS
        assert tab_result.details["detected_count"] == 2
        assert tab_result.details["tabs_at_max_depth"] is True

        print("PASS: test_tabs_only_on_final_pass")
    finally:
        os.unlink(temp_path)


def run_all_tests():
    """Run all G-code invariant tests."""
    tests = [
        # Valid G-code tests
        test_valid_simple_profile_gcode,
        test_valid_shaker_door_gcode,
        test_valid_multiple_depths_gcode,
        # Invalid file tests
        test_invalid_gcode_file,
        test_nonexistent_gcode_file,
        test_empty_gcode_file,
        # Safe Z tests
        test_safe_z_violation,
        test_safe_z_respected,
        # Feed rate tests
        test_negative_feed_rate,
        # Max stepdown tests
        test_max_stepdown_exceeded,
        test_max_stepdown_respected,
        # XY bounds tests
        test_xy_out_of_bounds,
        # Spindle tests
        test_spindle_not_on_before_cut,
        test_spindle_on_before_cut,
        # Tool declaration tests
        test_tool_change_without_declaration,
        test_tool_properly_declared,
        # End position tests
        test_ends_at_unsafe_z,
        test_ends_at_safe_z,
        # Continuous path tests
        test_path_discontinuity,
        test_continuous_path,
        # Tab pattern tests
        test_tab_pattern_detected,
        test_no_tabs_detected,
        test_tabs_only_on_final_pass,
        # Recipe validation tests
        test_all_recipe_gcodes_pass,
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

    print(f"\n{'=' * 60}")
    print(f"G-code Invariant Tests: {passed} passed, {failed} failed")
    print(f"{'=' * 60}")

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
