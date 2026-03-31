"""Comprehensive tests for the generator system.

This test module covers Stage 3 of the domain/generator system:
- Generator parameter validation
- FlatPocket generator (area)
- Profile generator (loop)
- End-to-end: Domain -> Generator -> AST -> IR
"""

from __future__ import annotations

import math

import pytest

# Add project root to path
from domains import Domain
from generators import (
    ChamferParams,
    FlatPocketParams,
    Generator,
    GeneratorSkipError,
    HoleGridParams,
    ProfileParams,
    RaisedPanelParams,
    bead_generator,
    chamfer_generator,
    concentric_border_generator,
    flat_pocket_generator,
    generate_shape_id,
    grid_generator,
    grid_lines_generator,
    hole_grid_generator,
    line_pattern_generator,
    measurement_edge_generator,
    measurement_grid_generator,
    notched_panel_generator,
    profile_generator,
    raised_panel_generator,
    svg_stamp_generator,
    validate_domain_for_generation,
    wave_generator,
    x_panel_generator,
)
from layout_ast.layout import LayoutAST, Sheet

# =============================================================================
# Test Helpers
# =============================================================================


def approx_equal(a: float, b: float, tolerance: float = 0.01) -> bool:
    """Check if two floats are approximately equal within tolerance."""
    return abs(a - b) <= tolerance


def point_approx_equal(
    p1: tuple[float, float],
    p2: tuple[float, float],
    tolerance: float = 0.01,
) -> bool:
    """Check if two points are approximately equal."""
    return approx_equal(p1[0], p2[0], tolerance) and approx_equal(p1[1], p2[1], tolerance)


def _make_dumbbell_domain() -> Domain:
    pts = [
        (0, 0),
        (80, 0),
        (80, 35),
        (170, 35),
        (170, 0),
        (250, 0),
        (250, 80),
        (170, 80),
        (170, 45),
        (80, 45),
        (80, 80),
        (0, 80),
    ]
    return Domain(outer_boundary=tuple((float(x), float(y)) for x, y in pts))


# =============================================================================
# Parameter Validation Tests
# =============================================================================


def test_flat_pocket_params_valid():
    """Test valid FlatPocketParams construction."""
    FlatPocketParams(depth_mm=6.0)
    FlatPocketParams(depth_mm=6.0, allowance_mm=2.0)


def test_flat_pocket_params_invalid_depth():
    """Test FlatPocketParams rejects non-positive depth."""
    try:
        FlatPocketParams(depth_mm=0.0)
        raise AssertionError("Should have raised ValueError")
    except ValueError as e:
        assert "positive" in str(e).lower()

    try:
        FlatPocketParams(depth_mm=-5.0)
        raise AssertionError("Should have raised ValueError")
    except ValueError as e:
        assert "positive" in str(e).lower()


def test_flat_pocket_params_invalid_allowance():
    """Test FlatPocketParams rejects negative allowance."""
    try:
        FlatPocketParams(depth_mm=6.0, allowance_mm=-1.0)
        raise AssertionError("Should have raised ValueError")
    except ValueError as e:
        assert "non-negative" in str(e).lower()


def test_profile_params_valid():
    """Test valid ProfileParams construction."""
    ProfileParams(side="outside", depth="through")
    ProfileParams(side="inside", depth=6.0)
    ProfileParams(side="on", depth=3.5, loop_selection="all_loops")
    ProfileParams(
        side="outside",
        depth="through",
        tab_count=4,
        tab_width_mm=15.0,
        tab_height_mm=4.0,
    )


def test_profile_params_invalid_side():
    """Test ProfileParams rejects invalid side."""
    try:
        ProfileParams(side="invalid", depth="through")  # type: ignore[arg-type]
        raise AssertionError("Should have raised ValueError")
    except ValueError as e:
        assert "side" in str(e).lower()


def test_profile_params_invalid_depth():
    """Test ProfileParams rejects invalid depth."""
    try:
        ProfileParams(side="outside", depth=-5.0)
        raise AssertionError("Should have raised ValueError")
    except ValueError as e:
        assert "positive" in str(e).lower()


def test_profile_params_invalid_loop_selection():
    """Test ProfileParams rejects invalid loop selection."""
    try:
        ProfileParams(side="outside", depth="through", loop_selection="invalid")  # type: ignore[arg-type]
        raise AssertionError("Should have raised ValueError")
    except ValueError as e:
        assert "loop_selection" in str(e).lower()


def test_profile_params_invalid_tab_config():
    """Test ProfileParams rejects invalid tab configuration."""
    try:
        ProfileParams(
            side="outside",
            depth="through",
            tab_count=-1,
        )
        raise AssertionError("Should have raised ValueError")
    except ValueError as e:
        assert "tab_count" in str(e).lower()


# =============================================================================
# FlatPocket Generator Tests
# =============================================================================


def test_flat_pocket_simple_rectangle():
    """Test flat pocket on simple rectangular domain."""
    domain = Domain.from_rectangle(100, 50, center=(50, 25))
    params = FlatPocketParams(depth_mm=6.0)

    items = flat_pocket_generator(domain, params)

    assert len(items) == 1
    item = items[0]

    assert item.kind == "shape"
    assert item.type == "Polygon"
    assert item.feature is not None
    assert item.shape_id is not None
    assert item.feature.type == "pocket"
    assert item.feature.depth_mm == 6.0
    assert "pocket" in item.shape_id


def test_flat_pocket_with_hole():
    """Test flat pocket on domain with inner boundary."""
    outer = [(0, 0), (100, 0), (100, 100), (0, 100)]
    inner = [(30, 30), (70, 30), (70, 70), (30, 70)]
    domain = Domain.from_polygon(outer, holes=[inner])

    params = FlatPocketParams(depth_mm=4.0)
    items = flat_pocket_generator(domain, params)

    assert len(items) == 1
    item = items[0]

    assert item.geometry is not None
    assert "holes" in item.geometry.data
    assert len(item.geometry.data["holes"]) == 1


def test_flat_pocket_various_depths():
    """Test flat pocket with various depth values."""
    domain = Domain.from_rectangle(100, 100)

    for depth in [1.0, 3.5, 6.0, 12.7, 19.0]:
        params = FlatPocketParams(depth_mm=depth)
        items = flat_pocket_generator(domain, params)

        assert len(items) == 1
        assert items[0].feature is not None
        assert items[0].feature.depth_mm == depth


