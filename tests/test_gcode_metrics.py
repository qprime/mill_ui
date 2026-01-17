# tests/test_gcode_metrics.py - Unit tests for G-code metric extraction
#
# Tests verify:
# 1. Correct metric extraction from known G-code files
# 2. Determinism (same input -> same output)
# 3. JSON serialization
# 4. Motion command parsing (G0, G1, G2, G3)
# 5. Z profile and XY bounds tracking
# 6. Time estimation with configurable rapid rate
# 7. Edge cases and error handling

from __future__ import annotations

import json
import math
import os
import sys
import tempfile

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from validation.metrics.gcode_metrics import (
    GCodeMetrics,
    GCodeConfig,
    extract_gcode_metrics,
    DEFAULT_RAPID_RATE_MM_MIN,
)
from validation.core import round_metric


# Path to recipe outputs
RECIPE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "docs",
    "recipes",
)


def get_recipe_nc_path(recipe_num: int, recipe_name: str, filename: str) -> str:
    """Get path to a recipe's G-code output."""
    return os.path.join(
        RECIPE_DIR,
        f"{recipe_num:02d}_{recipe_name}",
        "output",
        filename,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Test: Basic G-code Parsing
# ─────────────────────────────────────────────────────────────────────────────


def test_extract_gcode_metrics_simple_profile():
    """Test metric extraction from simple profile recipe."""
    nc_path = get_recipe_nc_path(1, "simple_profile", "profile-3.17mm.nc")

    if not os.path.exists(nc_path):
        print(f"SKIP: {nc_path} not found")
        return

    metrics = extract_gcode_metrics(nc_path)

    # Should have parsed lines
    assert metrics.summary.total_lines > 0, f"Total lines: {metrics.summary.total_lines}"
    assert metrics.summary.motion_lines > 0, f"Motion lines: {metrics.summary.motion_lines}"

    # Should have motion commands
    assert metrics.motion.g0_count > 0, f"G0 count: {metrics.motion.g0_count}"
    assert metrics.motion.g1_count > 0, f"G1 count: {metrics.motion.g1_count}"

    # Should have calculated distances
    assert metrics.motion.total_rapid_distance_mm > 0, f"Rapid distance: {metrics.motion.total_rapid_distance_mm}"
    assert metrics.motion.total_feed_distance_mm > 0, f"Feed distance: {metrics.motion.total_feed_distance_mm}"

    # Should have Z profile
    assert metrics.z_profile.safe_z_mm > 0, f"Safe Z: {metrics.z_profile.safe_z_mm}"
    assert metrics.z_profile.max_plunge_z_mm < 0, f"Max plunge Z: {metrics.z_profile.max_plunge_z_mm}"

    # Should have XY bounds
    assert metrics.xy_bounds.x_min < metrics.xy_bounds.x_max
    assert metrics.xy_bounds.y_min < metrics.xy_bounds.y_max

    # Should have time estimate
    assert metrics.time_estimate.total_time_s > 0, f"Time: {metrics.time_estimate.total_time_s}"

    print("PASS: test_extract_gcode_metrics_simple_profile")


def test_extract_gcode_metrics_pocket():
    """Test metric extraction from pocket G-code."""
    nc_path = get_recipe_nc_path(2, "pocket_with_cleanup", "pocket-9.53mm.nc")

    if not os.path.exists(nc_path):
        print(f"SKIP: {nc_path} not found")
        return

    metrics = extract_gcode_metrics(nc_path)

    # Pocket operations should have multiple Z depths
    assert len(metrics.z_profile.unique_cutting_depths) > 0, \
        f"Cutting depths: {metrics.z_profile.unique_cutting_depths}"

    # Should have feed rates
    assert len(metrics.feeds.feed_rates_used) > 0, f"Feed rates: {metrics.feeds.feed_rates_used}"

    # Should detect operation names from comments
    # Note: depends on comment format in generated G-code
    assert metrics.summary.comment_lines > 0, f"Comment lines: {metrics.summary.comment_lines}"

    print("PASS: test_extract_gcode_metrics_pocket")


def test_extract_gcode_metrics_bore():
    """Test metric extraction from bore/drill G-code."""
    nc_path = get_recipe_nc_path(4, "custom_template", "bore-3.17mm.nc")

    if not os.path.exists(nc_path):
        print(f"SKIP: {nc_path} not found")
        return

    metrics = extract_gcode_metrics(nc_path)

    # Bore operations use helical interpolation (linearized)
    assert metrics.motion.g1_count > 0, f"G1 count: {metrics.motion.g1_count}"

    # Should have spindle info
    assert len(metrics.tools.spindle_speeds) > 0, f"Spindle speeds: {metrics.tools.spindle_speeds}"

    print("PASS: test_extract_gcode_metrics_bore")


# ─────────────────────────────────────────────────────────────────────────────
# Test: Determinism
# ─────────────────────────────────────────────────────────────────────────────


def test_determinism():
    """Same G-code file should produce identical metrics."""
    nc_path = get_recipe_nc_path(1, "simple_profile", "profile-3.17mm.nc")

    if not os.path.exists(nc_path):
        print(f"SKIP: {nc_path} not found")
        return

    metrics1 = extract_gcode_metrics(nc_path)
    metrics2 = extract_gcode_metrics(nc_path)

    # Convert to dict, excluding extraction_time_ms
    dict1 = metrics1.to_dict()
    dict2 = metrics2.to_dict()

    # Remove timing field
    del dict1["gcode"]["extraction_time_ms"]
    del dict2["gcode"]["extraction_time_ms"]

    assert dict1 == dict2, "Metrics should be deterministic"

    print("PASS: test_determinism")


# ─────────────────────────────────────────────────────────────────────────────
# Test: JSON Serialization
# ─────────────────────────────────────────────────────────────────────────────


def test_json_serialization():
    """Metrics should serialize to valid JSON."""
    nc_path = get_recipe_nc_path(1, "simple_profile", "profile-3.17mm.nc")

    if not os.path.exists(nc_path):
        print(f"SKIP: {nc_path} not found")
        return

    metrics = extract_gcode_metrics(nc_path)
    d = metrics.to_dict()

    # Should serialize without errors
    json_str = json.dumps(d, indent=2)
    assert len(json_str) > 0

    # Should deserialize back
    parsed = json.loads(json_str)
    assert "gcode" in parsed
    assert "summary" in parsed["gcode"]
    assert "motion" in parsed["gcode"]

    print("PASS: test_json_serialization")


# ─────────────────────────────────────────────────────────────────────────────
# Test: Arc Commands (G2/G3)
# ─────────────────────────────────────────────────────────────────────────────


def test_arc_parsing_ij_format():
    """Test G2/G3 arc parsing with I/J center offset format."""
    gcode = """\
(test arc with IJ format)
G90
G21
G17
M3 S10000
G0 X0 Y0 Z5
G1 Z-1 F300
G2 X10 Y0 I5 J0 F500
G3 X0 Y0 I-5 J0 F500
G0 Z5
M5
M2
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".nc", delete=False) as f:
        f.write(gcode)
        f.flush()
        nc_path = f.name

    try:
        metrics = extract_gcode_metrics(nc_path)

        # Should detect arc commands
        assert metrics.motion.g2_count == 1, f"G2 count: {metrics.motion.g2_count}"
        assert metrics.motion.g3_count == 1, f"G3 count: {metrics.motion.g3_count}"

        # Arc distance should be approximately half circles (r=5, so each is pi*5)
        # Two half circles = full circle = 2*pi*5 ≈ 31.4mm
        expected_arc_distance = 2 * math.pi * 5
        actual_feed_distance = metrics.motion.total_feed_distance_mm

        # Feed distance includes the plunge Z move (5mm + 1mm = 6mm) plus arcs
        # Allow tolerance for rounding
        assert actual_feed_distance > expected_arc_distance, \
            f"Feed distance {actual_feed_distance} should include arcs"

        print("PASS: test_arc_parsing_ij_format")

    finally:
        os.unlink(nc_path)


def test_arc_parsing_r_format():
    """Test G2/G3 arc parsing with R radius format."""
    gcode = """\
(test arc with R format)
G90
G21
G17
M3 S10000
G0 X0 Y0 Z5
G1 Z-1 F300
G2 X10 Y0 R5 F500
G0 Z5
M5
M2
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".nc", delete=False) as f:
        f.write(gcode)
        f.flush()
        nc_path = f.name

    try:
        metrics = extract_gcode_metrics(nc_path)

        assert metrics.motion.g2_count == 1, f"G2 count: {metrics.motion.g2_count}"

        # With R format, arc should be a semicircle (180 degrees)
        # Arc length = pi * r = pi * 5 ≈ 15.7mm
        # But with chord=10 and R=5, this is actually a semicircle

        print("PASS: test_arc_parsing_r_format")

    finally:
        os.unlink(nc_path)


