from __future__ import annotations

import json
import math
import os
import tempfile

import pytest

from validation.metrics.gcode_metrics import (
    DEFAULT_RAPID_RATE_MM_MIN,
    GCodeConfig,
    extract_gcode_metrics,
)

RECIPE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "docs",
    "recipes",
)


def get_recipe_nc_path(recipe_num: int, recipe_name: str, filename: str) -> str:
    return os.path.join(
        RECIPE_DIR,
        f"{recipe_num:02d}_{recipe_name}",
        "output",
        filename,
    )


def test_extract_gcode_metrics_simple_profile():
    """Test metric extraction from simple profile recipe."""
    nc_path = get_recipe_nc_path(1, "simple_profile", "profile-3.17mm.nc")

    if not os.path.exists(nc_path):
        pytest.skip(f"{nc_path} not found")

    metrics = extract_gcode_metrics(nc_path)

    assert metrics.summary.total_lines > 0, f"Total lines: {metrics.summary.total_lines}"
    assert metrics.summary.motion_lines > 0, f"Motion lines: {metrics.summary.motion_lines}"
    assert metrics.motion.g0_count > 0, f"G0 count: {metrics.motion.g0_count}"
    assert metrics.motion.g1_count > 0, f"G1 count: {metrics.motion.g1_count}"
    assert metrics.motion.total_rapid_distance_mm > 0, f"Rapid distance: {metrics.motion.total_rapid_distance_mm}"
    assert metrics.motion.total_feed_distance_mm > 0, f"Feed distance: {metrics.motion.total_feed_distance_mm}"
    assert metrics.z_profile.safe_z_mm > 0, f"Safe Z: {metrics.z_profile.safe_z_mm}"
    assert metrics.z_profile.max_plunge_z_mm < 0, f"Max plunge Z: {metrics.z_profile.max_plunge_z_mm}"
    assert metrics.xy_bounds.x_min < metrics.xy_bounds.x_max
    assert metrics.xy_bounds.y_min < metrics.xy_bounds.y_max
    assert metrics.time_estimate.total_time_s > 0, f"Time: {metrics.time_estimate.total_time_s}"


def test_extract_gcode_metrics_pocket():
    """Test metric extraction from pocket G-code."""
    nc_path = get_recipe_nc_path(2, "pocket_with_cleanup", "pocket-12.70mm.nc")

    metrics = extract_gcode_metrics(nc_path)

    assert len(metrics.z_profile.unique_cutting_depths) > 0, (
        f"Cutting depths: {metrics.z_profile.unique_cutting_depths}"
    )
    assert len(metrics.feeds.feed_rates_used) > 0, f"Feed rates: {metrics.feeds.feed_rates_used}"
    assert metrics.summary.comment_lines > 0, f"Comment lines: {metrics.summary.comment_lines}"


def test_extract_gcode_metrics_bore():
    """Test metric extraction from bore/drill G-code."""
    nc_path = get_recipe_nc_path(4, "custom_template", "bore-3.17mm.nc")

    if not os.path.exists(nc_path):
        pytest.skip(f"{nc_path} not found")

    metrics = extract_gcode_metrics(nc_path)

    assert metrics.motion.g1_count > 0, f"G1 count: {metrics.motion.g1_count}"
    assert len(metrics.tools.spindle_speeds) > 0, f"Spindle speeds: {metrics.tools.spindle_speeds}"


def test_determinism():
    """Same G-code file should produce identical metrics."""
    nc_path = get_recipe_nc_path(1, "simple_profile", "profile-3.17mm.nc")

    if not os.path.exists(nc_path):
        pytest.skip(f"{nc_path} not found")

    metrics1 = extract_gcode_metrics(nc_path)
    metrics2 = extract_gcode_metrics(nc_path)

    dict1 = metrics1.to_dict()
    dict2 = metrics2.to_dict()

    del dict1["gcode"]["extraction_time_ms"]
    del dict2["gcode"]["extraction_time_ms"]

    assert dict1 == dict2, "Metrics should be deterministic"


def test_json_serialization():
    """Metrics should serialize to valid JSON."""
    nc_path = get_recipe_nc_path(1, "simple_profile", "profile-3.17mm.nc")

    if not os.path.exists(nc_path):
        pytest.skip(f"{nc_path} not found")

    metrics = extract_gcode_metrics(nc_path)
    d = metrics.to_dict()

    json_str = json.dumps(d, indent=2)
    assert len(json_str) > 0

    parsed = json.loads(json_str)
    assert "gcode" in parsed
    assert "summary" in parsed["gcode"]
    assert "motion" in parsed["gcode"]


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

        assert metrics.motion.g2_count == 1, f"G2 count: {metrics.motion.g2_count}"
        assert metrics.motion.g3_count == 1, f"G3 count: {metrics.motion.g3_count}"

        expected_arc_distance = 2 * math.pi * 5
        actual_feed_distance = metrics.motion.total_feed_distance_mm

        assert actual_feed_distance > expected_arc_distance, f"Feed distance {actual_feed_distance} should include arcs"

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

        xy_arc = 2 * math.pi * 5
        z_delta = 10
        expected_helix = math.sqrt(xy_arc**2 + z_delta**2)

        actual = metrics.motion.total_feed_distance_mm
        assert abs(actual - expected_helix) < expected_helix * 0.1, (
            f"Helix distance: expected ~{expected_helix:.2f}, got {actual:.2f}"
        )

    finally:
        os.unlink(nc_path)