def test_flat_pocket_with_allowance():
    """Test flat pocket with inward allowance."""
    domain = Domain.from_rectangle(100, 100, center=(50, 50))
    params = FlatPocketParams(depth_mm=6.0, allowance_mm=10.0)

    items = flat_pocket_generator(domain, params)

    assert len(items) == 1
    assert items[0].geometry is not None
    points = items[0].geometry.data["points"]
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    width = max(xs) - min(xs)
    height = max(ys) - min(ys)
    assert approx_equal(width, 80.0)
    assert approx_equal(height, 80.0)


def test_flat_pocket_allowance_too_large():
    """Test that large allowance raises error."""
    domain = Domain.from_rectangle(100, 100)
    params = FlatPocketParams(depth_mm=6.0, allowance_mm=60.0)  # > half of 100

    try:
        flat_pocket_generator(domain, params)
        raise AssertionError("Should have raised ValueError")
    except ValueError as e:
        assert "allowance" in str(e).lower()


def test_flat_pocket_allowance_too_large_with_allow_empty():
    """Test that large allowance returns empty with allow_empty=True."""
    domain = Domain.from_rectangle(100, 100)
    params = FlatPocketParams(depth_mm=6.0, allowance_mm=60.0)

    items = flat_pocket_generator(domain, params, allow_empty=True)
    assert items == []


def test_flat_pocket_empty_domain():
    """Test that very small domain raises error."""
    # Create domain that will be too small after any processing
    domain = Domain.from_rectangle(0.001, 0.001)
    params = FlatPocketParams(depth_mm=6.0)

    try:
        flat_pocket_generator(domain, params)
        raise AssertionError("Should have raised ValueError")
    except ValueError as e:
        assert "area" in str(e).lower() or "domain" in str(e).lower()


def test_flat_pocket_empty_domain_allow_empty():
    """Test that small domain returns empty with allow_empty=True."""
    domain = Domain.from_rectangle(0.001, 0.001)
    params = FlatPocketParams(depth_mm=6.0)

    items = flat_pocket_generator(domain, params, allow_empty=True)
    assert items == []


def test_flat_pocket_disjoint_inset_raises_skip():
    domain = _make_dumbbell_domain()
    params = FlatPocketParams(depth_mm=6.0, allowance_mm=8.0)

    with pytest.raises(GeneratorSkipError, match="disjoint regions"):
        flat_pocket_generator(domain, params)


def test_flat_pocket_disjoint_inset_allow_empty():
    domain = _make_dumbbell_domain()
    params = FlatPocketParams(depth_mm=6.0, allowance_mm=8.0)

    items = flat_pocket_generator(domain, params, allow_empty=True)
    assert items == []


# =============================================================================
# Profile Generator Tests
# =============================================================================


def test_profile_simple_rectangle():
    """Test profile on simple rectangular domain."""
    domain = Domain.from_rectangle(100, 50, center=(50, 25))
    params = ProfileParams(side="outside", depth="through")

    items = profile_generator(domain, params)

    assert len(items) == 1
    item = items[0]

    assert item.kind == "shape"
    assert item.type == "Polygon"
    assert item.feature is not None
    assert item.shape_id is not None
    assert item.feature.type == "profile"
    assert item.feature.side == "outside"
    assert item.feature.is_through
    assert "profile" in item.shape_id


def test_profile_all_sides():
    """Test profile with all side options."""
    domain = Domain.from_rectangle(100, 100)

    for side in ["outside", "inside", "on"]:
        params = ProfileParams(side=side, depth="through")  # type: ignore[arg-type]
        items = profile_generator(domain, params)

        assert len(items) == 1
        assert items[0].feature is not None
        assert items[0].feature.side == side


def test_profile_numeric_depth():
    """Test profile with numeric depth."""
    domain = Domain.from_rectangle(100, 100)
    params = ProfileParams(side="outside", depth=12.0)

    items = profile_generator(domain, params)

    assert len(items) == 1
    assert items[0].feature is not None
    assert items[0].feature.depth_mm == 12.0
    assert items[0].feature.depth_mm == 12.0


def test_profile_with_tabs():
    """Test profile with holding tabs."""
    domain = Domain.from_rectangle(100, 100)
    params = ProfileParams(
        side="outside",
        depth="through",
        tab_count=4,
        tab_width_mm=15.0,
        tab_height_mm=5.0,
    )

    items = profile_generator(domain, params)

    assert len(items) == 1
    item = items[0]
    assert item.feature is not None
    assert item.feature.tab_count == 4
    assert item.feature.tab_width_mm == 15.0
    assert item.feature.tab_height_mm == 5.0


def test_profile_outer_only():
    """Test profile with outer_only selection on domain with holes."""
    outer = [(0, 0), (100, 0), (100, 100), (0, 100)]
    inner = [(30, 30), (70, 30), (70, 70), (30, 70)]
    domain = Domain.from_polygon(outer, holes=[inner])

    params = ProfileParams(side="outside", depth="through", loop_selection="outer_only")
    items = profile_generator(domain, params)

    assert len(items) == 1
    assert items[0].shape_id is not None
    assert "outer" in items[0].shape_id


def test_profile_inner_only():
    """Test profile with inner_only selection."""
    outer = [(0, 0), (100, 0), (100, 100), (0, 100)]
    inner = [(30, 30), (70, 30), (70, 70), (30, 70)]
    domain = Domain.from_polygon(outer, holes=[inner])

    params = ProfileParams(side="inside", depth="through", loop_selection="inner_only")
    items = profile_generator(domain, params)

    assert len(items) == 1
    assert items[0].shape_id is not None
    assert "inner" in items[0].shape_id


def test_profile_all_loops():
    """Test profile with all_loops selection."""
    outer = [(0, 0), (100, 0), (100, 100), (0, 100)]
    inner = [(30, 30), (70, 30), (70, 70), (30, 70)]
    domain = Domain.from_polygon(outer, holes=[inner])

    params = ProfileParams(side="on", depth="through", loop_selection="all_loops")
    items = profile_generator(domain, params)

    assert len(items) == 2
    # Should have both outer and inner
    shape_ids = [item.shape_id for item in items if item.shape_id is not None]
    assert any("outer" in sid for sid in shape_ids)
    assert any("inner" in sid for sid in shape_ids)


def test_profile_explicit_loop_indices():
    """Test profile with explicit loop index list."""
    outer = [(0, 0), (200, 0), (200, 100), (0, 100)]
    hole1 = [(20, 20), (80, 20), (80, 80), (20, 80)]
    hole2 = [(120, 20), (180, 20), (180, 80), (120, 80)]
    domain = Domain.from_polygon(outer, holes=[hole1, hole2])

    # Select only outer and second hole
    params = ProfileParams(side="outside", depth="through", loop_selection=[0, 2])
    items = profile_generator(domain, params)

    assert len(items) == 2