def test_helical_arc_distance():
    """Test that helical arcs (G2/G3 with Z) calculate 3D distance correctly."""
    gcode = """\
(test helical arc)
G90
G21
G17
M3 S10000
G0 X5 Y0 Z0
; Full circle helical interpolation: start at (5,0), center at (0,0), end at (5,0) with Z=-10
; XY arc length = 2*pi*5 = 31.416mm
; Z travel = 10mm
; 3D helix length = sqrt(31.416^2 + 10^2) = sqrt(987 + 100) = 32.97mm
G2 X5 Y0 Z-10 I-5 J0 F500
G0 Z5
M5
M2
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".nc", delete=False) as f:
        f.write(gcode)
        f.flush()
        nc_path = f.name

    try:
        metrics = extract_gcode_metrics(nc_path)

        assert metrics.motion.g2_count == 1, f"G2 count: {metrics.motion.g2_count}"

        # Expected helix length: sqrt((2*pi*5)^2 + 10^2) ≈ 32.97mm
        xy_arc = 2 * math.pi * 5
        z_delta = 10
        expected_helix = math.sqrt(xy_arc ** 2 + z_delta ** 2)

        # Feed distance should include the helix (main motion)
        # Allow 10% tolerance for floating point
        actual = metrics.motion.total_feed_distance_mm
        assert abs(actual - expected_helix) < expected_helix * 0.1, \
            f"Helix distance: expected ~{expected_helix:.2f}, got {actual:.2f}"

        print("PASS: test_helical_arc_distance")

    finally:
        os.unlink(nc_path)


def test_arc_bounds_extends_beyond_endpoints():
    """Test that arc bounds correctly include cardinal extrema beyond endpoints."""
    # This arc starts at (10, 0), goes CCW to (0, 10) with center at (0, 0)
    # This is a 90-degree arc in Q1. The arc passes through no cardinal extrema
    # beyond its endpoints, so bounds should be just x:[0,10], y:[0,10]
    gcode_quarter = """\
