"""Comprehensive tests for Stage 5 generators: Wave, Grid, and Bead.

This test module covers Stage 5 of the domain/generator system:
- WaveParams, GridParams, BeadParams validation
- wave_generator (area)
- grid_generator (area)
- bead_generator (loop)
- Determinism verification
- Integration with existing pipeline
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from domains import Domain, MultiDomain
from generators import (
    WaveParams,
    GridParams,
    BeadParams,
    wave_generator,
    grid_generator,
    bead_generator,
)
from layout_ast.layout import LayoutAST, Sheet


# =============================================================================
# Test Helpers
# =============================================================================

def approx_equal(a: float, b: float, tolerance: float = 0.01) -> bool:
    """Check if two floats are approximately equal within tolerance."""
    return abs(a - b) <= tolerance


# =============================================================================
# WaveParams Validation Tests
# =============================================================================

def test_wave_params_valid():
    """Test valid WaveParams construction."""
    params = WaveParams(amplitude_mm=10.0, wavelength_mm=30.0, depth_mm=3.0)
    params.validate()  # Should not raise

    params_full = WaveParams(
        amplitude_mm=5.0,
        wavelength_mm=20.0,
        depth_mm=2.0,
        direction_rad=math.pi / 4,
        phase_rad=math.pi / 2,
        tool_width_mm=6.0,
        wave_count=5,
    )
    params_full.validate()


def test_wave_params_invalid_amplitude():
    """Test WaveParams rejects non-positive amplitude."""
    params = WaveParams(amplitude_mm=0.0, wavelength_mm=30.0, depth_mm=3.0)
    try:
        params.validate()
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "amplitude" in str(e).lower()

    params_neg = WaveParams(amplitude_mm=-5.0, wavelength_mm=30.0, depth_mm=3.0)
    try:
        params_neg.validate()
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "amplitude" in str(e).lower()


def test_wave_params_invalid_wavelength():
    """Test WaveParams rejects non-positive wavelength."""
    params = WaveParams(amplitude_mm=10.0, wavelength_mm=0.0, depth_mm=3.0)
    try:
        params.validate()
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "wavelength" in str(e).lower()


def test_wave_params_invalid_depth():
    """Test WaveParams rejects non-positive depth."""
    params = WaveParams(amplitude_mm=10.0, wavelength_mm=30.0, depth_mm=-1.0)
    try:
        params.validate()
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "depth" in str(e).lower()


def test_wave_params_invalid_wave_count():
    """Test WaveParams rejects non-positive wave_count."""
    params = WaveParams(amplitude_mm=10.0, wavelength_mm=30.0, depth_mm=3.0, wave_count=0)
    try:
        params.validate()
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "wave_count" in str(e).lower()


# =============================================================================
# GridParams Validation Tests
# =============================================================================

def test_grid_params_valid():
    """Test valid GridParams construction."""
    params = GridParams(
        spacing_x_mm=25.0,
        spacing_y_mm=25.0,
        line_width_mm=3.0,
        depth_mm=2.0,
    )
    params.validate()  # Should not raise

    params_offset = GridParams(
        spacing_x_mm=20.0,
        spacing_y_mm=30.0,
        line_width_mm=6.0,
        depth_mm=4.0,
        offset_x_mm=5.0,
        offset_y_mm=10.0,
    )
    params_offset.validate()


def test_grid_params_invalid_spacing():
    """Test GridParams rejects non-positive spacing."""
    params = GridParams(spacing_x_mm=0.0, spacing_y_mm=25.0, line_width_mm=3.0, depth_mm=2.0)
    try:
        params.validate()
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "spacing_x" in str(e).lower()

    params_y = GridParams(spacing_x_mm=25.0, spacing_y_mm=-5.0, line_width_mm=3.0, depth_mm=2.0)
    try:
        params_y.validate()
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "spacing_y" in str(e).lower()


def test_grid_params_invalid_line_width():
    """Test GridParams rejects non-positive line_width."""
    params = GridParams(spacing_x_mm=25.0, spacing_y_mm=25.0, line_width_mm=0.0, depth_mm=2.0)
    try:
        params.validate()
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "line_width" in str(e).lower()


def test_grid_params_invalid_depth():
    """Test GridParams rejects non-positive depth."""
    params = GridParams(spacing_x_mm=25.0, spacing_y_mm=25.0, line_width_mm=3.0, depth_mm=-2.0)
    try:
        params.validate()
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "depth" in str(e).lower()


# =============================================================================
# BeadParams Validation Tests
# =============================================================================

def test_bead_params_valid():
    """Test valid BeadParams construction."""
    params = BeadParams(width_mm=6.0, depth_mm=3.0)
    params.validate()  # Should not raise

    params_offset = BeadParams(
        width_mm=8.0,
        depth_mm=4.0,
        offset_mm=15.0,
        loop_selection="all_loops",
    )
    params_offset.validate()

    params_explicit = BeadParams(
        width_mm=5.0,
        depth_mm=2.0,
        loop_selection=[0, 1],
    )
    params_explicit.validate()


def test_bead_params_invalid_width():
    """Test BeadParams rejects non-positive width."""
    params = BeadParams(width_mm=0.0, depth_mm=3.0)
    try:
        params.validate()
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "width" in str(e).lower()


def test_bead_params_invalid_depth():
    """Test BeadParams rejects non-positive depth."""
    params = BeadParams(width_mm=6.0, depth_mm=-1.0)
    try:
        params.validate()
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "depth" in str(e).lower()


def test_bead_params_invalid_loop_selection():
    """Test BeadParams rejects invalid loop_selection."""
    params = BeadParams(width_mm=6.0, depth_mm=3.0, loop_selection="invalid")
    try:
        params.validate()
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "loop_selection" in str(e).lower()


# =============================================================================
# Wave Generator Tests
# =============================================================================

def test_wave_simple_rectangle():
    """Test wave pattern on simple rectangular domain."""
    domain = Domain.from_rectangle(200, 100, center=(100, 50))
    params = WaveParams(
        amplitude_mm=10.0,
        wavelength_mm=30.0,
        depth_mm=3.0,
    )

    items = wave_generator(domain, params)

    assert len(items) > 0, "Should generate at least one wave item"

    # Verify item structure
    for item in items:
        assert item.kind == "shape"
        assert item.type == "Polyline"
        assert item.feature.type == "engrave"
        assert item.feature.depth_mm == 3.0
        assert "wave" in item.shape_id


def test_wave_with_direction():
    """Test wave pattern with non-zero direction."""
    domain = Domain.from_rectangle(200, 200, center=(100, 100))
    params = WaveParams(
        amplitude_mm=15.0,
        wavelength_mm=40.0,
        depth_mm=4.0,
        direction_rad=math.pi / 4,  # 45 degrees
    )

    items = wave_generator(domain, params)

    assert len(items) > 0, "Should generate wave items with rotated direction"


def test_wave_with_phase():
    """Test wave pattern with phase offset."""
    domain = Domain.from_rectangle(200, 100, center=(100, 50))

    params1 = WaveParams(amplitude_mm=10.0, wavelength_mm=30.0, depth_mm=3.0, phase_rad=0)
    params2 = WaveParams(amplitude_mm=10.0, wavelength_mm=30.0, depth_mm=3.0, phase_rad=math.pi)

    items1 = wave_generator(domain, params1)
    items2 = wave_generator(domain, params2)

    # Both should produce output (phase shouldn't prevent generation)
    assert len(items1) > 0
    assert len(items2) > 0


def test_wave_amplitude_too_large():
    """Test wave generator error when amplitude exceeds domain size."""
    domain = Domain.from_rectangle(20, 20, center=(10, 10))
    params = WaveParams(
        amplitude_mm=15.0,  # > half of 20mm dimension
        wavelength_mm=10.0,
        depth_mm=2.0,
    )

    try:
        wave_generator(domain, params)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "amplitude" in str(e).lower()


def test_wave_amplitude_too_large_allow_empty():
    """Test wave generator returns empty with allow_empty."""
    domain = Domain.from_rectangle(20, 20, center=(10, 10))
    params = WaveParams(amplitude_mm=15.0, wavelength_mm=10.0, depth_mm=2.0)

    items = wave_generator(domain, params, allow_empty=True)
    assert items == []


def test_wave_small_domain():
    """Test wave generator on very small domain."""
    domain = Domain.from_rectangle(0.001, 0.001)
    params = WaveParams(amplitude_mm=0.0001, wavelength_mm=0.0001, depth_mm=0.0001)

    items = wave_generator(domain, params, allow_empty=True)
    assert items == []


# =============================================================================
# Grid Generator Tests
# =============================================================================

def test_grid_simple_rectangle():
    """Test grid pattern on simple rectangular domain."""
    domain = Domain.from_rectangle(100, 100, center=(50, 50))
    params = GridParams(
        spacing_x_mm=25.0,
        spacing_y_mm=25.0,
        line_width_mm=3.0,
        depth_mm=2.0,
    )

    items = grid_generator(domain, params)

    assert len(items) > 0, "Should generate grid lines"

    # Verify item structure
    for item in items:
        assert item.kind == "shape"
        assert item.type == "Line"
        assert item.feature.type == "engrave"
        assert item.feature.depth_mm == 2.0
        assert "grid" in item.shape_id


def test_grid_with_offset():
    """Test grid pattern with offset."""
    domain = Domain.from_rectangle(100, 100, center=(50, 50))
    params = GridParams(
        spacing_x_mm=30.0,
        spacing_y_mm=30.0,
        line_width_mm=3.0,
        depth_mm=2.0,
        offset_x_mm=10.0,
        offset_y_mm=15.0,
    )

    items = grid_generator(domain, params)

    assert len(items) > 0, "Should generate grid lines with offset"


def test_grid_different_spacing():
    """Test grid pattern with different X and Y spacing."""
    domain = Domain.from_rectangle(100, 100, center=(50, 50))
    params = GridParams(
        spacing_x_mm=20.0,
        spacing_y_mm=40.0,
        line_width_mm=3.0,
        depth_mm=2.0,
    )

    items = grid_generator(domain, params)

    assert len(items) > 0, "Should generate grid with different spacing"


def test_grid_with_hole():
    """Test grid pattern on domain with inner boundary."""
    outer = [(0, 0), (100, 0), (100, 100), (0, 100)]
    inner = [(30, 30), (70, 30), (70, 70), (30, 70)]
    domain = Domain.from_polygon(outer, holes=[inner])

    params = GridParams(
        spacing_x_mm=20.0,
        spacing_y_mm=20.0,
        line_width_mm=3.0,
        depth_mm=2.0,
    )

    items = grid_generator(domain, params)

    # Grid should produce lines, some may be split by the hole
    assert len(items) > 0


def test_grid_spacing_too_large():
    """Test grid generator when spacing exceeds domain size."""
    domain = Domain.from_rectangle(20, 20, center=(10, 10))
    params = GridParams(
        spacing_x_mm=50.0,  # > domain width
        spacing_y_mm=50.0,  # > domain height
        line_width_mm=3.0,
        depth_mm=2.0,
    )

    try:
        grid_generator(domain, params)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "spacing" in str(e).lower() or "domain" in str(e).lower()


def test_grid_spacing_too_large_allow_empty():
    """Test grid generator returns empty with allow_empty."""
    domain = Domain.from_rectangle(20, 20, center=(10, 10))
    params = GridParams(
        spacing_x_mm=50.0,
        spacing_y_mm=50.0,
        line_width_mm=3.0,
        depth_mm=2.0,
    )

    items = grid_generator(domain, params, allow_empty=True)
    assert items == []


# =============================================================================
# Bead Generator Tests
# =============================================================================

def test_bead_simple_rectangle():
    """Test bead on simple rectangular domain."""
    domain = Domain.from_rectangle(100, 100, center=(50, 50))
    params = BeadParams(width_mm=6.0, depth_mm=3.0, offset_mm=10.0)

    items = bead_generator(domain, params)

    assert len(items) == 1, "Should generate one bead item for outer boundary"

    item = items[0]
    assert item.kind == "shape"
    assert item.type == "Polygon"
    assert item.feature.type == "engrave"
    assert item.feature.depth_mm == 3.0
    assert "bead" in item.shape_id
    assert "outer" in item.shape_id


def test_bead_no_offset():
    """Test bead with zero offset (on the boundary line)."""
    domain = Domain.from_rectangle(100, 100, center=(50, 50))
    params = BeadParams(width_mm=6.0, depth_mm=3.0, offset_mm=0.0)

    items = bead_generator(domain, params)

    assert len(items) == 1


def test_bead_outer_only():
    """Test bead with outer_only selection on domain with holes."""
    outer = [(0, 0), (100, 0), (100, 100), (0, 100)]
    inner = [(30, 30), (70, 30), (70, 70), (30, 70)]
    domain = Domain.from_polygon(outer, holes=[inner])

    params = BeadParams(width_mm=6.0, depth_mm=3.0, offset_mm=10.0, loop_selection="outer_only")
    items = bead_generator(domain, params)

    assert len(items) == 1
    assert "outer" in items[0].shape_id


def test_bead_inner_only():
    """Test bead with inner_only selection."""
    outer = [(0, 0), (100, 0), (100, 100), (0, 100)]
    inner = [(30, 30), (70, 30), (70, 70), (30, 70)]
    domain = Domain.from_polygon(outer, holes=[inner])

    params = BeadParams(width_mm=6.0, depth_mm=3.0, offset_mm=5.0, loop_selection="inner_only")
    items = bead_generator(domain, params)

    assert len(items) == 1
    assert "inner" in items[0].shape_id


def test_bead_all_loops():
    """Test bead with all_loops selection."""
    outer = [(0, 0), (100, 0), (100, 100), (0, 100)]
    inner = [(30, 30), (70, 30), (70, 70), (30, 70)]
    domain = Domain.from_polygon(outer, holes=[inner])

    params = BeadParams(width_mm=6.0, depth_mm=3.0, offset_mm=5.0, loop_selection="all_loops")
    items = bead_generator(domain, params)

    assert len(items) == 2
    shape_ids = [item.shape_id for item in items]
    assert any("outer" in sid for sid in shape_ids)
    assert any("inner" in sid for sid in shape_ids)


def test_bead_explicit_loop_indices():
    """Test bead with explicit loop index list."""
    outer = [(0, 0), (200, 0), (200, 100), (0, 100)]
    hole1 = [(20, 20), (80, 20), (80, 80), (20, 80)]
    hole2 = [(120, 20), (180, 20), (180, 80), (120, 80)]
    domain = Domain.from_polygon(outer, holes=[hole1, hole2])

    # Select only outer and second hole
    params = BeadParams(width_mm=6.0, depth_mm=3.0, offset_mm=5.0, loop_selection=[0, 2])
    items = bead_generator(domain, params)

    assert len(items) == 2


def test_bead_invalid_loop_index():
    """Test bead with invalid loop index raises error."""
    domain = Domain.from_rectangle(100, 100)  # No holes

    params = BeadParams(width_mm=6.0, depth_mm=3.0, loop_selection=[0, 1])

    try:
        bead_generator(domain, params)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "loop index" in str(e).lower() or "out of range" in str(e).lower()


def test_bead_invalid_index_allow_empty():
    """Test bead with invalid loop index returns empty with allow_empty."""
    domain = Domain.from_rectangle(100, 100)
    params = BeadParams(width_mm=6.0, depth_mm=3.0, loop_selection=[0, 1])

    items = bead_generator(domain, params, allow_empty=True)
    assert items == []


def test_bead_inner_only_no_holes():
    """Test inner_only on domain without holes returns empty."""
    domain = Domain.from_rectangle(100, 100)
    params = BeadParams(width_mm=6.0, depth_mm=3.0, loop_selection="inner_only")

    items = bead_generator(domain, params, allow_empty=True)
    assert items == []


def test_bead_offset_too_large():
    """Test bead when offset is too large."""
    domain = Domain.from_rectangle(50, 50, center=(25, 25))
    params = BeadParams(width_mm=6.0, depth_mm=3.0, offset_mm=30.0)  # > half of 50

    try:
        bead_generator(domain, params)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "offset" in str(e).lower() or "collapse" in str(e).lower()


def test_bead_offset_too_large_allow_empty():
    """Test bead returns empty when offset collapses domain with allow_empty."""
    domain = Domain.from_rectangle(50, 50, center=(25, 25))
    params = BeadParams(width_mm=6.0, depth_mm=3.0, offset_mm=30.0)

    items = bead_generator(domain, params, allow_empty=True)
    assert items == []


# =============================================================================
# Determinism Tests
# =============================================================================

def test_wave_generator_determinism():
    """Test that wave generator produces identical output for same input."""
    domain = Domain.from_rectangle(200, 100, center=(100, 50))
    params = WaveParams(amplitude_mm=10.0, wavelength_mm=30.0, depth_mm=3.0)

    results = [wave_generator(domain, params) for _ in range(3)]

    # All results should be identical
    for result in results[1:]:
        assert len(result) == len(results[0])
        for i, item in enumerate(result):
            ref_item = results[0][i]
            assert item.geometry.data == ref_item.geometry.data
            assert item.placement.center_xy_mm == ref_item.placement.center_xy_mm


def test_grid_generator_determinism():
    """Test that grid generator produces identical output for same input."""
    domain = Domain.from_rectangle(100, 100, center=(50, 50))
    params = GridParams(spacing_x_mm=25.0, spacing_y_mm=25.0, line_width_mm=3.0, depth_mm=2.0)

    results = [grid_generator(domain, params) for _ in range(3)]

    for result in results[1:]:
        assert len(result) == len(results[0])
        for i, item in enumerate(result):
            ref_item = results[0][i]
            assert item.geometry.data == ref_item.geometry.data


def test_bead_generator_determinism():
    """Test that bead generator produces identical output for same input."""
    domain = Domain.from_rectangle(100, 100, center=(50, 50))
    params = BeadParams(width_mm=6.0, depth_mm=3.0, offset_mm=10.0)

    results = [bead_generator(domain, params) for _ in range(3)]

    for result in results[1:]:
        assert len(result) == len(results[0])
        for i, item in enumerate(result):
            ref_item = results[0][i]
            assert item.geometry.data == ref_item.geometry.data


# =============================================================================
# Integration Tests
# =============================================================================

def test_combined_generators_on_same_domain():
    """Test using multiple generators on the same domain."""
    domain = Domain.from_rectangle(200, 150, center=(100, 75))

    # Generate different patterns
    wave_items = wave_generator(
        domain,
        WaveParams(amplitude_mm=8.0, wavelength_mm=25.0, depth_mm=2.0),
    )

    grid_items = grid_generator(
        domain,
        GridParams(spacing_x_mm=40.0, spacing_y_mm=40.0, line_width_mm=3.0, depth_mm=1.5),
    )

    bead_items = bead_generator(
        domain,
        BeadParams(width_mm=6.0, depth_mm=3.0, offset_mm=10.0),
    )

    all_items = wave_items + grid_items + bead_items

    # Should have items from all generators
    assert len(wave_items) > 0
    assert len(grid_items) > 0
    assert len(bead_items) > 0


def test_decorated_border_with_bead():
    """Test creating a decorated border using domain subtraction and bead."""
    # Create outer domain
    outer = Domain.from_rectangle(200, 150, center=(100, 75))

    # Create inner domain (panel area)
    inner_result = outer.inset(30.0)
    assert not inner_result.is_empty
    inner = inner_result.domains[0]

    # Create border domain
    border_result = outer.subtract(inner)
    assert not border_result.is_empty
    border = border_result.domains[0]

    # Apply bead to border outer edge
    bead_items = bead_generator(
        border,
        BeadParams(width_mm=5.0, depth_mm=2.0, offset_mm=5.0, loop_selection="outer_only"),
    )

    assert len(bead_items) == 1


def test_end_to_end_stage5_to_ast():
    """Test complete flow: Domain -> Stage 5 Generators -> AST."""
    # Create domain structure
    outer_domain = Domain.from_rectangle(300, 200, center=(150, 100))
    panel_result = outer_domain.inset(40)
    panel_domain = panel_result.domains[0]

    # Generate pattern on panel
    wave_items = wave_generator(
        panel_domain,
        WaveParams(amplitude_mm=5.0, wavelength_mm=20.0, depth_mm=2.0),
    )

    # Generate bead around panel
    bead_items = bead_generator(
        panel_domain,
        BeadParams(width_mm=4.0, depth_mm=2.5, offset_mm=0.0),
    )

    # Combine into AST
    all_items = wave_items + bead_items

    ast = LayoutAST(
        sheet=Sheet(width_mm=350, height_mm=250, thickness_mm=19),
        items=tuple(all_items),
    )

    assert len(ast.items) > 0


# =============================================================================
# Test Runner
# =============================================================================

def run_tests():
    """Run all tests and report results."""
    import traceback

    # Collect all test functions
    tests = [
        (name, func) for name, func in globals().items()
        if name.startswith("test_") and callable(func)
    ]

    passed = 0
    failed = 0
    errors = []

    print(f"Running {len(tests)} Stage 5 generator tests...")
    print("-" * 60)

    for name, func in sorted(tests):
        try:
            func()
            print(f"PASS: {name}")
            passed += 1
        except AssertionError as e:
            print(f"FAIL: {name}")
            print(f"      {e}")
            failed += 1
            errors.append((name, "FAIL", str(e)))
        except Exception as e:
            print(f"ERROR: {name}")
            print(f"       {type(e).__name__}: {e}")
            traceback.print_exc()
            failed += 1
            errors.append((name, "ERROR", f"{type(e).__name__}: {e}"))

    print("-" * 60)
    print(f"Results: {passed} passed, {failed} failed")

    if errors:
        print("\nFailures:")
        for name, status, msg in errors:
            print(f"  {name}: {status} - {msg}")

    return failed == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