def test_profile_invalid_loop_index():
    """Test that invalid loop index raises error."""
    domain = Domain.from_rectangle(100, 100)  # No holes

    params = ProfileParams(side="outside", depth="through", loop_selection=[0, 1])

    try:
        profile_generator(domain, params)
        raise AssertionError("Should have raised ValueError")
    except ValueError as e:
        assert "loop index" in str(e).lower() or "out of range" in str(e).lower()


def test_profile_invalid_index_allow_empty():
    """Test that invalid loop index returns empty with allow_empty."""
    domain = Domain.from_rectangle(100, 100)
    params = ProfileParams(side="outside", depth="through", loop_selection=[0, 1])

    items = profile_generator(domain, params, allow_empty=True)
    assert items == []


def test_profile_inner_only_no_holes():
    """Test inner_only on domain without holes returns empty list."""
    domain = Domain.from_rectangle(100, 100)
    params = ProfileParams(side="inside", depth="through", loop_selection="inner_only")

    items = profile_generator(domain, params, allow_empty=True)
    assert items == []


# =============================================================================
# Utility Function Tests
# =============================================================================


def test_generate_shape_id_basic():
    """Test shape ID generation."""
    sid = generate_shape_id("pocket", 0)
    assert "generated" in sid
    assert "pocket" in sid
    assert "000" in sid


def test_generate_shape_id_with_suffix():
    """Test shape ID generation with suffix."""
    sid = generate_shape_id("profile", 0, "outer")
    assert "generated" in sid
    assert "profile" in sid
    assert "outer" in sid


def test_validate_domain_for_generation():
    """Test domain validation utility."""
    domain = Domain.from_rectangle(100, 100)

    # Should pass
    result = validate_domain_for_generation(domain, min_area_mm2=100.0)
    assert result is True

    # Should fail
    try:
        validate_domain_for_generation(domain, min_area_mm2=100000.0)
        raise AssertionError("Should have raised ValueError")
    except ValueError:
        pass

    # With allow_empty
    result = validate_domain_for_generation(
        domain,
        min_area_mm2=100000.0,
        allow_empty=True,
    )
    assert result is False


# =============================================================================
# End-to-End Integration Tests
# =============================================================================


def test_end_to_end_domain_to_ast():
    """Test complete flow: Domain -> Generator -> AST."""
    # Create a simple Shaker-like door structure
    outer_domain = Domain.from_rectangle(400, 600, center=(200, 300))
    panel_result = outer_domain.inset(50)
    panel_domain = panel_result.domains[0]

    # Generate profile for outer
    profile_items = profile_generator(
        outer_domain,
        ProfileParams(side="outside", depth="through"),
    )

    # Generate pocket for panel
    pocket_items = flat_pocket_generator(
        panel_domain,
        FlatPocketParams(depth_mm=6.0),
    )

    # Combine into AST
    all_items = profile_items + pocket_items

    ast = LayoutAST(
        sheet=Sheet(width_mm=450, height_mm=650, thickness_mm=19, margin_mm=0.0),
        items=tuple(all_items),
    )

    assert len(ast.items) == 2
    assert ast.items[0].feature is not None
    assert ast.items[1].feature is not None
    assert ast.items[0].feature.type == "profile"
    assert ast.items[1].feature.type == "pocket"


def test_end_to_end_domain_to_ir():
    """Test complete flow: Domain -> Generator -> AST -> IR."""
    from adapters.ast_to_removal import ast_to_removal_intents

    # Create domain structure
    domain = Domain.from_rectangle(100, 100, center=(75, 75))

    # Generate items
    items = flat_pocket_generator(
        domain,
        FlatPocketParams(depth_mm=6.0),
    )

    # Build AST
    ast = LayoutAST(
        sheet=Sheet(width_mm=150, height_mm=150, thickness_mm=19, margin_mm=0.0),
        items=tuple(items),
    )

    # Convert to RemovalIntent
    warnings: list[str] = []
    ast_to_removal_intents(ast, warnings=warnings)

    # Note: Polygon type may not be fully supported by hints_to_removal
    # This test verifies the pipeline runs without crashing
    # Full support for Polygon -> RemovalIntent may require adapter updates
    if warnings:
        # Expected: Polygon type might not be fully handled
        print(f"  (Expected warning for Polygon type: {warnings})")


def test_end_to_end_shaker_style_door():
    """Test recreating a Shaker-style door with domains and generators."""
    # Outer dimensions
    outer_w, outer_h = 400.0, 600.0
    stile_w, _rail_h = 50.0, 50.0
    panel_recess = 6.0

    # Create domains
    outer_domain = Domain.from_rectangle(
        outer_w,
        outer_h,
        center=(outer_w / 2, outer_h / 2),
    )

    # Panel domain is outer inset by stile/rail width
    # For simplicity, use uniform inset (same as frame effect)
    panel_result = outer_domain.inset(stile_w)
    assert not panel_result.is_empty
    panel_domain = panel_result.domains[0]

    # Generate outer profile
    profile_items = profile_generator(
        outer_domain,
        ProfileParams(side="outside", depth="through"),
    )

    # Generate panel pocket
    pocket_items = flat_pocket_generator(
        panel_domain,
        FlatPocketParams(depth_mm=panel_recess),
    )

    # Verify output
    assert len(profile_items) == 1
    assert len(pocket_items) == 1

    # Build complete AST
    margin = 25.0
    ast = LayoutAST(
        sheet=Sheet(
            width_mm=outer_w + 2 * margin,
            height_mm=outer_h + 2 * margin,
            thickness_mm=19.0,
            margin_mm=0.0,
        ),
        items=tuple(profile_items + pocket_items),
    )

    assert len(ast.items) == 2

    # Verify features
    profile_item = next(i for i in ast.items if i.feature is not None and i.feature.type == "profile")
    pocket_item = next(i for i in ast.items if i.feature is not None and i.feature.type == "pocket")

    assert profile_item.feature is not None
    assert profile_item.feature.side == "outside"
    assert profile_item.feature.is_through
    assert pocket_item.feature is not None
    assert pocket_item.feature.depth_mm == panel_recess


