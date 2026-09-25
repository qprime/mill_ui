"""Comprehensive tests for the generator system.

This test module covers Stage 3 of the domain/generator system:
- Generator parameter validation
- FlatPocket generator (area)
- Profile generator (loop)
- End-to-end: Domain -> Generator -> AST -> IR
"""

from __future__ import annotations

import itertools
import math
from dataclasses import replace
from typing import Any

import numpy as np
import pytest
from shapely.geometry import LineString, MultiPoint, MultiPolygon, Polygon
from shapely.ops import voronoi_diagram

# Add project root to path
from core.constants import GOLDEN_ANGLE_DEG
from domains import Domain
from domains.transforms import local_to_sheet
from generators import (
    ChamferParams,
    ConcentricBorderParams,
    FlatPocketParams,
    Generator,
    GeneratorSkipError,
    HoleGridParams,
    PhyllotaxisHoleParams,
    PhyllotaxisPocketParams,
    PhyllotaxisSvgParams,
    ProfileParams,
    RaisedPanelParams,
    StringArtParams,
    VoronoiParams,
    bead_generator,
    chamfer_generator,
    concentric_border_generator,
    flat_pocket_generator,
    generate_shape_id,
    grid_generator,
    grid_lines_generator,
    hole_grid_generator,
    line_pattern_generator,
    lissajous_curve_generator,
    measurement_edge_generator,
    measurement_grid_generator,
    notched_panel_generator,
    phyllotaxis_hole_generator,
    phyllotaxis_pocket_generator,
    phyllotaxis_svg_generator,
    profile_generator,
    raised_panel_generator,
    rose_curve_generator,
    spirograph_curve_generator,
    string_art_generator,
    svg_stamp_generator,
    validate_domain_for_generation,
    voronoi_generator,
    wave_generator,
    x_panel_generator,
)
from generators.area.voronoi import _sample_seeds
from generators.placement import item_inside_domain, place_item
from generators.radial_utils import closest_pair_distance, spiral_positions
from generators.utils import rotate_points
from layout_ast.layout import Feature, Geometry, Item, LayoutAST, Placement, RestSpec, Sheet

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
    GROOVE_WIDTH = 4.0
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


def _holed_square_domain() -> Domain:
    return Domain(
        outer_boundary=((0, 0), (200, 0), (200, 200), (0, 200)),
        inner_boundaries=(((80, 80), (120, 80), (120, 120), (80, 120)),),
    )


def _ring_data(item: Item) -> dict[str, Any]:
    assert item.geometry is not None
    return item.geometry.data


def _x_extent(item: Item) -> float:
    xs = [float(p[0]) for p in _ring_data(item)["points"]]
    return max(xs) - min(xs)


def test_concentric_params_engrave_rejects_groove():
    with pytest.raises(ValueError, match="groove_width_mm=None"):
        ConcentricBorderParams(insets_mm=(10.0,), groove_width_mm=3.0, mode="engrave")


def test_concentric_params_pocket_requires_groove():
    with pytest.raises(ValueError, match="groove_width_mm must be positive in pocket mode"):
        ConcentricBorderParams(insets_mm=(10.0,), groove_width_mm=None)


def test_concentric_params_rejects_bad_join():
    with pytest.raises(ValueError, match="join_style"):
        ConcentricBorderParams(insets_mm=(10.0,), join_style="square")  # type: ignore[arg-type]


def test_concentric_params_rejects_duplicate_insets():
    with pytest.raises(ValueError, match="duplicate"):
        ConcentricBorderParams(insets_mm=(15.0, 15.0), groove_width_mm=None, mode="engrave")


@pytest.mark.parametrize("insets", [(15.0, 16.0), (16.0, 15.0)])
def test_concentric_params_rejects_overlapping_pocket_rings(insets):
    with pytest.raises(ValueError, match=r"15\.0 and 16\.0 are closer than groove_width_mm 3\.0"):
        ConcentricBorderParams(insets_mm=insets, groove_width_mm=3.0)


def test_concentric_params_allows_touching_and_engrave_close_rings():
    ConcentricBorderParams(insets_mm=(15.0, 18.0), groove_width_mm=3.0)
    ConcentricBorderParams(insets_mm=(15.0, 16.0), groove_width_mm=None, mode="engrave")


def test_concentric_engrave_emits_closed_polylines():
    domain = Domain.from_rectangle(200, 200, center=(100, 100))
    params = ConcentricBorderParams(insets_mm=(10.0, 20.0, 30.0), groove_width_mm=None, mode="engrave")

    items = concentric_border_generator(domain, params)

    assert len(items) == 3
    assert all(item.type == "Polyline" for item in items)
    assert all(item.feature is not None and item.feature.type == "engrave" for item in items)
    assert all(_ring_data(item)["is_open"] is False for item in items)
    assert [_x_extent(item) for item in items] == pytest.approx([180.0, 160.0, 140.0])


def test_concentric_engrave_holed_domain_emits_outer_and_hole():
    params = ConcentricBorderParams(insets_mm=(10.0,), groove_width_mm=None, mode="engrave")

    items = concentric_border_generator(_holed_square_domain(), params)

    extents = sorted(_x_extent(item) for item in items)
    assert extents == pytest.approx([60.0, 180.0])


@pytest.mark.parametrize(("join_style", "expect_rounded"), [("round", True), ("mitre", False)])
def test_concentric_round_join_rounds_hole_corners(join_style, expect_rounded):
    params = ConcentricBorderParams(insets_mm=(10.0,), groove_width_mm=3.0, join_style=join_style)

    items = concentric_border_generator(_holed_square_domain(), params)

    assert len(items) == 2
    (hole_ring,) = [item for item in items if _x_extent(item) == pytest.approx(66.0)]
    exterior = _ring_data(hole_ring)["points"]
    (interior,) = _ring_data(hole_ring)["holes"]
    if expect_rounded:
        assert len(exterior) > 4
        assert len(interior) > 4
    else:
        assert len(exterior) == 4
        assert len(interior) == 4