G90
G21
G17
G0 X10 Y0 Z5
G3 X0 Y10 I-10 J0 F500
M2
"""
    # This arc starts at (10, 0), goes CCW 270 degrees to (0, -10) with center at (0, 0)
    # It crosses: +Y at (0,10), -X at (-10,0), so bounds should be x:[-10,10], y:[-10,10]
    gcode_three_quarter = """\
G90
G21
G17
G0 X10 Y0 Z5
G3 X0 Y-10 I-10 J0 F500
M2
"""

    # Test quarter arc
    with tempfile.NamedTemporaryFile(mode="w", suffix=".nc", delete=False) as f:
        f.write(gcode_quarter)
        f.flush()
        nc_path = f.name

    try:
        metrics = extract_gcode_metrics(nc_path)
        # Quarter arc from (10,0) to (0,10): bounds should be [0,10] x [0,10]
        assert metrics.xy_bounds.x_min >= -0.01, f"x_min: {metrics.xy_bounds.x_min}"
        assert metrics.xy_bounds.x_max <= 10.01, f"x_max: {metrics.xy_bounds.x_max}"
        assert metrics.xy_bounds.y_min >= -0.01, f"y_min: {metrics.xy_bounds.y_min}"
        assert metrics.xy_bounds.y_max <= 10.01, f"y_max: {metrics.xy_bounds.y_max}"
    finally:
        os.unlink(nc_path)

    # Test 3/4 arc
    with tempfile.NamedTemporaryFile(mode="w", suffix=".nc", delete=False) as f:
        f.write(gcode_three_quarter)
        f.flush()
        nc_path = f.name

    try:
        metrics = extract_gcode_metrics(nc_path)
        # 270-degree arc crosses +Y and -X: bounds should include (-10,0) and (0,10)
        assert metrics.xy_bounds.x_min < -9.9, f"x_min should be ~-10: {metrics.xy_bounds.x_min}"
        assert metrics.xy_bounds.x_max > 9.9, f"x_max should be ~10: {metrics.xy_bounds.x_max}"
        assert metrics.xy_bounds.y_min < -9.9, f"y_min should be ~-10: {metrics.xy_bounds.y_min}"
        assert metrics.xy_bounds.y_max > 9.9, f"y_max should be ~10: {metrics.xy_bounds.y_max}"

        print("PASS: test_arc_bounds_extends_beyond_endpoints")
    finally:
        os.unlink(nc_path)


# ─────────────────────────────────────────────────────────────────────────────
# Test: Configurable Rapid Rate
# ─────────────────────────────────────────────────────────────────────────────


def test_configurable_rapid_rate():
    """Test that rapid rate can be configured for time estimation."""
    gcode = """\