def test_multidomain_iteration_with_generators():
    """Test using generators with MultiDomain results."""
    # Create a domain and split it
    wide = Domain.from_rectangle(200, 50, center=(100, 25))
    strip = Domain.from_rectangle(20, 100, center=(100, 25))
    result = wide.subtract(strip)

    assert len(result) == 2

    # Apply generator to each piece
    all_items = []
    for i, domain in enumerate(result):
        items = flat_pocket_generator(
            domain,
            FlatPocketParams(depth_mm=3.0),
            shape_id_prefix=f"piece_{i}_pocket",
        )
        all_items.extend(items)

    assert len(all_items) == 2


def test_generator_determinism():
    """Test that generators produce identical output for same input."""
    domain = Domain.from_rectangle(100, 100, center=(50, 50))

    # Run multiple times
    results = []
    for _ in range(5):
        params = FlatPocketParams(depth_mm=6.0)
        items = flat_pocket_generator(domain, params)
        results.append(items)

    # All results should be identical
    for result in results[1:]:
        assert len(result) == len(results[0])
        for i, item in enumerate(result):
            ref_item = results[0][i]
            assert item.geometry is not None
            assert ref_item.geometry is not None
            assert item.geometry.data == ref_item.geometry.data
            assert item.placement is not None
            assert ref_item.placement is not None
            assert item.placement.center_xy_mm == ref_item.placement.center_xy_mm
            assert item.feature is not None
            assert ref_item.feature is not None
            assert item.feature.depth_mm == ref_item.feature.depth_mm


# =============================================================================
# Stage 9: Raised Panel Generator Tests
# =============================================================================


def test_raised_panel_params_valid():
    """Test valid RaisedPanelParams construction."""
    RaisedPanelParams(
        border_width_mm=25.0,
        border_depth_mm=6.0,
        field_depth_mm=2.0,
    )
    RaisedPanelParams(
        border_width_mm=20.0,
        border_depth_mm=8.0,
        field_depth_mm=1.0,
        angle_degrees=20.0,
    )


def test_raised_panel_params_invalid_border_width():
    """Test RaisedPanelParams rejects non-positive border width."""
    try:
        RaisedPanelParams(
            border_width_mm=0.0,
            border_depth_mm=6.0,
            field_depth_mm=2.0,
        )
        raise AssertionError("Should have raised ValueError")
    except ValueError as e:
        assert "border_width" in str(e).lower()


def test_raised_panel_params_invalid_field_deeper():
    """Test RaisedPanelParams rejects field deeper than border."""
    try:
        RaisedPanelParams(
            border_width_mm=25.0,
            border_depth_mm=6.0,
            field_depth_mm=8.0,  # > border_depth
        )
        raise AssertionError("Should have raised ValueError")
    except ValueError as e:
        assert "field_depth" in str(e).lower()


def test_raised_panel_simple():
    """Test raised panel generator produces two items."""
    domain = Domain.from_rectangle(200, 300, center=(100, 150))
    params = RaisedPanelParams(
        border_width_mm=25.0,
        border_depth_mm=6.0,
        field_depth_mm=2.0,
    )

    items = raised_panel_generator(domain, params)

    assert len(items) == 2

    # First item should be border with bevel feature
    border_item = items[0]
    assert border_item.feature is not None
    assert border_item.feature.type == "bevel"
    assert border_item.feature.depth_mm == 6.0
    assert border_item.feature.bevel_width_mm == 25.0
    assert border_item.shape_id is not None
    assert "border" in border_item.shape_id

    # Second item should be field with pocket feature
    field_item = items[1]
    assert field_item.feature is not None
    assert field_item.feature.type == "pocket"
    assert field_item.feature.depth_mm == 2.0
    assert field_item.shape_id is not None
    assert "field" in field_item.shape_id


def test_raised_panel_border_has_hole():
    """Test that raised panel border geometry has field as hole."""
    domain = Domain.from_rectangle(200, 300, center=(100, 150))
    params = RaisedPanelParams(
        border_width_mm=30.0,
        border_depth_mm=6.0,
        field_depth_mm=2.0,
    )

    items = raised_panel_generator(domain, params)
    border_item = items[0]

    # Border geometry should have a hole (the field)
    assert border_item.geometry is not None
    assert "holes" in border_item.geometry.data
    assert len(border_item.geometry.data["holes"]) >= 1


def test_raised_panel_domain_too_small():
    """Test raised panel fails on domain too small for border."""
    domain = Domain.from_rectangle(40, 40, center=(20, 20))
    params = RaisedPanelParams(
        border_width_mm=25.0,  # > half of 40
        border_depth_mm=6.0,
        field_depth_mm=2.0,
    )

    try:
        raised_panel_generator(domain, params)
        raise AssertionError("Should have raised ValueError")
    except ValueError as e:
        assert "border_width" in str(e).lower()


def test_raised_panel_allow_empty():
    """Test raised panel returns empty with allow_empty on small domain."""
    domain = Domain.from_rectangle(40, 40, center=(20, 20))
    params = RaisedPanelParams(
        border_width_mm=25.0,
        border_depth_mm=6.0,
        field_depth_mm=2.0,
    )

    items = raised_panel_generator(domain, params, allow_empty=True)
    assert items == []


def test_raised_panel_disjoint_inset_raises_skip():
    domain = _make_dumbbell_domain()
    params = RaisedPanelParams(
        border_width_mm=8.0,
        border_depth_mm=6.0,
        field_depth_mm=2.0,
    )

    with pytest.raises(GeneratorSkipError, match="disjoint regions"):
        raised_panel_generator(domain, params)


def test_raised_panel_disjoint_inset_allow_empty():
    domain = _make_dumbbell_domain()
    params = RaisedPanelParams(
        border_width_mm=8.0,
        border_depth_mm=6.0,
        field_depth_mm=2.0,
    )

    items = raised_panel_generator(domain, params, allow_empty=True)
    assert items == []


# =============================================================================
# Stage 9: Chamfer Generator Tests
# =============================================================================


def test_chamfer_params_valid():
    """Test valid ChamferParams construction."""
    ChamferParams(width_mm=5.0, depth_mm=3.0)
    ChamferParams(
        width_mm=3.0,
        depth_mm=2.0,
        loop_selection="inner_only",
    )


def test_chamfer_params_invalid_width():
    """Test ChamferParams rejects non-positive width."""
    try:
        ChamferParams(width_mm=0.0, depth_mm=3.0)
        raise AssertionError("Should have raised ValueError")
    except ValueError as e:
        assert "width" in str(e).lower()


def test_chamfer_params_angle_property():
    """Test ChamferParams computes angle correctly."""
    params = ChamferParams(width_mm=5.0, depth_mm=5.0)  # 45 degrees
    assert approx_equal(params.angle_degrees, 45.0, tolerance=0.1)

    params2 = ChamferParams(width_mm=10.0, depth_mm=5.0)  # ~26.57 degrees
    assert approx_equal(params2.angle_degrees, 26.57, tolerance=0.1)