def test_concentric_engrave_skips_regions_under_one_square_mm():
    ring = Domain(
        outer_boundary=((0, 0), (200, 0), (200, 200), (0, 200)),
        inner_boundaries=(((60, 60), (140, 60), (140, 140), (60, 140)),),
    )
    params = ConcentricBorderParams(insets_mm=(32.0, 34.9), groove_width_mm=None, mode="engrave", join_style="round")

    items = concentric_border_generator(ring, params)

    assert len(items) == 4
    assert all(_x_extent(item) == pytest.approx(12.55, abs=0.01) for item in items)


def test_concentric_pocket_default_geometry():
    domain = Domain.from_rectangle(200, 200, center=(100, 100))
    params = ConcentricBorderParams(insets_mm=(15.0, 30.0, 45.0), groove_width_mm=3.0, depth_mm=2.0)

    items = concentric_border_generator(domain, params)

    assert len(items) == 3
    ring = items[0]
    assert ring.placement is not None
    cx, cy = ring.placement.center_xy_mm
    exterior = [(cx + x, cy + y) for x, y in _ring_data(ring)["points"]]
    (hole,) = _ring_data(ring)["holes"]
    interior = [(cx + x, cy + y) for x, y in hole]
    for axis in (0, 1):
        assert min(p[axis] for p in exterior) == pytest.approx(15.0)
        assert max(p[axis] for p in exterior) == pytest.approx(185.0)
        assert min(p[axis] for p in interior) == pytest.approx(18.0)
        assert max(p[axis] for p in interior) == pytest.approx(182.0)


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
# Polyline Clipping
# =============================================================================


class TestClipPolylinesToDomain:
    def _square(self) -> Domain:
        return Domain.from_rectangle(100, 100, center=(50, 50))

    def test_fully_inside_returned_unchanged(self):
        from generators.utils import clip_polylines_to_domain

        path = [(10.0, 10.0), (50.0, 60.0), (90.0, 20.0)]
        pieces = clip_polylines_to_domain([path], self._square())
        assert pieces == [path]

    def test_fully_outside_returns_empty(self):
        from generators.utils import clip_polylines_to_domain

        pieces = clip_polylines_to_domain([[(-50.0, -50.0), (-10.0, -10.0)]], self._square())
        assert pieces == []

    def test_crossing_once_ends_on_boundary(self):
        from generators.utils import clip_polylines_to_domain

        pieces = clip_polylines_to_domain([[(-10.0, 50.0), (50.0, 50.0)]], self._square())
        assert len(pieces) == 1
        assert pieces[0][0] == pytest.approx((0.0, 50.0), abs=1e-9)
        assert pieces[0][-1] == pytest.approx((50.0, 50.0), abs=1e-9)

    def test_in_out_in_returns_two_pieces(self):
        from generators.utils import clip_polylines_to_domain

        path = [(20.0, 50.0), (120.0, 50.0), (120.0, 80.0), (20.0, 80.0)]
        pieces = clip_polylines_to_domain([path], self._square())
        assert len(pieces) == 2
        for piece in pieces:
            assert any(abs(x - 100.0) < 1e-9 for x, _ in (piece[0], piece[-1]))

    def test_touch_at_vertex_returns_empty(self):
        from generators.utils import clip_polylines_to_domain

        pieces = clip_polylines_to_domain([[(-10.0, 10.0), (0.0, 0.0), (10.0, -10.0)]], self._square())
        assert pieces == []

    def test_along_edge_is_kept(self):
        from generators.utils import clip_polylines_to_domain

        pieces = clip_polylines_to_domain([[(-10.0, 100.0), (110.0, 100.0)]], self._square())
        assert len(pieces) == 1
        assert pieces[0][0] == pytest.approx((0.0, 100.0), abs=1e-9)
        assert pieces[0][-1] == pytest.approx((100.0, 100.0), abs=1e-9)

    def test_crossing_hole_returns_two_pieces(self):
        from generators.utils import clip_polylines_to_domain

        domain = Domain.from_polygon(
            [(0, 0), (100, 0), (100, 100), (0, 100)],
            holes=[[(40, 40), (60, 40), (60, 60), (40, 60)]],
        )
        pieces = clip_polylines_to_domain([[(-10.0, 50.0), (110.0, 50.0)]], domain)
        assert len(pieces) == 2
        for piece in pieces:
            assert all(not (40.0 < x < 60.0) for x, _ in piece)

    def test_short_polyline_skipped(self):
        from generators.utils import clip_polylines_to_domain

        assert clip_polylines_to_domain([[(50.0, 50.0)]], self._square()) == []

    def test_input_order_preserved(self):
        from generators.utils import clip_polylines_to_domain

        a = [(10.0, 10.0), (20.0, 10.0)]
        b = [(10.0, 90.0), (20.0, 90.0)]
        pieces = clip_polylines_to_domain([a, b], self._square())
        assert pieces == [a, b]

    def test_clip_is_deterministic(self):
        from generators.utils import clip_polylines_to_domain

        path = [(20.0, 50.0), (120.0, 50.0), (120.0, 80.0), (20.0, 80.0)]
        first = clip_polylines_to_domain([path], self._square())
        second = clip_polylines_to_domain([path], self._square())
        assert first == second

    def test_mixed_collection_keeps_only_lines(self):
        from generators.utils import clip_polylines_to_domain

        path = [(-10.0, 10.0), (0.0, 0.0), (10.0, -10.0), (50.0, -10.0), (50.0, 50.0)]
        pieces = clip_polylines_to_domain([path], self._square())
        assert len(pieces) == 1
        assert pieces[0][0] == pytest.approx((50.0, 0.0), abs=1e-9)
        assert pieces[0][-1] == pytest.approx((50.0, 50.0), abs=1e-9)

    def test_drops_pieces_below_min_length(self):
        from generators.utils import clip_polylines_to_domain

        short = [(10.0, 10.0), (12.0, 10.0)]
        long = [(10.0, 90.0), (60.0, 90.0)]
        pieces = clip_polylines_to_domain([short, long], self._square(), min_length_mm=3.0)
        assert pieces == [long]

    def test_self_intersecting_path_inside_returned_unchanged(self):
        from generators.utils import clip_polylines_to_domain

        figure_eight = [(20.0, 20.0), (80.0, 80.0), (80.0, 20.0), (20.0, 80.0), (20.0, 20.0)]
        pieces = clip_polylines_to_domain([figure_eight], self._square())
        assert pieces == [figure_eight]

    def test_grazing_edge_from_inside_returns_one_piece(self):
        from generators.utils import clip_polylines_to_domain

        path = [(10.0, 90.0), (30.0, 100.0), (50.0, 90.0), (70.0, 100.0), (90.0, 90.0)]
        pieces = clip_polylines_to_domain([path], self._square())
        assert pieces == [path]

    def test_negative_min_length_raises(self):
        from generators.utils import clip_polylines_to_domain

        with pytest.raises(ValueError, match="min_length_mm"):
            clip_polylines_to_domain([[(10.0, 10.0), (20.0, 10.0)]], self._square(), min_length_mm=-1.0)