(test rapid rate)
G90
G21
M3 S10000
G0 X0 Y0 Z5
G0 X100 Y0
G0 X100 Y100
G0 X0 Y100
G0 X0 Y0
M5
M2
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".nc", delete=False) as f:
        f.write(gcode)
        f.flush()
        nc_path = f.name

    try:
        # Default rapid rate
        config_default = GCodeConfig()
        metrics_default = extract_gcode_metrics(nc_path, config_default)

        # Double the rapid rate -> half the rapid time
        config_fast = GCodeConfig(rapid_rate_mm_min=DEFAULT_RAPID_RATE_MM_MIN * 2)
        metrics_fast = extract_gcode_metrics(nc_path, config_fast)

        # Rapid time should be approximately halved
        ratio = metrics_default.time_estimate.rapid_time_s / metrics_fast.time_estimate.rapid_time_s
        assert 1.9 < ratio < 2.1, f"Time ratio should be ~2, got {ratio}"

        print("PASS: test_configurable_rapid_rate")

    finally:
        os.unlink(nc_path)


# ─────────────────────────────────────────────────────────────────────────────
# Test: Z Profile Analysis
# ─────────────────────────────────────────────────────────────────────────────


def test_z_profile_analysis():
    """Test Z profile extraction including safe height and cutting depths."""
    gcode = """\
(test z profile)
G90
G21
M3 S10000
G0 Z25.0
G0 X50 Y50
G1 Z-3 F300
G1 X100 Y50 F500
G0 Z25.0
G0 X50 Y75
G1 Z-6 F300
G1 X100 Y75 F500
G0 Z25.0
G0 X50 Y100
G1 Z-9 F300
G1 X100 Y100 F500
G0 Z25.0
M5
M2
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".nc", delete=False) as f:
        f.write(gcode)
        f.flush()
        nc_path = f.name

    try:
        metrics = extract_gcode_metrics(nc_path)

        # Safe Z should be 25.0
        assert abs(metrics.z_profile.safe_z_mm - 25.0) < 0.01, \
            f"Safe Z: {metrics.z_profile.safe_z_mm}"

        # Max plunge should be -9.0
        assert abs(metrics.z_profile.max_plunge_z_mm - (-9.0)) < 0.01, \
            f"Max plunge: {metrics.z_profile.max_plunge_z_mm}"

        # Should have 3 cutting depths
        assert metrics.z_profile.depth_count == 3, \
            f"Depth count: {metrics.z_profile.depth_count}"

        # Cutting depths should be -3, -6, -9
        depths = metrics.z_profile.unique_cutting_depths
        assert len(depths) == 3, f"Depths: {depths}"
        assert -3.0 in [round(d) for d in depths]
        assert -6.0 in [round(d) for d in depths]
        assert -9.0 in [round(d) for d in depths]

        print("PASS: test_z_profile_analysis")

    finally:
        os.unlink(nc_path)


# ─────────────────────────────────────────────────────────────────────────────
# Test: XY Bounds
# ─────────────────────────────────────────────────────────────────────────────


def test_xy_bounds():
    """Test XY bounding box calculation."""
    gcode = """\