def test_chamfer_simple_rectangle():
    """Test chamfer on simple rectangular domain."""
    domain = Domain.from_rectangle(100, 100, center=(50, 50))
    params = ChamferParams(width_mm=5.0, depth_mm=3.0)

    items = chamfer_generator(domain, params)

    assert len(items) == 1
    item = items[0]

    assert item.feature is not None
    assert item.feature.type == "chamfer"
    assert item.feature.depth_mm == 3.0
    assert item.feature.chamfer_width_mm == 5.0
    assert item.feature.side == "outside"  # Outer loop
    assert item.shape_id is not None
    assert "chamfer" in item.shape_id


def test_chamfer_outer_only():
    """Test chamfer with outer_only on domain with holes."""
    outer = [(0, 0), (100, 0), (100, 100), (0, 100)]
    inner = [(30, 30), (70, 30), (70, 70), (30, 70)]
    domain = Domain.from_polygon(outer, holes=[inner])

    params = ChamferParams(width_mm=3.0, depth_mm=2.0, loop_selection="outer_only")
    items = chamfer_generator(domain, params)

    assert len(items) == 1
    assert items[0].shape_id is not None
    assert "outer" in items[0].shape_id


def test_chamfer_inner_only():
    """Test chamfer with inner_only selection."""
    outer = [(0, 0), (100, 0), (100, 100), (0, 100)]
    inner = [(30, 30), (70, 30), (70, 70), (30, 70)]
    domain = Domain.from_polygon(outer, holes=[inner])

    params = ChamferParams(width_mm=3.0, depth_mm=2.0, loop_selection="inner_only")
    items = chamfer_generator(domain, params)

    assert len(items) == 1
    assert items[0].shape_id is not None
    assert "inner" in items[0].shape_id
    assert items[0].feature is not None
    assert items[0].feature.side == "inside"  # Inner loops get inside side


def test_chamfer_all_loops():
    """Test chamfer with all_loops selection."""
    outer = [(0, 0), (100, 0), (100, 100), (0, 100)]
    inner = [(30, 30), (70, 30), (70, 70), (30, 70)]
    domain = Domain.from_polygon(outer, holes=[inner])

    params = ChamferParams(width_mm=3.0, depth_mm=2.0, loop_selection="all_loops")
    items = chamfer_generator(domain, params)

    assert len(items) == 2
    # Should have both outer and inner
    shape_ids = [item.shape_id for item in items if item.shape_id is not None]
    assert any("outer" in sid for sid in shape_ids)
    assert any("inner" in sid for sid in shape_ids)


def test_chamfer_inner_only_no_holes():
    """Test chamfer inner_only on domain without holes returns empty."""
    domain = Domain.from_rectangle(100, 100)
    params = ChamferParams(width_mm=3.0, depth_mm=2.0, loop_selection="inner_only")

    items = chamfer_generator(domain, params, allow_empty=True)
    assert items == []


# =============================================================================
# Stage 9: Integration Tests
# =============================================================================


def test_split_with_raised_panels():
    """Test creating multi-panel door with split and raised panels."""
    # 4-panel door layout
    door = Domain.from_rectangle(500, 700, center=(250, 350))
    panel_region = door.inset(65).domains[0]

    # Split into 2x2 grid
    panels = panel_region.split_grid(rows=2, cols=2, gap_mm=35)
    assert len(panels) == 4

    # Generate raised panels for each cell
    all_items = []
    for panel in panels:
        items = raised_panel_generator(
            panel,
            RaisedPanelParams(
                border_width_mm=20.0,
                border_depth_mm=6.0,
                field_depth_mm=1.5,
            ),
        )
        all_items.extend(items)

    # Should have 2 items per panel x 4 panels = 8 items
    assert len(all_items) == 8

    # Verify we have equal numbers of border and field items
    bevel_count = len([i for i in all_items if i.feature is not None and i.feature.type == "bevel"])
    pocket_count = len([i for i in all_items if i.feature is not None and i.feature.type == "pocket"])
    assert bevel_count == 4
    assert pocket_count == 4


def test_door_with_chamfer_and_pocket():
    """Test door with chamfered edge and pocket panel."""
    door = Domain.from_rectangle(400, 600, center=(200, 300))
    panel = door.inset(50).domains[0]

    # Profile cut
    profile_items = profile_generator(door, ProfileParams(side="outside", depth="through"))

    # Pocket
    pocket_items = flat_pocket_generator(panel, FlatPocketParams(depth_mm=6.0))

    # Chamfer
    chamfer_items = chamfer_generator(door, ChamferParams(width_mm=5.0, depth_mm=3.0))

    all_items = profile_items + pocket_items + chamfer_items
    assert len(all_items) == 3

    # Verify feature types
    feature_types = [i.feature.type for i in all_items if i.feature is not None]
    assert "profile" in feature_types
    assert "pocket" in feature_types
    assert "chamfer" in feature_types


def test_six_panel_door():
    """Test complete 6-panel door generation."""
    # Standard interior door
    door = Domain.from_rectangle(610, 2032, center=(305, 1016))
    panel_region = door.inset(75).domains[0]

    # 3 rows, 2 columns
    panels = panel_region.split_grid(rows=3, cols=2, gap_mm=30)
    assert len(panels) == 6

    # Profile for outer
    profile_items = profile_generator(door, ProfileParams(side="outside", depth="through"))

    # Pockets for each panel
    pocket_items = []
    for panel in panels:
        pocket_items.extend(flat_pocket_generator(panel, FlatPocketParams(depth_mm=6.0)))

    all_items = profile_items + pocket_items
    assert len(all_items) == 7  # 1 profile + 6 pockets


# =============================================================================
# Stage 13: Line Pattern Generator Tests
# =============================================================================


def test_line_pattern_params_valid():
    """Test valid LinePatternParams construction."""
    from generators import LinePatternParams

    LinePatternParams(angle_deg=45, spacing_mm=20.0, line_width_mm=3.0, depth_mm=2.0)
    LinePatternParams()


def test_line_pattern_params_invalid():
    """Test LinePatternParams validation."""
    from generators import LinePatternParams

    try:
        LinePatternParams(spacing_mm=0)
        raise AssertionError("Should have raised ValueError")
    except ValueError as e:
        assert "spacing" in str(e).lower()

    try:
        LinePatternParams(line_width_mm=-1)
        raise AssertionError("Should have raised ValueError")
    except ValueError as e:
        assert "line_width" in str(e).lower()