# =============================================================================
# Phyllotaxis
# =============================================================================


def _spiral_points(count: int, spacing_mm: float, angle_deg: float) -> list[tuple[float, float]]:
    return [point for point, _ in spiral_positions(count, spacing_mm, angle_deg)]


class TestPlaceItem:
    def test_scale_one_matches_old_radial_placement(self):
        item = Item(
            kind="shape",
            type="Polyline",
            geometry=Geometry(data={"points": [[1.0, 0.0], [0.0, 2.0]], "is_open": True}),
            placement=Placement(center_xy_mm=(3.0, 0.0)),
            feature=Feature(type="engrave", depth_mm=0.3),
        )
        placed = place_item(item, angle_rad=math.pi / 2, offset=(10.0, 20.0), shape_id="s")
        assert placed.geometry is not None
        assert placed.placement is not None
        points = placed.geometry.data["points"]
        assert points[0] == pytest.approx([0.0, 1.0], abs=1e-12)
        assert points[1] == pytest.approx([-2.0, 0.0], abs=1e-12)
        assert placed.placement.center_xy_mm == pytest.approx((10.0, 23.0), abs=1e-12)
        assert placed.shape_id == "s"

    def test_scales_circle_diameter(self):
        item = Item(
            kind="shape",
            type="Circle",
            geometry=Geometry(data={"diameter_mm": 6.0}),
            placement=Placement(center_xy_mm=(0.0, 0.0)),
            feature=Feature(type="pocket", depth_mm=3.0),
        )
        placed = place_item(item, angle_rad=0.0, offset=(5.0, 5.0), shape_id="c", scale=0.5)
        assert placed.geometry is not None
        assert placed.geometry.data["diameter_mm"] == pytest.approx(3.0)


class TestItemInsideDomain:
    def _holed_square(self) -> Domain:
        return Domain.from_polygon(
            [(0, 0), (100, 0), (100, 100), (0, 100)],
            holes=[[(49, 49), (51, 49), (51, 51), (49, 51)]],
        )

    def _triangle(self, item_type: str) -> Item:
        return Item(
            kind="shape",
            type=item_type,
            geometry=Geometry(data={"points": [[-6.0, -6.0], [6.0, -6.0], [-6.0, 6.0], [-6.0, -6.0]]}),
            placement=Placement(center_xy_mm=(52.0, 52.0)),
            feature=Feature(type="pocket", depth_mm=1.0),
        )

    def test_polygon_covering_hole_is_outside(self):
        assert not item_inside_domain(self._triangle("Polygon"), self._holed_square())

    def test_polyline_around_hole_is_inside(self):
        assert item_inside_domain(self._triangle("Polyline"), self._holed_square())

    def test_polyline_crossing_hole_is_outside(self):
        line = Item(
            kind="shape",
            type="Polyline",
            geometry=Geometry(data={"points": [[-5.0, 0.0], [5.0, 0.0]]}),
            placement=Placement(center_xy_mm=(50.0, 50.0)),
            feature=Feature(type="engrave", depth_mm=0.3),
        )
        assert not item_inside_domain(line, self._holed_square())

    def test_line_item_uses_start_and_end(self):
        line = Item(
            kind="shape",
            type="Line",
            geometry=Geometry(data={"start": [-5.0, 0.0], "end": [5.0, 0.0]}),
            placement=Placement(center_xy_mm=(20.0, 20.0)),
            feature=Feature(type="engrave", depth_mm=0.3),
        )
        assert item_inside_domain(line, self._holed_square())
        assert not item_inside_domain(
            replace(line, placement=Placement(center_xy_mm=(50.0, 50.0))), self._holed_square()
        )


class TestSpiralUtils:
    def test_closest_pair_golden_equals_spacing(self):
        assert closest_pair_distance(_spiral_points(200, 7.0, GOLDEN_ANGLE_DEG)) == pytest.approx(7.0, abs=1e-9)

    def test_closest_pair_ninety_degrees(self):
        assert closest_pair_distance(_spiral_points(200, 7.0, 90.0)) < 1.0

    def test_closest_pair_single_point_is_inf(self):
        assert closest_pair_distance([(0.0, 0.0)]) == math.inf