(test xy bounds)
G90
G21
M3 S10000
G0 X10 Y20 Z5
G1 Z-1 F300
G1 X100 Y20 F500
G1 X100 Y80 F500
G1 X10 Y80 F500
G1 X10 Y20 F500
G0 Z5
M5
M2
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".nc", delete=False) as f:
        f.write(gcode)
        f.flush()
        nc_path = f.name

    try:
        metrics = extract_gcode_metrics(nc_path)

        assert abs(metrics.xy_bounds.x_min - 10.0) < 0.01
        assert abs(metrics.xy_bounds.x_max - 100.0) < 0.01
        assert abs(metrics.xy_bounds.y_min - 20.0) < 0.01
        assert abs(metrics.xy_bounds.y_max - 80.0) < 0.01

        print("PASS: test_xy_bounds")

    finally:
        os.unlink(nc_path)


# ─────────────────────────────────────────────────────────────────────────────
# Test: Feed Rate Tracking
# ─────────────────────────────────────────────────────────────────────────────


def test_feed_rate_tracking():
    """Test feed rate extraction."""
    gcode = """\
(test feed rates)
G90
G21
M3 S10000
G0 X0 Y0 Z5
G1 Z-1 F200
F500
G1 X50 Y0 F500
G1 X50 Y50 F1000
G1 X0 Y50 F750
G0 Z5
M5
M2
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".nc", delete=False) as f:
        f.write(gcode)
        f.flush()
        nc_path = f.name

    try:
        metrics = extract_gcode_metrics(nc_path)

        # Should detect all feed rates
        feeds = metrics.feeds.feed_rates_used
        assert 200.0 in feeds, f"Missing F200 in {feeds}"
        assert 500.0 in feeds, f"Missing F500 in {feeds}"
        assert 750.0 in feeds, f"Missing F750 in {feeds}"
        assert 1000.0 in feeds, f"Missing F1000 in {feeds}"

        # Min/max should be correct
        assert metrics.feeds.min_feed_rate == 200.0
        assert metrics.feeds.max_feed_rate == 1000.0

        print("PASS: test_feed_rate_tracking")

    finally:
        os.unlink(nc_path)


# ─────────────────────────────────────────────────────────────────────────────
# Test: Spindle and Tool Tracking
# ─────────────────────────────────────────────────────────────────────────────


def test_spindle_tracking():
    """Test spindle speed extraction."""
    gcode = """\
(test spindle)
G90
G21
T1 M6
M3 S12000
G0 X0 Y0 Z5
G1 Z-1 F300
G0 Z5
T2 M6
M3 S18000
G0 X50 Y50 Z5
G1 Z-2 F300
G0 Z5
M5
M2
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".nc", delete=False) as f:
        f.write(gcode)
        f.flush()
        nc_path = f.name

    try:
        metrics = extract_gcode_metrics(nc_path)

        # Should detect spindle speeds
        assert 12000 in metrics.tools.spindle_speeds, \
            f"Missing S12000 in {metrics.tools.spindle_speeds}"
        assert 18000 in metrics.tools.spindle_speeds, \
            f"Missing S18000 in {metrics.tools.spindle_speeds}"

        # Should detect tool numbers
        assert 1 in metrics.tools.tool_numbers
        assert 2 in metrics.tools.tool_numbers

        # Should count tool change
        assert metrics.tools.tool_changes == 1, \
            f"Tool changes: {metrics.tools.tool_changes}"

        print("PASS: test_spindle_tracking")

    finally:
        os.unlink(nc_path)


# ─────────────────────────────────────────────────────────────────────────────
# Test: Operation Detection from Comments
# ─────────────────────────────────────────────────────────────────────────────