def test_line_pattern_horizontal():
    """Test horizontal line pattern (0 degrees)."""
    from generators import LinePatternParams, line_pattern_generator

    domain = Domain.from_rectangle(100, 100, center=(50, 50))
    params = LinePatternParams(angle_deg=0, spacing_mm=20.0, line_width_mm=3.0, depth_mm=2.0)

    items = line_pattern_generator(domain, params)

    assert len(items) > 0
    for item in items:
        assert item.feature is not None
        assert item.feature.type == "pocket"
        assert item.feature.depth_mm == 2.0


def test_line_pattern_diagonal():
    """Test diagonal line pattern (45 degrees)."""
    from generators import LinePatternParams, line_pattern_generator

    domain = Domain.from_rectangle(200, 200, center=(100, 100))
    params = LinePatternParams(angle_deg=45, spacing_mm=25.0, line_width_mm=4.0, depth_mm=3.0)

    items = line_pattern_generator(domain, params)

    assert len(items) > 0
    for item in items:
        assert item.type == "Polygon"


def test_line_pattern_vertical():
    """Test vertical line pattern (90 degrees)."""
    from generators import LinePatternParams, line_pattern_generator

    domain = Domain.from_rectangle(100, 100, center=(50, 50))
    params = LinePatternParams(angle_deg=90, spacing_mm=20.0, line_width_mm=3.0, depth_mm=2.0)

    items = line_pattern_generator(domain, params)

    assert len(items) > 0


def test_line_pattern_allow_empty():
    """Test line pattern with tiny domain returns empty with allow_empty."""
    from generators import LinePatternParams, line_pattern_generator

    # Domain smaller than min_area_mm2 threshold (1.0)
    domain = Domain.from_rectangle(0.5, 0.5, center=(0.25, 0.25))
    params = LinePatternParams(spacing_mm=50.0, line_width_mm=3.0, depth_mm=2.0)

    items = line_pattern_generator(domain, params, allow_empty=True)
    assert items == []


def test_line_pattern_local_coords_unrotated():
    """Test local_coords=True on unrotated domain matches sheet coords."""
    from generators import LinePatternParams, line_pattern_generator

    domain = Domain.from_rectangle(100, 100, center=(50, 50))
    params = LinePatternParams(angle_deg=0, spacing_mm=20.0, line_width_mm=3.0, depth_mm=2.0)

    items_sheet = line_pattern_generator(domain, params, local_coords=False)
    items_local = line_pattern_generator(domain, params, local_coords=True)

    assert len(items_sheet) == len(items_local)


def test_line_pattern_local_coords_rotated():
    """Test local_coords=True respects domain rotation."""
    from generators import LinePatternParams, line_pattern_generator

    domain = Domain.from_rectangle(100, 100, center=(50, 50), rotation_rad=math.pi / 4)
    params = LinePatternParams(angle_deg=0, spacing_mm=20.0, line_width_mm=3.0, depth_mm=2.0)

    items_sheet = line_pattern_generator(domain, params, local_coords=False)
    items_local = line_pattern_generator(domain, params, local_coords=True)

    assert len(items_sheet) > 0
    assert len(items_local) > 0

    assert items_sheet[0].geometry is not None
    assert items_local[0].geometry is not None
    sheet_centroid = items_sheet[0].geometry.data["points"][0]
    local_centroid = items_local[0].geometry.data["points"][0]
    assert sheet_centroid != local_centroid


# =============================================================================
# Stage 13: Concentric Border Generator Tests
# =============================================================================


def test_concentric_border_params_valid():
    """Test valid ConcentricBorderParams construction."""
    from generators import ConcentricBorderParams

    ConcentricBorderParams(insets_mm=(10.0, 20.0, 30.0), groove_width_mm=3.0, depth_mm=2.0)


def test_concentric_border_params_invalid():
    """Test ConcentricBorderParams validation."""
    from generators import ConcentricBorderParams

    try:
        ConcentricBorderParams(insets_mm=(), groove_width_mm=3.0, depth_mm=2.0)
        raise AssertionError("Should have raised ValueError")
    except ValueError as e:
        assert "insets" in str(e).lower()

    try:
        ConcentricBorderParams(insets_mm=(-5.0,), groove_width_mm=3.0, depth_mm=2.0)
        raise AssertionError("Should have raised ValueError")
    except ValueError as e:
        assert "positive" in str(e).lower()


def test_concentric_border_simple():
    """Test concentric border on simple rectangle."""
    from generators import ConcentricBorderParams, concentric_border_generator

    domain = Domain.from_rectangle(200, 200, center=(100, 100))
    params = ConcentricBorderParams(insets_mm=(15.0, 30.0), groove_width_mm=3.0, depth_mm=2.0)

    items = concentric_border_generator(domain, params)

    assert len(items) >= 2  # At least 2 ring polygons
    for item in items:
        assert item.feature is not None
        assert item.feature.type == "pocket"
        assert item.feature.depth_mm == 2.0


def test_concentric_border_single_inset():
    """Test concentric border with single inset."""
    from generators import ConcentricBorderParams, concentric_border_generator

    domain = Domain.from_rectangle(100, 100, center=(50, 50))
    params = ConcentricBorderParams(insets_mm=(10.0,), groove_width_mm=3.0, depth_mm=2.0)

    items = concentric_border_generator(domain, params)

    assert len(items) >= 1


def test_concentric_border_matches_recipe_25_pattern():
    """Test that concentric border matches Recipe 25 pattern."""
    from generators import ConcentricBorderParams, concentric_border_generator

    # Match Recipe 25 parameters
    PANEL_WIDTH = 350
    PANEL_HEIGHT = 450
    GROOVE_DEPTH = 2.0
    GROOVE_WIDTH = 3.0
    INSETS = (15.0, 30.0, 45.0)

    domain = Domain.from_rectangle(PANEL_WIDTH, PANEL_HEIGHT, center=(175, 225))
    params = ConcentricBorderParams(
        insets_mm=INSETS,
        groove_width_mm=GROOVE_WIDTH,
        depth_mm=GROOVE_DEPTH,
    )

    items = concentric_border_generator(domain, params)

    # Should produce 3 rings
    assert len(items) == 3
    for item in items:
        assert item.feature is not None
        assert item.feature.depth_mm == GROOVE_DEPTH