class TestPhyllotaxisParams:
    def test_rejects_diameter_equal_to_spacing(self):
        with pytest.raises(ValueError, match=r"spacing 7\.0mm"):
            PhyllotaxisHoleParams(count=200, spacing_mm=7.0, diameter_mm=7.0, depth_mm="through")

    def test_rejects_overlap_at_non_golden_angle(self):
        with pytest.raises(ValueError, match=r"closest-pair distance 0\.997mm"):
            PhyllotaxisHoleParams(count=200, spacing_mm=7.0, diameter_mm=5.0, depth_mm="through", angle_deg=90.0)

    def test_short_non_golden_pattern_is_valid(self):
        PhyllotaxisHoleParams(count=10, spacing_mm=7.0, diameter_mm=5.0, depth_mm="through", angle_deg=90.0)

    def test_single_point_has_no_spacing_limit(self):
        PhyllotaxisHoleParams(count=1, spacing_mm=7.0, diameter_mm=50.0, depth_mm="through")

    def test_svg_uses_diagonal_extent(self):
        with pytest.raises(ValueError, match=r"11\.314mm"):
            PhyllotaxisSvgParams(count=50, spacing_mm=10.0, svg_path="M 0 0 L 1 1", size_mm=8.0, depth_mm=0.3)
        PhyllotaxisSvgParams(count=50, spacing_mm=10.0, svg_path="M 0 0 L 1 1", size_mm=7.0, depth_mm=0.3)

    def test_svg_rejects_profile_feature(self):
        with pytest.raises(ValueError, match="feature_type"):
            PhyllotaxisSvgParams(
                count=50,
                spacing_mm=10.0,
                svg_path="M 0 0 L 1 1",
                size_mm=6.0,
                depth_mm=0.3,
                feature_type="profile",  # type: ignore[arg-type]
            )

    def test_scale_with_radius_requires_min_size(self):
        with pytest.raises(ValueError, match="requires min_size_mm"):
            PhyllotaxisPocketParams(count=50, spacing_mm=8.0, diameter_mm=6.0, depth_mm=3.0, scale_with_radius=True)

    def test_min_size_rejected_without_scale_with_radius(self):
        with pytest.raises(ValueError, match="requires scale_with_radius"):
            PhyllotaxisPocketParams(count=50, spacing_mm=8.0, diameter_mm=6.0, depth_mm=3.0, min_size_mm=3.0)

    def test_min_size_must_not_exceed_diameter(self):
        with pytest.raises(ValueError, match="must not exceed"):
            PhyllotaxisPocketParams(
                count=50, spacing_mm=8.0, diameter_mm=6.0, depth_mm=3.0, scale_with_radius=True, min_size_mm=7.0
            )