def test_operation_detection():
    """Test operation name extraction from comments."""
    gcode = """\
(begin)
G90
G21
(profile_outline)
M3 S14000
G0 X10 Y10 Z5
G1 Z-10 F300
G1 X100 Y10 F500
G0 Z5
(pocket_raster depth=6.0)
G0 X20 Y20 Z5
G1 Z-6 F300
G1 X80 Y20 F500
G0 Z5
(bore_helical D=10.0)
G0 X50 Y80 Z5
G1 Z-10 F300
G0 Z5
M5
M2
(end)
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".nc", delete=False) as f:
        f.write(gcode)
        f.flush()
        nc_path = f.name

    try:
        metrics = extract_gcode_metrics(nc_path)

        assert metrics.operations.profile_passes >= 1, \
            f"Profile passes: {metrics.operations.profile_passes}"
        assert metrics.operations.pocket_passes >= 1, \
            f"Pocket passes: {metrics.operations.pocket_passes}"
        assert metrics.operations.bore_passes >= 1, \
            f"Bore passes: {metrics.operations.bore_passes}"

        # Total passes should sum up
        assert metrics.operations.total_passes >= 3

        print("PASS: test_operation_detection")

    finally:
        os.unlink(nc_path)


# ─────────────────────────────────────────────────────────────────────────────
# Test: Error Handling
# ─────────────────────────────────────────────────────────────────────────────


def test_file_not_found():
    """Test FileNotFoundError for missing file."""
    try:
        extract_gcode_metrics("/nonexistent/file.nc")
        assert False, "Should have raised FileNotFoundError"
    except FileNotFoundError:
        pass  # Expected

    print("PASS: test_file_not_found")


def test_empty_file():
    """Test ValueError for empty file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".nc", delete=False) as f:
        f.flush()
        nc_path = f.name

    try:
        extract_gcode_metrics(nc_path)
        assert False, "Should have raised ValueError"
    except ValueError:
        pass  # Expected

    finally:
        os.unlink(nc_path)

    print("PASS: test_empty_file")


# ─────────────────────────────────────────────────────────────────────────────
# Test: Recipe Coverage
# ─────────────────────────────────────────────────────────────────────────────


def test_all_recipe_nc_files():
    """Test that all recipe NC files can be parsed without error."""
    import glob

    nc_files = glob.glob(os.path.join(RECIPE_DIR, "**/output/*.nc"), recursive=True)

    # Filter out macOS ._ files
    nc_files = [f for f in nc_files if not os.path.basename(f).startswith("._")]

    if not nc_files:
        print("SKIP: No recipe NC files found")
        return

    errors = []
    for nc_path in nc_files:
        try:
            metrics = extract_gcode_metrics(nc_path)
            # Basic sanity check
            assert metrics.summary.total_lines > 0
        except Exception as e:
            errors.append(f"{nc_path}: {e}")

    if errors:
        for err in errors:
            print(f"ERROR: {err}")
        assert False, f"Failed to parse {len(errors)} NC files"

    print(f"PASS: test_all_recipe_nc_files ({len(nc_files)} files)")


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────


def run_tests():
    """Run all tests."""
    tests = [
        test_extract_gcode_metrics_simple_profile,
        test_extract_gcode_metrics_pocket,
        test_extract_gcode_metrics_bore,
        test_determinism,
        test_json_serialization,
        test_arc_parsing_ij_format,
        test_arc_parsing_r_format,
        test_helical_arc_distance,
        test_arc_bounds_extends_beyond_endpoints,
        test_configurable_rapid_rate,
        test_z_profile_analysis,
        test_xy_bounds,
        test_feed_rate_tracking,
        test_spindle_tracking,
        test_operation_detection,
        test_file_not_found,
        test_empty_file,
        test_all_recipe_nc_files,
    ]

    passed = 0
    failed = 0
    skipped = 0

    for test_fn in tests:
        try:
            test_fn()
            passed += 1
        except AssertionError as e:
            print(f"FAIL: {test_fn.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"ERROR: {test_fn.__name__}: {e}")
            failed += 1

    print(f"\n{'='*60}")
    print(f"G-code Metrics Tests: {passed} passed, {failed} failed")
    print(f"{'='*60}")

    return failed == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