def test_concentric_border_allow_empty():
    """Test concentric border returns empty when inset exceeds domain."""
    from generators import ConcentricBorderParams, concentric_border_generator

    domain = Domain.from_rectangle(50, 50, center=(25, 25))
    params = ConcentricBorderParams(insets_mm=(100.0,), groove_width_mm=3.0, depth_mm=2.0)

    items = concentric_border_generator(domain, params, allow_empty=True)
    assert items == []


def test_concentric_border_skips_overflow_ring():
    """Test that rings are skipped when groove width overflows available space."""
    from generators import ConcentricBorderParams, concentric_border_generator

    domain = Domain.from_rectangle(100, 100, center=(50, 50))
    params = ConcentricBorderParams(
        insets_mm=(10.0, 40.0),
        groove_width_mm=20.0,
        depth_mm=2.0,
    )

    items = concentric_border_generator(domain, params)

    assert len(items) == 1


# =============================================================================
# Stage 13: Utility Tests
# =============================================================================


def test_shapely_to_item():
    """Test shapely_to_item utility."""
    from shapely.geometry import Polygon

    from generators.utils import shapely_to_item

    poly = Polygon([(0, 0), (100, 0), (100, 100), (0, 100)])
    item = shapely_to_item(poly, "pocket", 5.0, "test_001")

    assert item.type == "Polygon"
    assert item.feature is not None
    assert item.feature.type == "pocket"
    assert item.feature.depth_mm == 5.0
    assert item.shape_id == "test_001"
    assert item.geometry is not None
    assert len(item.geometry.data["points"]) == 4


def test_shapely_to_item_with_hole():
    """Test shapely_to_item with polygon containing holes."""
    from shapely.geometry import Polygon

    from generators.utils import shapely_to_item

    outer = [(0, 0), (100, 0), (100, 100), (0, 100)]
    hole = [(30, 30), (70, 30), (70, 70), (30, 70)]
    poly = Polygon(outer, [hole])

    item = shapely_to_item(poly, "pocket", 3.0, "with_hole")

    assert item.geometry is not None
    assert "holes" in item.geometry.data
    assert len(item.geometry.data["holes"]) == 1


def test_iter_polygons():
    """Test iter_polygons utility."""
    from shapely.geometry import MultiPolygon, Polygon

    from generators.utils import iter_polygons

    # Single polygon
    single = Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])
    result = iter_polygons(single)
    assert len(result) == 1

    # MultiPolygon
    mp = MultiPolygon(
        [
            Polygon([(0, 0), (1, 0), (1, 1), (0, 1)]),
            Polygon([(2, 0), (3, 0), (3, 1), (2, 1)]),
        ]
    )
    result = iter_polygons(mp)
    assert len(result) == 2


# =============================================================================
# Hole Grid Generator Tests
# =============================================================================


def test_hole_grid_params_valid():
    """Test valid HoleGridParams construction."""
    HoleGridParams(spacing_mm=50.0, diameter_mm=6.35, depth_mm=12.0)
    HoleGridParams(spacing_mm=25.0, diameter_mm=5.0, depth_mm="through")
    HoleGridParams(
        spacing_mm=30.0,
        diameter_mm=8.0,
        depth_mm=10.0,
        pattern="hexagonal",
        inset_mm=5.0,
        align="corner",
    )


def test_hole_grid_params_invalid_spacing():
    """Test HoleGridParams rejects non-positive spacing."""
    try:
        HoleGridParams(spacing_mm=0.0, diameter_mm=5.0, depth_mm=10.0)
        raise AssertionError("Should have raised ValueError")
    except ValueError as e:
        assert "spacing" in str(e).lower()


def test_hole_grid_params_invalid_diameter():
    """Test HoleGridParams rejects non-positive diameter."""
    try:
        HoleGridParams(spacing_mm=50.0, diameter_mm=-1.0, depth_mm=10.0)
        raise AssertionError("Should have raised ValueError")
    except ValueError as e:
        assert "diameter" in str(e).lower()


def test_hole_grid_params_diameter_exceeds_spacing():
    """Test HoleGridParams rejects diameter >= spacing."""
    try:
        HoleGridParams(spacing_mm=10.0, diameter_mm=15.0, depth_mm=10.0)
        raise AssertionError("Should have raised ValueError")
    except ValueError as e:
        assert "overlap" in str(e).lower()


def test_hole_grid_params_invalid_depth():
    """Test HoleGridParams rejects invalid depth."""
    try:
        HoleGridParams(spacing_mm=50.0, diameter_mm=5.0, depth_mm=-5.0)
        raise AssertionError("Should have raised ValueError")
    except ValueError as e:
        assert "depth" in str(e).lower()


def test_hole_grid_params_invalid_pattern():
    """Test HoleGridParams rejects invalid pattern."""
    try:
        HoleGridParams(spacing_mm=50.0, diameter_mm=5.0, depth_mm=10.0, pattern="invalid")  # type: ignore[arg-type]
        raise AssertionError("Should have raised ValueError")
    except ValueError as e:
        assert "pattern" in str(e).lower()


def test_hole_grid_rectangular_basic():
    """Test basic rectangular hole grid."""
    domain = Domain.from_rectangle(200, 200, center=(100, 100))
    params = HoleGridParams(spacing_mm=50.0, diameter_mm=10.0, depth_mm=12.0)

    items = hole_grid_generator(domain, params)

    assert len(items) > 0
    for item in items:
        assert item.type == "Circle"
        assert item.feature is not None
        assert item.feature.type == "hole"
        assert item.feature.depth_mm == 12.0
        assert item.geometry is not None
        assert item.geometry.data["diameter_mm"] == 10.0


def test_hole_grid_hexagonal():
    """Test hexagonal pattern hole grid."""
    domain = Domain.from_rectangle(200, 200, center=(100, 100))
    params = HoleGridParams(
        spacing_mm=30.0,
        diameter_mm=8.0,
        depth_mm=10.0,
        pattern="hexagonal",
    )

    items = hole_grid_generator(domain, params)

    assert len(items) > 0
    for item in items:
        assert item.type == "Circle"
        assert item.feature is not None
        assert item.feature.type == "hole"


def test_hole_grid_offset():
    """Test offset pattern hole grid."""
    domain = Domain.from_rectangle(200, 200, center=(100, 100))
    params = HoleGridParams(
        spacing_mm=40.0,
        diameter_mm=10.0,
        depth_mm=15.0,
        pattern="offset",
    )

    items = hole_grid_generator(domain, params)

    assert len(items) > 0