class TestParamsImport:
    def test_params_module_imports_without_area_package(self):
        import subprocess
        import sys

        result = subprocess.run(
            [sys.executable, "-c", "import generators.params.area"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr


class TestPhyllotaxisGenerators:
    def _large_square(self) -> Domain:
        return Domain.from_rectangle(1000, 1000, center=(500, 500))

    def _centers(self, items: list[Item]) -> list[tuple[float, float]]:
        centers = []
        for item in items:
            assert item.placement is not None
            centers.append(item.placement.center_xy_mm)
        return centers

    def _data(self, item: Item) -> dict:
        assert item.geometry is not None
        return item.geometry.data

    def test_consecutive_points_differ_by_golden_angle(self):
        params = PhyllotaxisHoleParams(count=50, spacing_mm=7.0, diameter_mm=5.0, depth_mm="through")
        items = phyllotaxis_hole_generator(self._large_square(), params)
        assert len(items) == 50
        polar = [math.atan2(y - 500.0, x - 500.0) for x, y in self._centers(items)[1:]]
        for a, b in itertools.pairwise(polar):
            delta = math.degrees(b - a) % 360.0
            assert delta == pytest.approx(GOLDEN_ANGLE_DEG, abs=1e-9)

    def test_radius_is_spacing_times_sqrt_index(self):
        params = PhyllotaxisHoleParams(count=50, spacing_mm=7.0, diameter_mm=5.0, depth_mm="through")
        items = phyllotaxis_hole_generator(self._large_square(), params)
        for i, (x, y) in enumerate(self._centers(items)):
            assert math.dist((x, y), (500.0, 500.0)) == pytest.approx(7.0 * math.sqrt(i), abs=1e-9)

    def test_circle_parent_drops_edge_motifs(self):
        domain = Domain.from_circle(200, center=(150, 150))
        params = PhyllotaxisHoleParams(count=400, spacing_mm=7.0, diameter_mm=5.0, depth_mm="through")
        items = phyllotaxis_hole_generator(domain, params)
        assert 0 < len(items) < 400
        for item in items:
            assert item.type == "Circle"
            assert item.feature is not None
            assert item.feature.is_through
        for center in self._centers(items):
            assert math.dist(center, (150.0, 150.0)) + 2.5 <= 100.0

    def test_scale_with_radius_grows_pockets(self):
        params = PhyllotaxisPocketParams(
            count=100, spacing_mm=8.0, diameter_mm=6.0, depth_mm=3.0, scale_with_radius=True, min_size_mm=0.1
        )
        items = phyllotaxis_pocket_generator(self._large_square(), params)
        diameters = [self._data(item)["diameter_mm"] for item in items]
        radii = [math.dist(c, (500.0, 500.0)) for c in self._centers(items)]
        assert radii == sorted(radii)
        assert diameters == sorted(diameters)
        assert diameters[-1] == pytest.approx(6.0)
        assert all(item.feature is not None and item.feature.type == "pocket" for item in items)

    def test_min_size_drops_inner_motifs(self):
        params = PhyllotaxisPocketParams(
            count=150, spacing_mm=8.0, diameter_mm=6.0, depth_mm=3.0, scale_with_radius=True, min_size_mm=3.0
        )
        items = phyllotaxis_pocket_generator(self._large_square(), params)
        first_index = next(i for i in range(150) if 6.0 * math.sqrt((i + 1) / 150) >= 3.0)
        assert len(items) == 150 - first_index
        assert min(self._data(item)["diameter_mm"] for item in items) >= 3.0
        first_radius = math.dist(self._centers(items)[0], (500.0, 500.0))
        assert first_radius == pytest.approx(8.0 * math.sqrt(first_index), abs=1e-9)

    def test_svg_motifs_face_outward(self):
        params = PhyllotaxisSvgParams(
            count=20, spacing_mm=10.0, svg_path="M 0 0 L 20 10 L 0 20 Z", size_mm=6.0, depth_mm=0.3
        )
        fixed = phyllotaxis_svg_generator(self._large_square(), replace(params, rotate_element=False))
        turned = phyllotaxis_svg_generator(self._large_square(), params)
        assert len(fixed) == len(turned) == 20
        for i, (a, b) in enumerate(zip(fixed, turned, strict=True)):
            theta = math.radians(i * GOLDEN_ANGLE_DEG)
            expected = rotate_points([(p[0], p[1]) for p in self._data(a)["points"]], theta)
            assert self._data(b)["points"][0] == pytest.approx(list(expected[0]), abs=1e-9)

    def test_rotated_parent_rotates_spiral_and_motifs(self):
        rotation = math.pi / 6
        domain = replace(self._large_square(), local_rotation_rad=rotation)
        params = PhyllotaxisSvgParams(
            count=20,
            spacing_mm=10.0,
            svg_path="M 0 0 L 20 10 L 0 20 Z",
            size_mm=6.0,
            depth_mm=0.3,
            rotate_element=False,
        )
        unrotated = phyllotaxis_svg_generator(self._large_square(), params)
        rotated = phyllotaxis_svg_generator(domain, params)
        assert len(rotated) == len(unrotated) == 20
        for a, b in zip(unrotated, rotated, strict=True):
            (ax, ay), (bx, by) = self._centers([a])[0], self._centers([b])[0]
            expected_center = rotate_points([(ax - 500.0, ay - 500.0)], rotation)[0]
            assert (bx - 500.0, by - 500.0) == pytest.approx(expected_center, abs=1e-9)
            expected = rotate_points([(p[0], p[1]) for p in self._data(a)["points"]], rotation)
            for actual, want in zip(self._data(b)["points"], expected, strict=True):
                assert actual == pytest.approx(list(want), abs=1e-9)

    def test_svg_scale_with_radius_drops_small_motifs(self):
        params = PhyllotaxisSvgParams(
            count=100,
            spacing_mm=10.0,
            svg_path="M 0 0 L 20 0 L 20 20 L 0 20 Z",
            size_mm=6.0,
            depth_mm=0.3,
            rotate_element=False,
            scale_with_radius=True,
            min_size_mm=3.0,
        )
        items = phyllotaxis_svg_generator(self._large_square(), params)
        first_index = next(i for i in range(100) if 6.0 * math.sqrt((i + 1) / 100) >= 3.0)
        assert len(items) == 100 - first_index
        widths = [
            max(p[0] for p in self._data(i)["points"]) - min(p[0] for p in self._data(i)["points"]) for i in items
        ]
        assert min(widths) >= 3.0 - 1e-9
        assert widths[-1] == pytest.approx(6.0)
        assert widths == sorted(widths)

    def test_holed_parent_drops_motifs_over_hole(self):
        domain = Domain.from_polygon(
            [(0, 0), (200, 0), (200, 200), (0, 200)],
            holes=[[(80, 80), (120, 80), (120, 120), (80, 120)]],
        )
        params = PhyllotaxisHoleParams(count=200, spacing_mm=7.0, diameter_mm=5.0, depth_mm="through")
        items = phyllotaxis_hole_generator(domain, params)
        assert items
        for x, y in self._centers(items):
            assert not (77.5 < x < 122.5 and 77.5 < y < 122.5)

    def test_nothing_fits_raises_skip(self):
        domain = Domain.from_rectangle(4, 4, center=(2, 2))
        params = PhyllotaxisHoleParams(count=10, spacing_mm=7.0, diameter_mm=5.0, depth_mm="through")
        with pytest.raises(GeneratorSkipError):
            phyllotaxis_hole_generator(domain, params)
        assert phyllotaxis_hole_generator(domain, params, allow_empty=True) == []

    def test_deterministic(self):
        params = PhyllotaxisSvgParams(
            count=60, spacing_mm=10.0, svg_path="M 0 0 L 20 10 L 0 20 Z", size_mm=6.0, depth_mm=0.3
        )
        domain = Domain.from_circle(200, center=(150, 150))
        first = phyllotaxis_svg_generator(domain, params)
        second = phyllotaxis_svg_generator(domain, params)
        assert [self._data(i) for i in first] == [self._data(i) for i in second]
        assert self._centers(first) == self._centers(second)


# =============================================================================
# Voronoi
# =============================================================================


def _voronoi_circle() -> Domain:
    return Domain.from_circle(200, center=(150, 150))


def _sheet_points(item: Item) -> list[tuple[float, float]]:
    assert item.placement is not None
    assert item.geometry is not None
    cx, cy = item.placement.center_xy_mm
    return [(x + cx, y + cy) for x, y in item.geometry.data["points"]]


def _pocket_polygon(item: Item) -> Polygon:
    assert item.placement is not None
    assert item.geometry is not None
    cx, cy = item.placement.center_xy_mm
    holes = [[(x + cx, y + cy) for x, y in hole] for hole in item.geometry.data.get("holes", [])]
    return Polygon(_sheet_points(item), holes)


class TestVoronoiParams:
    def test_requires_exactly_one_seed_source(self):
        with pytest.raises(ValueError, match="exactly one"):
            VoronoiParams(depth_mm=0.5)
        with pytest.raises(ValueError, match="exactly one"):
            VoronoiParams(depth_mm=0.5, seed_count=10, points=((0.0, 0.0), (10.0, 0.0)))

    def test_points_require_two_distinct(self):
        with pytest.raises(ValueError, match="distinct"):
            VoronoiParams(depth_mm=0.5, points=((0.0, 0.0), (0.0, 0.0)))
        VoronoiParams(depth_mm=0.5, points=((0.0, 0.0), (0.0, 0.0), (10.0, 0.0)))

    def test_points_reject_seed(self):
        with pytest.raises(ValueError, match="seed"):
            VoronoiParams(depth_mm=0.5, points=((0.0, 0.0), (10.0, 0.0)), seed=3)

    def test_points_reject_margin(self):
        with pytest.raises(ValueError, match="margin"):
            VoronoiParams(depth_mm=0.5, points=((0.0, 0.0), (10.0, 0.0)), margin_mm=5.0)

    def test_points_reject_min_spacing(self):
        with pytest.raises(ValueError, match="min_spacing"):
            VoronoiParams(depth_mm=0.5, points=((0.0, 0.0), (10.0, 0.0)), min_spacing_mm=5.0)

    def test_seed_must_be_non_negative(self):
        with pytest.raises(ValueError, match="seed"):
            VoronoiParams(depth_mm=0.5, seed_count=10, seed=-1)

    def test_min_spacing_must_be_positive(self):
        with pytest.raises(ValueError, match="min_spacing"):
            VoronoiParams(depth_mm=0.5, seed_count=10, min_spacing_mm=0.0)

    def test_pocket_requires_line_width(self):
        with pytest.raises(ValueError, match="line_width"):
            VoronoiParams(depth_mm=3.0, seed_count=10, mode="pocket")

    def test_engrave_rejects_cell_inset(self):
        with pytest.raises(ValueError, match="cell_inset"):
            VoronoiParams(depth_mm=0.5, seed_count=10, cell_inset_mm=1.0)

    def test_engrave_rejects_rest(self):
        with pytest.raises(ValueError, match="rest"):
            VoronoiParams(depth_mm=0.5, seed_count=10, rest=RestSpec(tool_diameter_mm=3.175))


class TestVoronoiGenerator:
    def _seeded(self, seed: int) -> VoronoiParams:
        return VoronoiParams(depth_mm=0.5, seed_count=40, seed=seed, min_spacing_mm=12.0)

    def _pocket_params(self) -> VoronoiParams:
        return VoronoiParams(depth_mm=3.0, seed_count=25, seed=3, min_spacing_mm=18.0, mode="pocket", line_width_mm=4.0)

    def _u_shape(self) -> Domain:
        return Domain.from_polygon([(0, 0), (120, 0), (120, 100), (80, 100), (80, 30), (40, 30), (40, 100), (0, 100)])

    def test_same_seed_same_output(self):
        first = voronoi_generator(_voronoi_circle(), self._seeded(7))
        second = voronoi_generator(_voronoi_circle(), self._seeded(7))
        assert [_sheet_points(i) for i in first] == [_sheet_points(i) for i in second]

    def test_different_seed_different_output(self):
        first = voronoi_generator(_voronoi_circle(), self._seeded(1))
        second = voronoi_generator(_voronoi_circle(), self._seeded(2))
        assert [_sheet_points(i) for i in first] != [_sheet_points(i) for i in second]

    def test_sampling_draws_x_then_y(self):
        domain = Domain.from_rectangle(200, 100, center=(150, 100))
        params = VoronoiParams(depth_mm=0.5, seed_count=10, seed=7)
        rng = np.random.default_rng(7)
        x_min, y_min, x_max, y_max = domain.polygon.bounds
        expected = []
        for _ in range(10):
            x = float(rng.uniform(x_min, x_max))
            y = float(rng.uniform(y_min, y_max))
            expected.append((x, y))
        assert _sample_seeds(domain, 10, params) == expected

    def test_seeds_respect_min_spacing(self):
        seeds = _sample_seeds(_voronoi_circle(), 40, self._seeded(7))
        assert len(seeds) == 40
        assert all(math.dist(a, b) >= 12.0 for a, b in itertools.combinations(seeds, 2))

    def test_unsatisfiable_spacing_raises(self):
        params = VoronoiParams(depth_mm=0.5, seed_count=40, min_spacing_mm=60.0)
        with pytest.raises(ValueError, match="of 40 seeds") as excinfo:
            voronoi_generator(_voronoi_circle(), params, allow_empty=True)
        assert excinfo.type is ValueError

    def test_empty_seed_region_names_margin(self):
        params = VoronoiParams(depth_mm=0.5, seed_count=10, margin_mm=150.0)
        with pytest.raises(ValueError, match="margin") as excinfo:
            voronoi_generator(_voronoi_circle(), params, allow_empty=True)
        assert excinfo.type is ValueError

    def test_explicit_point_outside_parent_raises(self):
        params = VoronoiParams(depth_mm=0.5, points=((0.0, 0.0), (150.0, 0.0)))
        with pytest.raises(ValueError, match="point 1") as excinfo:
            voronoi_generator(_voronoi_circle(), params, allow_empty=True)
        assert excinfo.type is ValueError

    def test_engrave_has_no_duplicate_segments(self):
        items = voronoi_generator(_voronoi_circle(), self._seeded(7))
        segments = [
            tuple(sorted((tuple(round(v, 6) for v in a), tuple(round(v, 6) for v in b))))
            for item in items
            for a, b in itertools.pairwise(_sheet_points(item))
        ]
        assert len(segments) == len(set(segments))

    def test_engrave_pieces_are_oriented_and_sorted(self):
        pieces = [tuple(_sheet_points(item)) for item in voronoi_generator(_voronoi_circle(), self._seeded(7))]
        assert all(piece[0] <= piece[-1] for piece in pieces)
        assert pieces == sorted(pieces)

    def test_engrave_omits_outline(self):
        domain = _voronoi_circle()
        outline = domain.polygon.boundary.buffer(1e-3)
        items = voronoi_generator(domain, self._seeded(7))
        assert items
        assert not any(LineString(_sheet_points(item)).within(outline) for item in items)

    def test_engrave_two_points(self):
        params = VoronoiParams(depth_mm=0.5, points=((-40.0, 0.0), (40.0, 0.0)))
        items = voronoi_generator(_voronoi_circle(), params)
        assert len(items) == 1
        assert all(x == pytest.approx(150.0, abs=1e-6) for x, _ in _sheet_points(items[0]))

    def test_explicit_three_points(self):
        local = ((-40.0, -30.0), (35.0, -20.0), (0.0, 45.0))
        params = VoronoiParams(depth_mm=0.5, points=local)
        items = voronoi_generator(_voronoi_circle(), params)
        (ax, ay), (bx, by), (cx, cy) = ((x + 150.0, y + 150.0) for x, y in local)
        d = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
        ux = ((ax**2 + ay**2) * (by - cy) + (bx**2 + by**2) * (cy - ay) + (cx**2 + cy**2) * (ay - by)) / d
        uy = ((ax**2 + ay**2) * (cx - bx) + (bx**2 + by**2) * (ax - cx) + (cx**2 + cy**2) * (bx - ax)) / d
        assert len(items) == 3
        for item in items:
            points = _sheet_points(item)
            assert min(math.dist(points[0], (ux, uy)), math.dist(points[-1], (ux, uy))) < 1e-6

    def test_pocket_webs_are_line_width(self):
        domain = Domain.from_rectangle(200, 200, center=(150, 150))
        pockets = [_pocket_polygon(item) for item in voronoi_generator(domain, self._pocket_params())]
        inner = domain.polygon.buffer(-2 + 1e-6)
        assert len(pockets) == 25
        assert all(inner.covers(pocket) for pocket in pockets)
        assert all(a.distance(b) >= 4 - 1e-6 for a, b in itertools.combinations(pockets, 2))

    def test_pocket_items_carry_rest(self):
        rest = RestSpec(tool_diameter_mm=3.175, rough_allowance_mm=0.3)
        domain = Domain.from_rectangle(200, 200, center=(150, 150))
        items = voronoi_generator(domain, replace(self._pocket_params(), rest=rest))
        assert items
        assert all(item.feature is not None and item.feature.rest == rest for item in items)

    def test_pocket_concave_parent_split_cell(self):
        domain = self._u_shape()
        sheet = [(20.0, 90.0), (60.0, 10.0), (110.0, 10.0)]
        cells = voronoi_diagram(MultiPoint(sheet), envelope=domain.polygon).geoms
        assert any(isinstance(cell.intersection(domain.polygon), MultiPolygon) for cell in cells)
        ox, oy = domain.local_origin or (0.0, 0.0)
        params = VoronoiParams(
            depth_mm=3.0, points=tuple((x - ox, y - oy) for x, y in sheet), mode="pocket", line_width_mm=4.0
        )
        assert len(voronoi_generator(domain, params)) == 4

    def test_explicit_points_follow_rotated_domain(self):
        domain = Domain.from_rectangle(200, 200, center=(150, 150), rotation_rad=math.pi / 6)
        local = ((-20.0, 0.0), (20.0, 0.0))
        seeds = [local_to_sheet(point, domain) for point in local]
        items = voronoi_generator(domain, VoronoiParams(depth_mm=0.5, points=local))
        assert len(items) == 1
        for vertex in _sheet_points(items[0]):
            assert math.dist(vertex, seeds[0]) == pytest.approx(math.dist(vertex, seeds[1]), abs=1e-6)


# =============================================================================
# StringArt
# =============================================================================


def _string_art_square() -> Domain:
    return Domain.from_rectangle(200, 200, center=(100, 100))


def _string_art_l_shape() -> Domain:
    return Domain.from_polygon([(0, 0), (200, 0), (200, 200), (100, 200), (100, 100), (0, 100)])


def _string_art_pieces(domain: Domain, params: StringArtParams) -> list[list[tuple[float, float]]]:
    return [_sheet_points(item) for item in string_art_generator(domain, params)]


def _has_piece(
    pieces: list[list[tuple[float, float]]],
    start: tuple[float, float],
    end: tuple[float, float],
    tolerance_mm: float = 1e-5,
) -> bool:
    return any(
        max(math.dist(piece[0], start), math.dist(piece[-1], end)) < tolerance_mm
        or max(math.dist(piece[0], end), math.dist(piece[-1], start)) < tolerance_mm
        for piece in pieces
    )


def _boundary_overlap_mm(domain: Domain, piece: list[tuple[float, float]]) -> float:
    return LineString(piece).intersection(domain.polygon.boundary.buffer(1e-6)).length


class TestStringArtParams:
    def test_multiply_requires_factor(self):
        with pytest.raises(ValueError, match="factor"):
            StringArtParams(anchors=72, rule="multiply", depth_mm=0.3)

    def test_skip_rejects_factor(self):
        with pytest.raises(ValueError, match="factor"):
            StringArtParams(anchors=72, rule="skip", step=5, factor=2, depth_mm=0.3)

    def test_step_must_be_less_than_anchors(self):
        with pytest.raises(ValueError, match="step"):
            StringArtParams(anchors=12, rule="skip", step=12, depth_mm=0.3)

    def test_rejects_two_anchors(self):
        with pytest.raises(ValueError, match="anchors"):
            StringArtParams(anchors=2, rule="mirror", depth_mm=0.3)


class TestStringArtGenerator:
    def _circle(self) -> Domain:
        return Domain.from_circle(200, center=(100, 100))

    def test_cardioid_chord_count(self):
        items = string_art_generator(
            self._circle(), StringArtParams(anchors=72, rule="multiply", factor=2, depth_mm=0.3)
        )
        assert len(items) == 70

    def test_skip_half_emits_each_diameter_once(self):
        items = string_art_generator(self._circle(), StringArtParams(anchors=12, rule="skip", step=6, depth_mm=0.3))
        assert len(items) == 6

    def test_mirror_odd_drops_middle(self):
        items = string_art_generator(self._circle(), StringArtParams(anchors=11, rule="mirror", depth_mm=0.3))
        assert len(items) == 5

    def test_anchors_evenly_spaced_on_circle(self):
        pieces = _string_art_pieces(self._circle(), StringArtParams(anchors=40, rule="skip", step=1, depth_mm=0.3))
        lengths = [math.dist(piece[0], piece[-1]) for piece in pieces]
        assert len(lengths) == 40
        assert max(lengths) - min(lengths) < 1e-9

    def test_anchor_zero_at_boundary_start(self):
        pieces = _string_art_pieces(_string_art_square(), StringArtParams(anchors=4, rule="skip", step=2, depth_mm=0.3))
        assert len(pieces) == 2
        assert _has_piece(pieces, (0.0, 0.0), (200.0, 200.0))
        assert _has_piece(pieces, (200.0, 0.0), (0.0, 200.0))

    def test_phase_shifts_anchors(self):
        params = StringArtParams(anchors=4, rule="skip", step=2, phase_deg=45.0, depth_mm=0.3)
        pieces = _string_art_pieces(_string_art_square(), params)
        assert len(pieces) == 2
        assert _has_piece(pieces, (100.0, 0.0), (100.0, 200.0))
        assert _has_piece(pieces, (200.0, 100.0), (0.0, 100.0))

    def test_boundary_chords_dropped(self):
        domain = _string_art_square()
        pieces = _string_art_pieces(domain, StringArtParams(anchors=80, rule="multiply", factor=2, depth_mm=0.3))
        assert len(pieces) == 57
        assert all(_boundary_overlap_mm(domain, piece) < 1e-3 for piece in pieces)

    def test_all_boundary_chords_raise(self):
        params = StringArtParams(anchors=4, rule="skip", step=1, depth_mm=0.3)
        with pytest.raises(GeneratorSkipError):
            string_art_generator(_string_art_square(), params)
        assert string_art_generator(_string_art_square(), params, allow_empty=True) == []

    def test_concave_parent_splits_chords(self):
        domain = _string_art_l_shape()
        pieces = _string_art_pieces(domain, StringArtParams(anchors=40, rule="skip", step=17, depth_mm=0.3))
        assert len(pieces) == 46
        inside = domain.polygon.buffer(1e-6)
        assert all(inside.covers(LineString(piece)) for piece in pieces)
        assert all(_boundary_overlap_mm(domain, piece) < 1e-3 for piece in pieces)
        assert _has_piece(pieces, (100.0, 0.0), (100.0, 100.0))
        assert _has_piece(pieces, (100.0, 100.0), (200.0, 100.0))

    def test_min_length_drops_short_pieces(self):
        params = StringArtParams(anchors=40, rule="skip", step=17, min_length_mm=50.0, depth_mm=0.3)
        pieces = _string_art_pieces(_string_art_l_shape(), params)
        assert len(pieces) == 44
        assert all(math.dist(piece[0], piece[-1]) >= 50.0 for piece in pieces)

    def test_chord_through_reflex_vertex_splits(self):
        pieces = _string_art_pieces(
            _string_art_l_shape(), StringArtParams(anchors=8, rule="skip", step=4, depth_mm=0.3)
        )
        expected = [
            ((0.0, 0.0), (100.0, 100.0)),
            ((100.0, 100.0), (200.0, 200.0)),
            ((100.0, 0.0), (100.0, 100.0)),
            ((100.0, 100.0), (200.0, 0.0)),
            ((100.0, 100.0), (200.0, 100.0)),
        ]
        assert len(pieces) == len(expected)
        assert all(_has_piece(pieces, start, end) for start, end in expected)

    def test_deterministic(self):
        params = StringArtParams(anchors=40, rule="skip", step=17, phase_deg=15.0, depth_mm=0.3)
        first = _string_art_pieces(_string_art_l_shape(), params)
        second = _string_art_pieces(_string_art_l_shape(), params)
        assert first == second


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
    rose_curve_generator,
    spirograph_curve_generator,
    lissajous_curve_generator,
    phyllotaxis_hole_generator,
    phyllotaxis_pocket_generator,
    phyllotaxis_svg_generator,
    voronoi_generator,
    string_art_generator,
]


@pytest.mark.parametrize("gen", ALL_GENERATORS, ids=lambda g: g.__name__)
def test_generator_satisfies_protocol(gen):
    assert isinstance(gen, Generator), f"{gen.__name__} does not satisfy the Generator protocol"
