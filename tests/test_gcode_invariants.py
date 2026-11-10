from __future__ import annotations

import os
import sys
import tempfile

from cam.pipeline import run_pipeline
from pml import parse_pml
from validation.invariants.gcode_invariants import check_gcode_invariants_from_content

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from validation.core import Verdict
from validation.invariants.gcode_invariants import (
    GCODE_INVARIANT_IDS,
    check_gcode_invariants,
)

SHELF_PML = """Sheet:
  width: 280mm
  height: 170mm
  thickness: 19mm
  material: mdf
children:
- Rect:
    id: shelf
    feature:
      type: profile
      depth: through
      side: outside
    at:
      x: 140mm
      y: 85mm
      width: 220mm
      height: 120mm
- Rect:
    id: shelf_dado
    feature:
      type: pocket
      depth: 6mm
    at:
      x: 140mm
      y: 85mm
      width: 120mm
      height: 50mm
- Circle:
    id: shelf_pin
    diameter: 6mm
    feature:
      type: hole
      depth: 9mm
    at:
      x: 50mm
      y: 45mm
"""


def _make_pipeline_gcode() -> dict[str, str]:
    return run_pipeline(parse_pml(SHELF_PML), kerf_mm=3.175).gcode


def test_pipeline_gcode_passes_every_invariant():
    gcode_files = _make_pipeline_gcode()
    assert len(gcode_files) >= 3, sorted(gcode_files)

    for name, gcode in gcode_files.items():
        results = check_gcode_invariants_from_content(gcode)
        assert set(GCODE_INVARIANT_IDS) <= {r.id for r in results}, name
        assert [(r.id, r.failures) for r in results if r.status == Verdict.FAIL] == [], name


def test_invalid_gcode_file():
    """Test that invalid G-code file fails GCODE_PARSEABLE invariant."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".nc", delete=False) as f:
        f.write("@#$%^& not valid gcode at all!\n")
        f.write("more garbage lines\n")
        temp_path = f.name

    try:
        results = check_gcode_invariants(temp_path)

        assert results[0].id == "GCODE_PARSEABLE"
        assert results[0].status == Verdict.FAIL

        for r in results[1:]:
            assert r.details.get("skipped") is True, f"{r.id} was not skipped"
    finally:
        os.unlink(temp_path)


def test_nonexistent_gcode_file():
    """Test that nonexistent file fails GCODE_PARSEABLE."""
    results = check_gcode_invariants("/nonexistent/path/to/file.nc")

    assert results[0].id == "GCODE_PARSEABLE"
    assert results[0].status == Verdict.FAIL
    assert "not found" in str(results[0].failures).lower()


def test_empty_gcode_file():
    """Test that empty G-code file fails GCODE_PARSEABLE."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".nc", delete=False) as f:
        temp_path = f.name

    try:
        results = check_gcode_invariants(temp_path)

        assert results[0].id == "GCODE_PARSEABLE"
        assert results[0].status == Verdict.FAIL
    finally:
        os.unlink(temp_path)


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
        results = check_gcode_invariants(temp_path, safe_z_mm=5.0)

        safe_z_result = next(r for r in results if r.id == "GCODE_SAFE_Z_RESPECTED")
        assert safe_z_result.status == Verdict.FAIL
        assert "Z=1.0" in str(safe_z_result.failures) or "Z=1" in str(safe_z_result.failures)
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
    finally:
        os.unlink(temp_path)


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
    finally:
        os.unlink(temp_path)


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
        results = check_gcode_invariants(temp_path, max_stepdown_mm=10.0)

        stepdown_result = next(r for r in results if r.id == "GCODE_MAX_STEPDOWN")
        assert stepdown_result.status == Verdict.FAIL
        assert "25" in str(stepdown_result.failures)
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
    finally:
        os.unlink(temp_path)


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
        results = check_gcode_invariants(temp_path, sheet_width_mm=100.0, sheet_height_mm=100.0, margin_mm=10.0)

        bounds_result = next(r for r in results if r.id == "GCODE_XY_WITHIN_BOUNDS")
        assert bounds_result.status == Verdict.FAIL
    finally:
        os.unlink(temp_path)


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
    finally:
        os.unlink(temp_path)


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
    finally:
        os.unlink(temp_path)


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
    finally:
        os.unlink(temp_path)


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
        assert path_result.status == Verdict.FAIL
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
    finally:
        os.unlink(temp_path)


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
    finally:
        os.unlink(temp_path)