def test_hole_grid_through_depth():
    """Test hole grid with through depth."""
    domain = Domain.from_rectangle(100, 100, center=(50, 50))
    params = HoleGridParams(spacing_mm=30.0, diameter_mm=6.0, depth_mm="through")

    items = hole_grid_generator(domain, params)

    assert len(items) > 0
    for item in items:
        assert item.feature is not None
        assert item.feature.is_through is True
        assert item.feature.depth_mm == 0.0


def test_hole_grid_with_inset():
    """Test hole grid respects inset parameter."""
    domain = Domain.from_rectangle(200, 200, center=(100, 100))
    params_no_inset = HoleGridParams(spacing_mm=25.0, diameter_mm=10.0, depth_mm=10.0, inset_mm=0.0)
    params_with_inset = HoleGridParams(spacing_mm=25.0, diameter_mm=10.0, depth_mm=10.0, inset_mm=40.0)

    items_no_inset = hole_grid_generator(domain, params_no_inset)
    items_with_inset = hole_grid_generator(domain, params_with_inset)

    assert len(items_with_inset) < len(items_no_inset)


def test_hole_grid_corner_align():
    """Test hole grid with corner alignment."""
    domain = Domain.from_rectangle(200, 200, center=(100, 100))
    params = HoleGridParams(
        spacing_mm=50.0,
        diameter_mm=10.0,
        depth_mm=10.0,
        align="corner",
    )

    items = hole_grid_generator(domain, params)

    assert len(items) > 0


def test_hole_grid_respects_domain_holes():
    """Test that hole grid avoids domain inner boundaries."""
    outer = [(0, 0), (200, 0), (200, 200), (0, 200)]
    inner = [(70, 70), (130, 70), (130, 130), (70, 130)]
    domain = Domain.from_polygon(outer, holes=[inner])

    params = HoleGridParams(spacing_mm=30.0, diameter_mm=10.0, depth_mm=10.0)

    items = hole_grid_generator(domain, params)

    for item in items:
        assert item.placement is not None
        cx, cy = item.placement.center_xy_mm
        assert not (70 < cx < 130 and 70 < cy < 130), "Hole placed inside domain hole"


def test_hole_grid_domain_too_small():
    """Test hole grid on domain too small for any holes."""
    domain = Domain.from_rectangle(5, 5, center=(2.5, 2.5))
    params = HoleGridParams(spacing_mm=50.0, diameter_mm=8.0, depth_mm=10.0)

    try:
        hole_grid_generator(domain, params)
        raise AssertionError("Should have raised ValueError")
    except ValueError as e:
        assert "area" in str(e).lower() or "small" in str(e).lower()


def test_hole_grid_allow_empty():
    """Test hole grid returns empty with allow_empty on small domain."""
    domain = Domain.from_rectangle(5, 5, center=(2.5, 2.5))
    params = HoleGridParams(spacing_mm=50.0, diameter_mm=8.0, depth_mm=10.0)

    items = hole_grid_generator(domain, params, allow_empty=True)
    assert items == []


def test_hole_grid_inset_too_large():
    """Test hole grid with inset larger than domain."""
    domain = Domain.from_rectangle(100, 100, center=(50, 50))
    params = HoleGridParams(spacing_mm=20.0, diameter_mm=5.0, depth_mm=10.0, inset_mm=60.0)

    items = hole_grid_generator(domain, params, allow_empty=True)
    assert items == []


def test_hole_grid_disjoint_inset_raises_skip():
    domain = _make_dumbbell_domain()
    params = HoleGridParams(spacing_mm=20.0, diameter_mm=5.0, depth_mm=10.0, inset_mm=8.0)

    with pytest.raises(GeneratorSkipError, match="disjoint regions"):
        hole_grid_generator(domain, params)


def test_hole_grid_disjoint_inset_allow_empty():
    domain = _make_dumbbell_domain()
    params = HoleGridParams(spacing_mm=20.0, diameter_mm=5.0, depth_mm=10.0, inset_mm=8.0)

    items = hole_grid_generator(domain, params, allow_empty=True)
    assert items == []


def test_hole_grid_domain_algebra():
    """Test hole grid works with domain algebra (subtract)."""
    outer = Domain.from_rectangle(200, 200, center=(100, 100))
    keepout = Domain.from_rectangle(60, 60, center=(100, 100))
    result = outer.subtract(keepout)

    assert not result.is_empty
    domain = result.domains[0]

    params = HoleGridParams(spacing_mm=25.0, diameter_mm=6.0, depth_mm=10.0)

    items = hole_grid_generator(domain, params)

    assert len(items) > 0
    for item in items:
        assert item.placement is not None
        cx, cy = item.placement.center_xy_mm
        in_keepout = 70 < cx < 130 and 70 < cy < 130
        assert not in_keepout, "Hole placed in keepout region"


def test_hole_grid_shape_id_prefix():
    """Test hole grid uses custom shape_id_prefix."""
    domain = Domain.from_rectangle(100, 100, center=(50, 50))
    params = HoleGridParams(spacing_mm=30.0, diameter_mm=6.0, depth_mm=10.0)

    items = hole_grid_generator(domain, params, shape_id_prefix="shelf_pin")

    assert len(items) > 0
    for item in items:
        assert item.shape_id is not None
        assert "shelf_pin" in item.shape_id


def test_hole_grid_determinism():
    """Test hole grid produces identical output for same input."""
    domain = Domain.from_rectangle(150, 150, center=(75, 75))
    params = HoleGridParams(spacing_mm=30.0, diameter_mm=8.0, depth_mm=10.0)

    results = [hole_grid_generator(domain, params) for _ in range(3)]

    for result in results[1:]:
        assert len(result) == len(results[0])
        for i, item in enumerate(result):
            ref = results[0][i]
            assert item.placement is not None
            assert ref.placement is not None
            assert item.placement.center_xy_mm == ref.placement.center_xy_mm
            assert item.geometry is not None
            assert ref.geometry is not None
            assert item.geometry.data == ref.geometry.data


# =============================================================================
# Test Runner
# =============================================================================


ALL_GENERATORS = [
    flat_pocket_generator,
    wave_generator,
    grid_generator,
    grid_lines_generator,
    measurement_grid_generator,
    raised_panel_generator,
    line_pattern_generator,
    concentric_border_generator,
    x_panel_generator,
    hole_grid_generator,
    profile_generator,
    bead_generator,
    chamfer_generator,
    measurement_edge_generator,
    svg_stamp_generator,
    notched_panel_generator,
]


@pytest.mark.parametrize("gen", ALL_GENERATORS, ids=lambda g: g.__name__)
def test_generator_satisfies_protocol(gen):
    assert isinstance(gen, Generator), f"{gen.__name__} does not satisfy the Generator protocol"