def test_arc_bounds_extends_beyond_endpoints():
    """Test that arc bounds correctly include cardinal extrema beyond endpoints."""
    gcode_quarter = """\
G90
G21
G17
G0 X10 Y0 Z5
G3 X0 Y10 I-10 J0 F500
M2
"""
    gcode_three_quarter = """\
G90
G21
G17
G0 X10 Y0 Z5
G3 X0 Y-10 I-10 J0 F500
M2
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".nc", delete=False) as f:
        f.write(gcode_quarter)
        f.flush()
        nc_path = f.name

    try:
        metrics = extract_gcode_metrics(nc_path)
        assert metrics.xy_bounds.x_min >= -0.01, f"x_min: {metrics.xy_bounds.x_min}"
        assert metrics.xy_bounds.x_max <= 10.01, f"x_max: {metrics.xy_bounds.x_max}"
        assert metrics.xy_bounds.y_min >= -0.01, f"y_min: {metrics.xy_bounds.y_min}"
        assert metrics.xy_bounds.y_max <= 10.01, f"y_max: {metrics.xy_bounds.y_max}"
    finally:
        os.unlink(nc_path)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".nc", delete=False) as f:
        f.write(gcode_three_quarter)
        f.flush()
        nc_path = f.name

    try:
        metrics = extract_gcode_metrics(nc_path)
        assert metrics.xy_bounds.x_min < -9.9, f"x_min should be ~-10: {metrics.xy_bounds.x_min}"
        assert metrics.xy_bounds.x_max > 9.9, f"x_max should be ~10: {metrics.xy_bounds.x_max}"
        assert metrics.xy_bounds.y_min < -9.9, f"y_min should be ~-10: {metrics.xy_bounds.y_min}"
        assert metrics.xy_bounds.y_max > 9.9, f"y_max should be ~10: {metrics.xy_bounds.y_max}"
    finally:
        os.unlink(nc_path)


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
        config_default = GCodeConfig()
        metrics_default = extract_gcode_metrics(nc_path, config_default)

        config_fast = GCodeConfig(rapid_rate_mm_min=DEFAULT_RAPID_RATE_MM_MIN * 2)
        metrics_fast = extract_gcode_metrics(nc_path, config_fast)

        ratio = metrics_default.time_estimate.rapid_time_s / metrics_fast.time_estimate.rapid_time_s
        assert 1.9 < ratio < 2.1, f"Time ratio should be ~2, got {ratio}"

    finally:
        os.unlink(nc_path)


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

        assert abs(metrics.z_profile.safe_z_mm - 25.0) < 0.01, f"Safe Z: {metrics.z_profile.safe_z_mm}"
        assert abs(metrics.z_profile.max_plunge_z_mm - (-9.0)) < 0.01, (
            f"Max plunge: {metrics.z_profile.max_plunge_z_mm}"
        )
        assert metrics.z_profile.depth_count == 3, f"Depth count: {metrics.z_profile.depth_count}"

        depths = metrics.z_profile.unique_cutting_depths
        assert len(depths) == 3, f"Depths: {depths}"
        assert -3.0 in [round(d) for d in depths]
        assert -6.0 in [round(d) for d in depths]
        assert -9.0 in [round(d) for d in depths]

    finally:
        os.unlink(nc_path)


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

    finally:
        os.unlink(nc_path)


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

        feeds = metrics.feeds.feed_rates_used
        assert 200.0 in feeds, f"Missing F200 in {feeds}"
        assert 500.0 in feeds, f"Missing F500 in {feeds}"
        assert 750.0 in feeds, f"Missing F750 in {feeds}"
        assert 1000.0 in feeds, f"Missing F1000 in {feeds}"

        assert metrics.feeds.min_feed_rate == 200.0
        assert metrics.feeds.max_feed_rate == 1000.0

    finally:
        os.unlink(nc_path)


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

        assert 12000 in metrics.tools.spindle_speeds, f"Missing S12000 in {metrics.tools.spindle_speeds}"
        assert 18000 in metrics.tools.spindle_speeds, f"Missing S18000 in {metrics.tools.spindle_speeds}"
        assert 1 in metrics.tools.tool_numbers
        assert 2 in metrics.tools.tool_numbers
        assert metrics.tools.tool_changes == 1, f"Tool changes: {metrics.tools.tool_changes}"

    finally:
        os.unlink(nc_path)


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

        assert metrics.operations.profile_passes >= 1, f"Profile passes: {metrics.operations.profile_passes}"
        assert metrics.operations.pocket_passes >= 1, f"Pocket passes: {metrics.operations.pocket_passes}"
        assert metrics.operations.bore_passes >= 1, f"Bore passes: {metrics.operations.bore_passes}"
        assert metrics.operations.total_passes >= 3

    finally:
        os.unlink(nc_path)


def test_file_not_found():
    """Test FileNotFoundError for missing file."""
    try:
        extract_gcode_metrics("/nonexistent/file.nc")
        raise AssertionError("Should have raised FileNotFoundError")
    except FileNotFoundError:
        pass


def test_empty_file():
    """Test ValueError for empty file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".nc", delete=False) as f:
        f.flush()
        nc_path = f.name

    try:
        extract_gcode_metrics(nc_path)
        raise AssertionError("Should have raised ValueError")
    except ValueError:
        pass

    finally:
        os.unlink(nc_path)
