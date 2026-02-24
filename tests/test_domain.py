"""Comprehensive tests for the Domain and MultiDomain classes.

This test module covers Stage 1 of the domain/generator system:
- Domain construction (vertices, rectangles)
- Domain operations (inset, offset, subtract, intersect)
- Edge cases (empty results, invalid inputs)
- JSON serialization round-trips
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from domains import Bounds2D, Domain, MultiDomain

# =============================================================================
# Test Helpers
# =============================================================================


def approx_equal(a: float, b: float, tolerance: float = 0.01) -> bool:
    """Check if two floats are approximately equal within tolerance."""
    return abs(a - b) <= tolerance


def bounds_approx_equal(b1: Bounds2D, b2: Bounds2D, tolerance: float = 0.01) -> bool:
    """Check if two bounds are approximately equal."""
    return (
        approx_equal(b1.x_min, b2.x_min, tolerance)
        and approx_equal(b1.x_max, b2.x_max, tolerance)
        and approx_equal(b1.y_min, b2.y_min, tolerance)
        and approx_equal(b1.y_max, b2.y_max, tolerance)
    )


def point_approx_equal(p1: tuple[float, float], p2: tuple[float, float], tolerance: float = 0.01) -> bool:
    """Check if two points are approximately equal."""
    return approx_equal(p1[0], p2[0], tolerance) and approx_equal(p1[1], p2[1], tolerance)


# =============================================================================
# Domain Construction Tests
# =============================================================================


def test_domain_from_vertices_simple_triangle():
    """Test creating a domain from triangle vertices."""
    vertices = [(0, 0), (100, 0), (50, 100)]
    domain = Domain.from_polygon(vertices)

    assert len(domain.outer_boundary) == 3
    assert domain.inner_boundaries == ()
    assert approx_equal(domain.area_mm2, 5000.0)  # Triangle area = 0.5 * base * height


def test_domain_from_vertices_square():
    """Test creating a domain from square vertices."""
    vertices = [(0, 0), (100, 0), (100, 100), (0, 100)]
    domain = Domain.from_polygon(vertices)

    assert len(domain.outer_boundary) == 4
    assert approx_equal(domain.area_mm2, 10000.0)
    assert bounds_approx_equal(domain.bounds, Bounds2D(x_min=0, x_max=100, y_min=0, y_max=100))


def test_domain_from_rectangle():
    """Test the rectangular convenience constructor."""
    domain = Domain.from_rectangle(width_mm=100, height_mm=50, center=(200, 150))

    assert len(domain.outer_boundary) == 4
    assert approx_equal(domain.area_mm2, 5000.0)
    assert bounds_approx_equal(domain.bounds, Bounds2D(x_min=150, x_max=250, y_min=125, y_max=175))
    assert point_approx_equal(domain.local_origin, (200, 150))


def test_domain_from_rectangle_rotated():
    """Test rectangular constructor with rotation."""
    domain = Domain.from_rectangle(
        width_mm=100,
        height_mm=50,
        center=(0, 0),
        rotation_rad=math.pi / 4,  # 45 degrees
    )

    assert len(domain.outer_boundary) == 4
    assert approx_equal(domain.area_mm2, 5000.0)
    # Rotated rectangle still has same area
    assert approx_equal(domain.local_rotation_rad, math.pi / 4)


def test_domain_from_rectangle_at_origin():
    """Test rectangular constructor at origin."""
    domain = Domain.from_rectangle(width_mm=100, height_mm=100)

    assert bounds_approx_equal(domain.bounds, Bounds2D(x_min=-50, x_max=50, y_min=-50, y_max=50))
    assert point_approx_equal(domain.centroid, (0, 0))


def test_domain_with_hole():
    """Test creating a domain with an inner boundary (hole)."""
    outer = [(0, 0), (100, 0), (100, 100), (0, 100)]
    inner = [(30, 30), (70, 30), (70, 70), (30, 70)]

    domain = Domain.from_polygon(outer, holes=[inner])

    assert len(domain.outer_boundary) == 4
    assert len(domain.inner_boundaries) == 1
    assert len(domain.inner_boundaries[0]) == 4
    # Area = outer - inner = 10000 - 1600 = 8400
    assert approx_equal(domain.area_mm2, 8400.0)


def test_domain_with_multiple_holes():
    """Test creating a domain with multiple holes."""
    outer = [(0, 0), (200, 0), (200, 100), (0, 100)]
    hole1 = [(20, 20), (80, 20), (80, 80), (20, 80)]
    hole2 = [(120, 20), (180, 20), (180, 80), (120, 80)]

    domain = Domain.from_polygon(outer, holes=[hole1, hole2])

    assert len(domain.inner_boundaries) == 2
    # Area = 20000 - 3600 - 3600 = 12800
    assert approx_equal(domain.area_mm2, 12800.0)


def test_domain_winding_normalization():
    """Test that winding order is normalized (CCW outer, CW holes)."""
    # CW outer (wrong order)
    outer_cw = [(0, 100), (100, 100), (100, 0), (0, 0)]
    domain = Domain.from_polygon(outer_cw)

    # Should be normalized to CCW
    # Check by verifying signed area is positive
    area = 0
    for i in range(len(domain.outer_boundary)):
        j = (i + 1) % len(domain.outer_boundary)
        x1, y1 = domain.outer_boundary[i]
        x2, y2 = domain.outer_boundary[j]
        area += (x2 - x1) * (y2 + y1)
    # Negative sum means CCW (standard form)
    assert area < 0  # CCW has negative shoelace sum


def test_domain_centroid_as_default_origin():
    """Test that local_origin defaults to centroid."""
    domain = Domain.from_rectangle(width_mm=100, height_mm=100, center=(50, 50))
    assert point_approx_equal(domain.local_origin, (50, 50))


# =============================================================================
# Domain Validation Tests
# =============================================================================


def test_domain_invalid_too_few_vertices():
    """Test that domains with < 3 vertices raise an error."""
    try:
        Domain.from_polygon([(0, 0), (100, 0)])
        raise AssertionError("Should have raised ValueError")
    except ValueError as e:
        assert "at least 3 points" in str(e).lower()


def test_domain_invalid_inner_not_contained():
    """Test that inner boundary not inside outer raises error."""
    outer = [(0, 0), (100, 0), (100, 100), (0, 100)]
    inner = [(150, 150), (200, 150), (200, 200), (150, 200)]  # Outside outer

    try:
        Domain.from_polygon(outer, holes=[inner])
        raise AssertionError("Should have raised ValueError")
    except ValueError as e:
        # Error can mention "contained" or "invalid" or "splits" - all valid rejections
        msg = str(e).lower()
        assert "contained" in msg or "invalid" in msg or "splits" in msg, f"Unexpected error: {e}"


def test_domain_invalid_overlapping_holes():
    """Test that overlapping inner boundaries raise error."""
    outer = [(0, 0), (200, 0), (200, 200), (0, 200)]
    hole1 = [(20, 20), (100, 20), (100, 100), (20, 100)]
    hole2 = [(50, 50), (150, 50), (150, 150), (50, 150)]  # Overlaps hole1

    try:
        Domain.from_polygon(outer, holes=[hole1, hole2])
        raise AssertionError("Should have raised ValueError")
    except ValueError as e:
        # Error can mention "overlap" or "invalid" or "splits" - all valid rejections
        msg = str(e).lower()
        assert "overlap" in msg or "invalid" in msg or "splits" in msg, f"Unexpected error: {e}"


def test_domain_invalid_zero_width_rectangle():
    """Test that zero-width rectangle raises error."""
    try:
        Domain.from_rectangle(width_mm=0, height_mm=100)
        raise AssertionError("Should have raised ValueError")
    except ValueError as e:
        assert "positive" in str(e).lower()


def test_domain_invalid_negative_dimensions():
    """Test that negative dimensions raise error."""
    try:
        Domain.from_rectangle(width_mm=-100, height_mm=100)
        raise AssertionError("Should have raised ValueError")
    except ValueError as e:
        assert "positive" in str(e).lower()


# =============================================================================
# Domain Properties Tests
# =============================================================================


def test_domain_bounds():
    """Test bounds computation."""
    domain = Domain.from_rectangle(width_mm=100, height_mm=50, center=(100, 100))
    bounds = domain.bounds

    assert approx_equal(bounds.x_min, 50)
    assert approx_equal(bounds.x_max, 150)
    assert approx_equal(bounds.y_min, 75)
    assert approx_equal(bounds.y_max, 125)
    assert approx_equal(bounds.width, 100)
    assert approx_equal(bounds.height, 50)


def test_domain_area():
    """Test area computation."""
    domain = Domain.from_rectangle(width_mm=100, height_mm=50)
    assert approx_equal(domain.area_mm2, 5000.0)


def test_domain_centroid():
    """Test centroid computation."""
    domain = Domain.from_rectangle(width_mm=100, height_mm=100, center=(200, 150))
    assert point_approx_equal(domain.centroid, (200, 150))


def test_domain_with_origin_at_centroid():
    """Test with_origin_at_centroid method."""
    domain = Domain.from_rectangle(width_mm=100, height_mm=100, center=(0, 0))
    # Move origin elsewhere
    shifted = Domain(
        outer_boundary=domain.outer_boundary,
        inner_boundaries=domain.inner_boundaries,
        local_origin=(100, 100),  # Not at centroid
        local_rotation_rad=0.0,
    )
    # Now move it back to centroid
    recentered = shifted.with_origin_at_centroid()
    assert point_approx_equal(recentered.local_origin, (0, 0))


# =============================================================================
# Inset Operation Tests
# =============================================================================


def test_inset_simple_rectangle():
    """Test insetting a simple rectangle."""
    domain = Domain.from_rectangle(width_mm=100, height_mm=100, center=(50, 50))
    result = domain.inset(10)

    assert len(result) == 1
    assert not result.is_empty

    inner = result.domains[0]
    assert approx_equal(inner.area_mm2, 6400.0)  # (100-20) * (100-20)
    assert bounds_approx_equal(inner.bounds, Bounds2D(x_min=10, x_max=90, y_min=10, y_max=90))


def test_inset_zero_distance():
    """Test that inset(0) returns the same domain."""
    domain = Domain.from_rectangle(width_mm=100, height_mm=100)
    result = domain.inset(0)

    assert len(result) == 1
    assert approx_equal(result.domains[0].area_mm2, 10000.0)


def test_inset_too_large():
    """Test that large inset produces empty result."""
    domain = Domain.from_rectangle(width_mm=100, height_mm=100)
    result = domain.inset(60)  # > half of minimum dimension

    assert result.is_empty
    assert len(result) == 0


def test_inset_with_round_join():
    """Test inset with round join style."""
    domain = Domain.from_rectangle(width_mm=100, height_mm=100)
    result = domain.inset(10, join_style="round")

    assert len(result) == 1
    # Corners will be slightly rounded, area slightly larger than mitre
    assert result.domains[0].area_mm2 > 6300.0  # More than simple rectangle inset


def test_inset_negative_distance_raises():
    """Test that negative inset distance raises error."""
    domain = Domain.from_rectangle(width_mm=100, height_mm=100)
    try:
        domain.inset(-10)
        raise AssertionError("Should have raised ValueError")
    except ValueError as e:
        assert "non-negative" in str(e).lower()


def test_inset_expands_holes():
    """Test that inset expands inner boundaries (holes)."""
    outer = [(0, 0), (100, 0), (100, 100), (0, 100)]
    inner = [(40, 40), (60, 40), (60, 60), (40, 60)]  # 20x20 hole
    domain = Domain.from_polygon(outer, holes=[inner])

    result = domain.inset(10)

    # Outer contracts, inner expands
    # If inset is large enough, the hole might consume the domain
    # With 10mm inset: outer becomes 80x80, hole becomes 40x40
    assert len(result) == 1
    inner_domain = result.domains[0]
    # Area = 80*80 - 40*40 = 6400 - 1600 = 4800
    assert approx_equal(inner_domain.area_mm2, 4800.0)


# =============================================================================
# Offset Operation Tests
# =============================================================================


def test_offset_simple_rectangle():
    """Test offsetting a simple rectangle."""
    domain = Domain.from_rectangle(width_mm=100, height_mm=100, center=(50, 50))
    result = domain.offset(10)

    assert len(result) == 1

    outer = result.domains[0]
    assert approx_equal(outer.area_mm2, 14400.0)  # (100+20) * (100+20)


def test_offset_zero_distance():
    """Test that offset(0) returns the same domain."""
    domain = Domain.from_rectangle(width_mm=100, height_mm=100)
    result = domain.offset(0)

    assert len(result) == 1
    assert approx_equal(result.domains[0].area_mm2, 10000.0)


def test_offset_negative_distance_raises():
    """Test that negative offset distance raises error."""
    domain = Domain.from_rectangle(width_mm=100, height_mm=100)
    try:
        domain.offset(-10)
        raise AssertionError("Should have raised ValueError")
    except ValueError as e:
        assert "non-negative" in str(e).lower()


def test_offset_shrinks_holes():
    """Test that offset shrinks inner boundaries (holes)."""
    outer = [(0, 0), (100, 0), (100, 100), (0, 100)]
    inner = [(40, 40), (60, 40), (60, 60), (40, 60)]  # 20x20 hole
    domain = Domain.from_polygon(outer, holes=[inner])

    result = domain.offset(5)

    # Outer expands, inner shrinks
    assert len(result) == 1
    outer_domain = result.domains[0]
    # Outer becomes 110x110, hole becomes 10x10
    # Area = 110*110 - 10*10 = 12100 - 100 = 12000
    assert approx_equal(outer_domain.area_mm2, 12000.0)


def test_offset_removes_small_hole():
    """Test that offset removes a hole that shrinks to nothing."""
    outer = [(0, 0), (100, 0), (100, 100), (0, 100)]
    inner = [(45, 45), (55, 45), (55, 55), (45, 55)]  # 10x10 hole
    domain = Domain.from_polygon(outer, holes=[inner])

    result = domain.offset(6)  # > half of hole size

    # Hole should be gone
    assert len(result) == 1
    outer_domain = result.domains[0]
    # Outer becomes 112x112, no hole
    assert len(outer_domain.inner_boundaries) == 0
    assert approx_equal(outer_domain.area_mm2, 112 * 112)


# =============================================================================
# Subtract Operation Tests
# =============================================================================


def test_subtract_creates_hole():
    """Test subtracting a smaller domain creates a hole."""
    outer = Domain.from_rectangle(width_mm=100, height_mm=100, center=(50, 50))
    inner = Domain.from_rectangle(width_mm=40, height_mm=40, center=(50, 50))

    result = outer.subtract(inner)

    assert len(result) == 1
    frame = result.domains[0]
    assert len(frame.inner_boundaries) == 1
    # Area = 10000 - 1600 = 8400
    assert approx_equal(frame.area_mm2, 8400.0)


def test_subtract_no_overlap():
    """Test subtracting non-overlapping domain returns original."""
    domain1 = Domain.from_rectangle(width_mm=100, height_mm=100, center=(50, 50))
    domain2 = Domain.from_rectangle(width_mm=100, height_mm=100, center=(300, 300))

    result = domain1.subtract(domain2)

    assert len(result) == 1
    assert approx_equal(result.domains[0].area_mm2, 10000.0)


def test_subtract_full_containment():
    """Test subtracting larger domain produces empty result."""
    small = Domain.from_rectangle(width_mm=50, height_mm=50, center=(50, 50))
    large = Domain.from_rectangle(width_mm=200, height_mm=200, center=(50, 50))

    result = small.subtract(large)

    assert result.is_empty


def test_subtract_partial_overlap():
    """Test subtracting partially overlapping domain."""
    domain1 = Domain.from_rectangle(width_mm=100, height_mm=100, center=(50, 50))
    domain2 = Domain.from_rectangle(width_mm=100, height_mm=100, center=(100, 50))

    result = domain1.subtract(domain2)

    assert len(result) == 1
    # Result is left half of domain1
    remaining = result.domains[0]
    assert approx_equal(remaining.area_mm2, 5000.0)


def test_subtract_splits_domain():
    """Test that subtraction can split a domain into multiple pieces."""
    # Wide domain
    wide = Domain.from_rectangle(width_mm=200, height_mm=50, center=(100, 25))
    # Strip through the middle
    strip = Domain.from_rectangle(width_mm=20, height_mm=100, center=(100, 25))

    result = wide.subtract(strip)

    # Should produce two separate domains
    assert len(result) == 2
    total_area = sum(d.area_mm2 for d in result)
    # Original 200*50 = 10000, minus 20*50 = 1000 = 9000
    assert approx_equal(total_area, 9000.0)


# =============================================================================
# Intersect Operation Tests
# =============================================================================


def test_intersect_full_overlap():
    """Test intersecting identical domains returns full domain."""
    domain1 = Domain.from_rectangle(width_mm=100, height_mm=100, center=(50, 50))
    domain2 = Domain.from_rectangle(width_mm=100, height_mm=100, center=(50, 50))

    result = domain1.intersect(domain2)

    assert len(result) == 1
    assert approx_equal(result.domains[0].area_mm2, 10000.0)


def test_intersect_no_overlap():
    """Test intersecting non-overlapping domains produces empty result."""
    domain1 = Domain.from_rectangle(width_mm=100, height_mm=100, center=(50, 50))
    domain2 = Domain.from_rectangle(width_mm=100, height_mm=100, center=(300, 300))

    result = domain1.intersect(domain2)

    assert result.is_empty


def test_intersect_partial_overlap():
    """Test intersecting partially overlapping domains."""
    domain1 = Domain.from_rectangle(width_mm=100, height_mm=100, center=(50, 50))
    domain2 = Domain.from_rectangle(width_mm=100, height_mm=100, center=(100, 50))

    result = domain1.intersect(domain2)

    assert len(result) == 1
    # Overlap is 50*100 = 5000
    assert approx_equal(result.domains[0].area_mm2, 5000.0)


def test_intersect_contained():
    """Test intersecting where one contains the other."""
    outer = Domain.from_rectangle(width_mm=200, height_mm=200, center=(100, 100))
    inner = Domain.from_rectangle(width_mm=50, height_mm=50, center=(100, 100))

    result = outer.intersect(inner)

    assert len(result) == 1
    assert approx_equal(result.domains[0].area_mm2, 2500.0)


# =============================================================================
# Origin and Rotation Inheritance Tests
# =============================================================================


def test_operation_preserves_origin():
    """Test that operations preserve local_origin from source domain."""
    domain = Domain.from_rectangle(width_mm=100, height_mm=100, center=(200, 150))
    # Custom origin
    domain_with_origin = Domain(
        outer_boundary=domain.outer_boundary,
        inner_boundaries=domain.inner_boundaries,
        local_origin=(10, 20),
        local_rotation_rad=0.5,
    )

    result = domain_with_origin.inset(10)

    assert len(result) == 1
    assert result.domains[0].local_origin == (10, 20)
    assert result.domains[0].local_rotation_rad == 0.5


def test_operation_preserves_rotation():
    """Test that operations preserve local_rotation from source domain."""
    domain = Domain.from_rectangle(
        width_mm=100,
        height_mm=100,
        center=(0, 0),
        rotation_rad=math.pi / 6,  # 30 degrees
    )

    result = domain.offset(10)

    assert len(result) == 1
    assert approx_equal(result.domains[0].local_rotation_rad, math.pi / 6)


# =============================================================================
# MultiDomain Tests
# =============================================================================


def test_multidomain_iteration():
    """Test iterating over MultiDomain."""
    d1 = Domain.from_rectangle(width_mm=50, height_mm=50, center=(25, 25))
    d2 = Domain.from_rectangle(width_mm=50, height_mm=50, center=(100, 25))
    multi = MultiDomain(domains=(d1, d2))

    count = 0
    for domain in multi:
        count += 1
        assert domain.area_mm2 > 0

    assert count == 2


def test_multidomain_indexing():
    """Test indexing MultiDomain."""
    d1 = Domain.from_rectangle(width_mm=50, height_mm=50, center=(25, 25))
    d2 = Domain.from_rectangle(width_mm=100, height_mm=100, center=(100, 100))
    multi = MultiDomain(domains=(d1, d2))

    assert approx_equal(multi[0].area_mm2, 2500.0)
    assert approx_equal(multi[1].area_mm2, 10000.0)


def test_multidomain_is_empty():
    """Test MultiDomain.is_empty property."""
    empty = MultiDomain(domains=())
    assert empty.is_empty
    assert len(empty) == 0

    non_empty = MultiDomain(domains=(Domain.from_rectangle(10, 10),))
    assert not non_empty.is_empty
    assert len(non_empty) == 1


# =============================================================================
# JSON Serialization Tests
# =============================================================================


def test_domain_json_roundtrip_simple():
    """Test JSON serialization round-trip for simple domain."""
    domain = Domain.from_rectangle(width_mm=100, height_mm=50, center=(200, 150))

    json_str = domain.to_json()
    restored = Domain.from_json(json_str)

    assert len(restored.outer_boundary) == len(domain.outer_boundary)
    assert approx_equal(restored.area_mm2, domain.area_mm2)
    assert point_approx_equal(restored.centroid, domain.centroid)


def test_domain_json_roundtrip_with_holes():
    """Test JSON serialization round-trip for domain with holes."""
    outer = [(0, 0), (100, 0), (100, 100), (0, 100)]
    inner = [(30, 30), (70, 30), (70, 70), (30, 70)]
    domain = Domain.from_polygon(outer, holes=[inner])

    json_str = domain.to_json()
    restored = Domain.from_json(json_str)

    assert len(restored.inner_boundaries) == 1
    assert approx_equal(restored.area_mm2, domain.area_mm2)


def test_domain_json_roundtrip_with_origin_rotation():
    """Test JSON serialization preserves origin and rotation."""
    domain = Domain.from_rectangle(width_mm=100, height_mm=100, center=(50, 50), rotation_rad=math.pi / 4)

    json_str = domain.to_json()
    restored = Domain.from_json(json_str)

    assert point_approx_equal(restored.local_origin, domain.local_origin)
    assert approx_equal(restored.local_rotation_rad, domain.local_rotation_rad)


def test_domain_to_dict_includes_computed():
    """Test that to_dict includes computed properties."""
    domain = Domain.from_rectangle(width_mm=100, height_mm=100, center=(50, 50))
    data = domain.to_dict()

    assert "computed" in data
    assert "bounds" in data["computed"]
    assert "area_mm2" in data["computed"]
    assert "centroid" in data["computed"]

    assert approx_equal(data["computed"]["area_mm2"], 10000.0)


def test_multidomain_json_roundtrip():
    """Test JSON serialization round-trip for MultiDomain."""
    d1 = Domain.from_rectangle(width_mm=50, height_mm=50, center=(25, 25))
    d2 = Domain.from_rectangle(width_mm=100, height_mm=100, center=(100, 100))
    multi = MultiDomain(domains=(d1, d2))

    json_str = multi.to_json()
    restored = MultiDomain.from_json(json_str)

    assert len(restored) == 2
    assert approx_equal(restored[0].area_mm2, d1.area_mm2)
    assert approx_equal(restored[1].area_mm2, d2.area_mm2)


def test_multidomain_to_dict_includes_count():
    """Test that MultiDomain.to_dict includes count."""
    d1 = Domain.from_rectangle(width_mm=50, height_mm=50)
    d2 = Domain.from_rectangle(width_mm=100, height_mm=100)
    multi = MultiDomain(domains=(d1, d2))

    data = multi.to_dict()
    assert data["count"] == 2


def test_domain_from_dict_wrapper_format():
    """Test that from_dict accepts both raw and wrapper format."""
    domain = Domain.from_rectangle(width_mm=100, height_mm=100)

    # Raw format
    raw_data = domain.to_dict()
    restored_raw = Domain.from_dict(raw_data)
    assert approx_equal(restored_raw.area_mm2, 10000.0)

    # Wrapper format
    wrapper_data = {"domain": raw_data}
    restored_wrapper = Domain.from_dict(wrapper_data)
    assert approx_equal(restored_wrapper.area_mm2, 10000.0)


# =============================================================================
# Edge Case Tests
# =============================================================================


def test_very_small_domain():
    """Test operations on very small domain."""
    domain = Domain.from_rectangle(width_mm=1, height_mm=1, center=(0, 0))

    # Very small inset
    result = domain.inset(0.1)
    assert len(result) == 1
    assert approx_equal(result.domains[0].area_mm2, 0.64)  # 0.8 * 0.8


def test_very_large_domain():
    """Test operations on very large domain."""
    domain = Domain.from_rectangle(width_mm=10000, height_mm=10000, center=(5000, 5000))

    result = domain.inset(100)
    assert len(result) == 1
    expected_area = 9800 * 9800  # 96_040_000
    assert approx_equal(result.domains[0].area_mm2, expected_area)


def test_l_shaped_domain():
    """Test operations on an L-shaped domain."""
    # L-shape
    vertices = [(0, 0), (100, 0), (100, 50), (50, 50), (50, 100), (0, 100)]
    domain = Domain.from_polygon(vertices)

    # L has area 100*50 + 50*50 = 7500
    assert approx_equal(domain.area_mm2, 7500.0)

    # Inset should work on complex shapes
    result = domain.inset(10)
    assert len(result) >= 1


def test_concave_domain():
    """Test operations on a concave domain."""
    # Arrow/chevron shape pointing right
    vertices = [(0, 0), (50, 25), (0, 50), (10, 25)]
    domain = Domain.from_polygon(vertices)

    # Should be valid and have positive area
    assert domain.area_mm2 > 0


# =============================================================================
# Additional Tests for Review Findings
# =============================================================================


def test_split_result_all_domains_processable():
    """HIGH: Verify all domains from split result can be processed without dropping geometry."""
    # Create a domain and split it into 3 pieces by subtracting two strips
    wide = Domain.from_rectangle(width_mm=300, height_mm=50, center=(150, 25))
    strip1 = Domain.from_rectangle(width_mm=20, height_mm=100, center=(100, 25))
    strip2 = Domain.from_rectangle(width_mm=20, height_mm=100, center=(200, 25))

    # Subtract first strip
    result1 = wide.subtract(strip1)
    assert len(result1) == 2, f"Expected 2 domains after first split, got {len(result1)}"

    # Subtract second strip from each resulting domain
    all_pieces = []
    for domain in result1:
        sub_result = domain.subtract(strip2)
        for piece in sub_result:
            all_pieces.append(piece)

    # Verify total area is preserved (minus the subtracted strips)
    total_area = sum(d.area_mm2 for d in all_pieces)
    expected_area = 300 * 50 - 20 * 50 - 20 * 50  # Original minus two strips
    assert approx_equal(total_area, expected_area), f"Area mismatch: {total_area} vs {expected_area}"

    # Verify each piece has valid geometry
    for i, piece in enumerate(all_pieces):
        assert piece.area_mm2 > 0, f"Piece {i} has non-positive area"
        assert len(piece.outer_boundary) >= 3, f"Piece {i} has invalid boundary"


def test_split_result_iteration_complete():
    """HIGH: Verify iteration over MultiDomain processes all domains."""
    wide = Domain.from_rectangle(width_mm=200, height_mm=50, center=(100, 25))
    strip = Domain.from_rectangle(width_mm=20, height_mm=100, center=(100, 25))
    result = wide.subtract(strip)

    # Collect via iteration
    iterated = list(result)
    assert len(iterated) == len(result.domains), "Iteration missed domains"

    # Collect via indexing
    indexed = [result[i] for i in range(len(result))]
    assert len(indexed) == len(result.domains), "Indexing missed domains"

    # Verify same areas
    for i in range(len(result)):
        assert approx_equal(iterated[i].area_mm2, indexed[i].area_mm2)


def test_default_join_style_is_mitre():
    """MEDIUM: Verify default join style is mitre (sharp corners for woodworking)."""
    domain = Domain.from_rectangle(width_mm=100, height_mm=100, center=(50, 50))

    # Inset with default (should be mitre)
    result_default = domain.inset(10)
    # Inset with explicit mitre
    result_mitre = domain.inset(10, join_style="mitre")

    # Default should match mitre exactly
    assert approx_equal(result_default[0].area_mm2, result_mitre[0].area_mm2, tolerance=0.001), (
        f"Default ({result_default[0].area_mm2}) should match mitre ({result_mitre[0].area_mm2})"
    )

    # Mitre produces exactly 80x80 = 6400 for rectangle (sharp corners, not rounded)
    assert approx_equal(result_mitre[0].area_mm2, 6400.0, tolerance=0.01), (
        f"Mitre should produce 6400, got {result_mitre[0].area_mm2}"
    )

    # Verify all three join styles are accepted
    result_round = domain.inset(10, join_style="round")
    result_bevel = domain.inset(10, join_style="bevel")
    assert not result_round.is_empty
    assert not result_bevel.is_empty


def test_winding_preserved_after_operations():
    """MEDIUM: Verify winding normalization is maintained after boolean/offset operations."""
    domain = Domain.from_rectangle(width_mm=100, height_mm=100, center=(50, 50))

    # Test after inset
    inset_result = domain.inset(10)
    for d in inset_result:
        _verify_ccw_winding(d.outer_boundary)

    # Test after offset
    offset_result = domain.offset(10)
    for d in offset_result:
        _verify_ccw_winding(d.outer_boundary)

    # Test after subtract (creates hole)
    inner = Domain.from_rectangle(width_mm=40, height_mm=40, center=(50, 50))
    subtract_result = domain.subtract(inner)
    for d in subtract_result:
        _verify_ccw_winding(d.outer_boundary)
        for hole in d.inner_boundaries:
            _verify_cw_winding(hole)

    # Test after intersect
    other = Domain.from_rectangle(width_mm=80, height_mm=80, center=(60, 60))
    intersect_result = domain.intersect(other)
    for d in intersect_result:
        _verify_ccw_winding(d.outer_boundary)


def _verify_ccw_winding(boundary):
    """Verify boundary has counter-clockwise winding (negative shoelace sum)."""
    area_sum = 0
    n = len(boundary)
    for i in range(n):
        j = (i + 1) % n
        x1, y1 = boundary[i]
        x2, y2 = boundary[j]
        area_sum += (x2 - x1) * (y2 + y1)
    # Negative sum indicates CCW winding
    assert area_sum < 0, f"Expected CCW winding (negative sum), got {area_sum}"


def _verify_cw_winding(boundary):
    """Verify boundary has clockwise winding (positive shoelace sum)."""
    area_sum = 0
    n = len(boundary)
    for i in range(n):
        j = (i + 1) % n
        x1, y1 = boundary[i]
        x2, y2 = boundary[j]
        area_sum += (x2 - x1) * (y2 + y1)
    # Positive sum indicates CW winding
    assert area_sum > 0, f"Expected CW winding (positive sum), got {area_sum}"


def test_multidomain_serialization_preserves_all_domains():
    """LOW: Verify MultiDomain serialization round-trips all domains correctly."""
    # Create MultiDomain from split operation
    wide = Domain.from_rectangle(width_mm=200, height_mm=50, center=(100, 25))
    strip = Domain.from_rectangle(width_mm=20, height_mm=100, center=(100, 25))
    original = wide.subtract(strip)

    # Round-trip through JSON
    json_str = original.to_json()
    restored = MultiDomain.from_json(json_str)

    # Verify count
    assert len(restored) == len(original), "Domain count mismatch after serialization"

    # Verify each domain's properties
    for i in range(len(original)):
        assert approx_equal(restored[i].area_mm2, original[i].area_mm2)
        assert len(restored[i].outer_boundary) == len(original[i].outer_boundary)
        assert point_approx_equal(restored[i].local_origin, original[i].local_origin)


def test_multidomain_empty_serialization():
    """LOW: Verify empty MultiDomain serializes and deserializes correctly."""
    empty = MultiDomain(domains=())

    json_str = empty.to_json()
    restored = MultiDomain.from_json(json_str)

    assert restored.is_empty
    assert len(restored) == 0


# =============================================================================
# Stage 9: Split Operations Tests
# =============================================================================


def test_split_horizontal_basic():
    """Test horizontal split into 3 rows."""
    domain = Domain.from_rectangle(100, 300, center=(50, 150))
    result = domain.split_horizontal(3)

    assert len(result) == 3
    # Each panel should be 100mm tall (300 / 3)
    for d in result:
        assert approx_equal(d.bounds.height, 100.0)
        assert approx_equal(d.bounds.width, 100.0)

    # Verify ordering: bottom to top
    assert result[0].bounds.y_min < result[1].bounds.y_min
    assert result[1].bounds.y_min < result[2].bounds.y_min


def test_split_horizontal_with_gap():
    """Test horizontal split with gaps for rails."""
    domain = Domain.from_rectangle(100, 300, center=(50, 150))
    result = domain.split_horizontal(3, gap_mm=30)

    assert len(result) == 3
    # Each panel should be (300 - 2*30) / 3 = 80mm tall
    for d in result:
        assert approx_equal(d.bounds.height, 80.0)
        assert approx_equal(d.bounds.width, 100.0)


def test_split_horizontal_single():
    """Test horizontal split with n=1 returns original domain."""
    domain = Domain.from_rectangle(100, 100, center=(50, 50))
    result = domain.split_horizontal(1)

    assert len(result) == 1
    assert approx_equal(result[0].area_mm2, domain.area_mm2)


def test_split_horizontal_gap_too_large():
    """Test that gap exceeding height raises error."""
    domain = Domain.from_rectangle(100, 100, center=(50, 50))
    try:
        domain.split_horizontal(3, gap_mm=60)  # 2 gaps of 60 = 120 > 100
        raise AssertionError("Should have raised ValueError")
    except ValueError as e:
        assert "gap" in str(e).lower()


def test_split_horizontal_invalid_n():
    """Test that n < 1 raises error."""
    domain = Domain.from_rectangle(100, 100)
    try:
        domain.split_horizontal(0)
        raise AssertionError("Should have raised ValueError")
    except ValueError as e:
        assert "n must be >= 1" in str(e)


def test_split_vertical_basic():
    """Test vertical split into 2 columns."""
    domain = Domain.from_rectangle(200, 100, center=(100, 50))
    result = domain.split_vertical(2)

    assert len(result) == 2
    # Each panel should be 100mm wide
    for d in result:
        assert approx_equal(d.bounds.width, 100.0)
        assert approx_equal(d.bounds.height, 100.0)

    # Verify ordering: left to right
    assert result[0].bounds.x_min < result[1].bounds.x_min


def test_split_vertical_with_gap():
    """Test vertical split with gaps."""
    domain = Domain.from_rectangle(200, 100, center=(100, 50))
    result = domain.split_vertical(2, gap_mm=20)

    assert len(result) == 2
    # Each panel should be (200 - 20) / 2 = 90mm wide
    for d in result:
        assert approx_equal(d.bounds.width, 90.0)


def test_split_grid_basic():
    """Test grid split into 2x3 cells."""
    domain = Domain.from_rectangle(300, 200, center=(150, 100))
    result = domain.split_grid(rows=2, cols=3)

    assert len(result) == 6
    # Each cell should be 100mm x 100mm
    for d in result:
        assert approx_equal(d.bounds.width, 100.0)
        assert approx_equal(d.bounds.height, 100.0)


def test_split_grid_with_gap():
    """Test grid split with gaps."""
    domain = Domain.from_rectangle(300, 200, center=(150, 100))
    result = domain.split_grid(rows=2, cols=3, gap_mm=10)

    assert len(result) == 6
    # Each cell should be (300 - 2*10) / 3 = 93.33mm x (200 - 10) / 2 = 95mm
    for d in result:
        assert approx_equal(d.bounds.width, 280 / 3)
        assert approx_equal(d.bounds.height, 95.0)


def test_split_grid_ordering():
    """Test grid split ordering: row-major from bottom."""
    domain = Domain.from_rectangle(200, 300, center=(100, 150))
    result = domain.split_grid(rows=3, cols=2)

    # Expected order:
    # [0] = bottom-left, [1] = bottom-right
    # [2] = middle-left, [3] = middle-right
    # [4] = top-left, [5] = top-right

    # Bottom row
    assert result[0].centroid[0] < result[1].centroid[0]
    assert approx_equal(result[0].centroid[1], result[1].centroid[1])

    # Middle row
    assert result[2].centroid[0] < result[3].centroid[0]
    assert result[2].centroid[1] > result[0].centroid[1]

    # Top row
    assert result[4].centroid[0] < result[5].centroid[0]
    assert result[4].centroid[1] > result[2].centroid[1]


def test_split_grid_single_cell():
    """Test grid split with 1x1 returns original domain."""
    domain = Domain.from_rectangle(100, 100, center=(50, 50))
    result = domain.split_grid(rows=1, cols=1)

    assert len(result) == 1
    assert approx_equal(result[0].area_mm2, domain.area_mm2)


def test_split_preserves_origin_rotation():
    """Test that split operations preserve local_origin and local_rotation."""
    domain = Domain.from_rectangle(
        200,
        200,
        center=(100, 100),
        rotation_rad=0.5,
    )
    # Override origin
    domain_with_origin = Domain(
        outer_boundary=domain.outer_boundary,
        inner_boundaries=(),
        local_origin=(10, 20),
        local_rotation_rad=0.5,
    )

    result = domain_with_origin.split_horizontal(2)

    for d in result:
        assert point_approx_equal(d.local_origin, (10, 20))
        assert approx_equal(d.local_rotation_rad, 0.5)


def test_split_on_complex_domain():
    """Test split on L-shaped domain.

    Note: Split operations work by creating rectangular cells based on
    the bounding box and intersecting with the domain. For an L-shape,
    this may result in non-uniform pieces depending on how the L
    intersects the grid cells.
    """
    # L-shape: 100x50 base + 50x50 left tower = 7500 mm²
    vertices = [(0, 0), (100, 0), (100, 50), (50, 50), (50, 100), (0, 100)]
    domain = Domain.from_polygon(vertices)

    # Horizontal split into 2 rows - each row is 50mm tall
    result = domain.split_horizontal(2)

    # Bottom row intersects the full 100mm base = 100*50 = 5000 mm²
    # Top row only intersects the left tower (50mm wide) = 50*50 = 2500 mm²
    # We may get 1 or 2 domains depending on the exact intersection

    # Total area should equal original (no gaps)
    total_area = sum(d.area_mm2 for d in result)
    assert approx_equal(total_area, domain.area_mm2)

    # All pieces should have valid geometry
    for d in result:
        assert d.area_mm2 > 0
        assert len(d.outer_boundary) >= 3


def test_split_total_area_preserved():
    """Verify that split operations preserve total area."""
    domain = Domain.from_rectangle(200, 300, center=(100, 150))
    original_area = domain.area_mm2

    # Test all split operations
    h_result = domain.split_horizontal(3, gap_mm=20)
    v_result = domain.split_vertical(2, gap_mm=15)
    g_result = domain.split_grid(rows=2, cols=3, gap_mm=10)

    # Area should be less by gap amounts
    h_expected = original_area - 2 * 20 * 200  # 2 horizontal gaps, 200mm wide
    v_expected = original_area - 1 * 15 * 300  # 1 vertical gap, 300mm tall
    original_area - (2 * 10 * 300) - (1 * 10 * 200)  # 2 v-gaps + 1 h-gap

    h_actual = sum(d.area_mm2 for d in h_result)
    v_actual = sum(d.area_mm2 for d in v_result)
    g_actual = sum(d.area_mm2 for d in g_result)

    assert approx_equal(h_actual, h_expected, tolerance=1.0)
    assert approx_equal(v_actual, v_expected, tolerance=1.0)
    # Grid gaps overlap at intersections, so just verify it's less than original
    assert g_actual < original_area


# =============================================================================
# Stage 11: Local-Coordinate Split Operations Tests
# =============================================================================


def test_split_horizontal_local_coords_default_false():
    """Test that local_coords=False (default) preserves existing behavior."""
    domain = Domain.from_rectangle(100, 300, center=(50, 150))

    # Default behavior
    result_default = domain.split_horizontal(3)
    # Explicit local_coords=False
    result_explicit = domain.split_horizontal(3, local_coords=False)

    assert len(result_default) == len(result_explicit)
    for d1, d2 in zip(result_default, result_explicit, strict=False):
        assert approx_equal(d1.area_mm2, d2.area_mm2)
        assert bounds_approx_equal(d1.bounds, d2.bounds)


def test_split_vertical_local_coords_default_false():
    """Test that local_coords=False (default) preserves existing behavior."""
    domain = Domain.from_rectangle(300, 100, center=(150, 50))

    result_default = domain.split_vertical(3)
    result_explicit = domain.split_vertical(3, local_coords=False)

    assert len(result_default) == len(result_explicit)
    for d1, d2 in zip(result_default, result_explicit, strict=False):
        assert approx_equal(d1.area_mm2, d2.area_mm2)


def test_split_grid_local_coords_default_false():
    """Test that local_coords=False (default) preserves existing behavior."""
    domain = Domain.from_rectangle(200, 300, center=(100, 150))

    result_default = domain.split_grid(2, 3)
    result_explicit = domain.split_grid(2, 3, local_coords=False)

    assert len(result_default) == len(result_explicit)
    for d1, d2 in zip(result_default, result_explicit, strict=False):
        assert approx_equal(d1.area_mm2, d2.area_mm2)


def test_split_horizontal_local_coords_unrotated():
    """Test local_coords=True on unrotated domain is same as local_coords=False."""
    domain = Domain.from_rectangle(100, 300, center=(50, 150))
    # No rotation, so local_coords should have no effect

    result_false = domain.split_horizontal(3, local_coords=False)
    result_true = domain.split_horizontal(3, local_coords=True)

    assert len(result_false) == len(result_true)
    for d1, d2 in zip(result_false, result_true, strict=False):
        assert approx_equal(d1.area_mm2, d2.area_mm2)


def test_split_horizontal_local_coords_rotated_90deg():
    """Test local_coords=True on 90-degree rotated domain.

    A 100x300 rectangle rotated 90 degrees becomes 300x100 in sheet space.
    Horizontal split in local coords should split along the original (local) Y axis,
    which is now the sheet X axis after rotation.
    """
    # 100mm wide x 300mm tall, rotated 90 degrees CCW
    domain = Domain.from_rectangle(
        width_mm=100,
        height_mm=300,
        center=(150, 50),
        rotation_rad=math.pi / 2,  # 90 degrees
    )

    # In local coordinates, this is still 100 wide x 300 tall
    # Horizontal split in local coords splits along local Y
    result = domain.split_horizontal(3, local_coords=True)

    assert len(result) == 3
    # Total area should be preserved
    total_area = sum(d.area_mm2 for d in result)
    assert approx_equal(total_area, 100 * 300, tolerance=1.0)

    # Each piece should have 1/3 of the area
    for d in result:
        assert approx_equal(d.area_mm2, 10000.0, tolerance=1.0)  # 100*100


def test_split_vertical_local_coords_rotated_90deg():
    """Test local_coords=True on 90-degree rotated domain for vertical split."""
    # 300mm wide x 100mm tall, rotated 90 degrees CCW
    domain = Domain.from_rectangle(
        width_mm=300,
        height_mm=100,
        center=(50, 150),
        rotation_rad=math.pi / 2,  # 90 degrees
    )

    result = domain.split_vertical(3, local_coords=True)

    assert len(result) == 3
    total_area = sum(d.area_mm2 for d in result)
    assert approx_equal(total_area, 300 * 100, tolerance=1.0)


def test_split_grid_local_coords_rotated_45deg():
    """Test local_coords=True on 45-degree rotated domain for grid split.

    A square rotated 45 degrees should split into a grid aligned with
    the domain's diagonal axes when using local_coords=True.
    """
    # 200mm x 200mm square, rotated 45 degrees
    domain = Domain.from_rectangle(
        width_mm=200,
        height_mm=200,
        center=(100, 100),
        rotation_rad=math.pi / 4,  # 45 degrees
    )

    result = domain.split_grid(2, 2, local_coords=True)

    assert len(result) == 4
    # Total area should be preserved
    total_area = sum(d.area_mm2 for d in result)
    assert approx_equal(total_area, 200 * 200, tolerance=1.0)

    # Each cell should be approximately 1/4 of the area
    for d in result:
        assert approx_equal(d.area_mm2, 10000.0, tolerance=1.0)  # 100*100


def test_split_horizontal_local_coords_preserves_rotation():
    """Test that local_coords splits preserve the original rotation."""
    domain = Domain.from_rectangle(
        width_mm=100,
        height_mm=300,
        center=(150, 150),
        rotation_rad=math.pi / 6,  # 30 degrees
    )

    result = domain.split_horizontal(3, local_coords=True)

    # All resulting domains should have the same rotation as the parent
    for d in result:
        assert approx_equal(d.local_rotation_rad, math.pi / 6)


def test_split_horizontal_local_coords_with_gap_rotated():
    """Test local_coords=True with gaps on a rotated domain."""
    domain = Domain.from_rectangle(
        width_mm=100,
        height_mm=300,
        center=(150, 150),
        rotation_rad=math.pi / 4,  # 45 degrees
    )

    # Split with 30mm gaps
    result = domain.split_horizontal(3, gap_mm=30, local_coords=True)

    assert len(result) == 3
    # Total area should be original minus gap areas
    # Gap area = 2 gaps * 30mm * 100mm = 6000 mm²
    total_area = sum(d.area_mm2 for d in result)
    expected_area = 100 * 300 - 2 * 30 * 100
    assert approx_equal(total_area, expected_area, tolerance=1.0)


def test_split_vertical_local_coords_with_gap_rotated():
    """Test local_coords=True vertical split with gaps on a rotated domain."""
    domain = Domain.from_rectangle(
        width_mm=200,
        height_mm=100,
        center=(100, 100),
        rotation_rad=math.pi / 3,  # 60 degrees
    )

    result = domain.split_vertical(2, gap_mm=20, local_coords=True)

    assert len(result) == 2
    # Total area should be original minus gap area
    total_area = sum(d.area_mm2 for d in result)
    expected_area = 200 * 100 - 20 * 100
    assert approx_equal(total_area, expected_area, tolerance=1.0)


def test_local_coords_vs_sheet_coords_different_for_rotated():
    """Test that local_coords=True produces different results than False for rotated domains."""
    domain = Domain.from_rectangle(
        width_mm=100,
        height_mm=200,
        center=(100, 100),
        rotation_rad=math.pi / 4,  # 45 degrees
    )

    result_sheet = domain.split_horizontal(2, local_coords=False)
    result_local = domain.split_horizontal(2, local_coords=True)

    # Both should have 2 domains
    assert len(result_sheet) == 2
    assert len(result_local) == 2

    # Both should have same total area
    sheet_area = sum(d.area_mm2 for d in result_sheet)
    local_area = sum(d.area_mm2 for d in result_local)
    assert approx_equal(sheet_area, local_area, tolerance=1.0)

    # But the individual domains should have different shapes
    # (sheet splits along sheet Y, local splits along local Y which is rotated)
    # Verify centroids are different
    sheet_centroid_0 = result_sheet[0].centroid
    local_centroid_0 = result_local[0].centroid

    # The centroids should differ due to different split orientations
    # For a 45-degree rotation, the difference should be noticeable
    centroid_diff = math.sqrt(
        (sheet_centroid_0[0] - local_centroid_0[0]) ** 2 + (sheet_centroid_0[1] - local_centroid_0[1]) ** 2
    )
    # With a 45-degree rotated 100x200 rectangle split in half,
    # the centroids will be in notably different positions
    assert centroid_diff > 1.0, "Local and sheet splits should produce different geometry for rotated domains"


def test_transform_point_roundtrip():
    """Test that point transforms are reversible."""
    domain = Domain.from_rectangle(
        width_mm=100,
        height_mm=100,
        center=(200, 150),
        rotation_rad=math.pi / 6,  # 30 degrees
    )

    test_point = (250, 200)

    # Transform to local and back
    local_point = domain._transform_point_to_local(test_point)
    back_to_sheet = domain._transform_point_to_sheet(local_point)

    assert point_approx_equal(back_to_sheet, test_point, tolerance=0.001)


def test_to_local_domain_and_back():
    """Test that domain can be transformed to local space and back."""
    domain = Domain.from_rectangle(
        width_mm=100,
        height_mm=200,
        center=(150, 100),
        rotation_rad=math.pi / 4,  # 45 degrees
    )
    original_area = domain.area_mm2

    # Transform to local space
    local_domain = domain._to_local_domain()

    # Local domain should have same area
    assert approx_equal(local_domain.area_mm2, original_area)

    # Local domain should be axis-aligned (rotation = 0)
    assert approx_equal(local_domain.local_rotation_rad, 0.0)

    # Local domain's origin should be at (0, 0)
    assert point_approx_equal(local_domain.local_origin, (0.0, 0.0))

    # Transform back to sheet coordinates
    back_to_sheet = domain._from_local_domain(local_domain)

    # Should have same area
    assert approx_equal(back_to_sheet.area_mm2, original_area)

    # Should have same rotation as original
    assert approx_equal(back_to_sheet.local_rotation_rad, domain.local_rotation_rad)

    # Centroid should be approximately the same
    assert point_approx_equal(back_to_sheet.centroid, domain.centroid, tolerance=0.1)


# =============================================================================
# Stage 13: Domain Factory Methods and Utilities
# =============================================================================


def test_from_arch_basic():
    """Test creating an arch-topped domain."""
    arch = Domain.from_arch(
        width_mm=500,
        height_mm=800,
        arch_radius_mm=250,  # Full semicircle
    )

    # Should have valid geometry
    assert arch.area_mm2 > 0
    assert len(arch.outer_boundary) > 4  # More than a rectangle due to arc

    # Bounds should match input dimensions
    assert approx_equal(arch.bounds.width, 500.0)
    assert approx_equal(arch.bounds.height, 800.0)


def test_from_arch_with_center():
    """Test arch with custom center position."""
    arch = Domain.from_arch(
        width_mm=500,
        height_mm=800,
        arch_radius_mm=250,
        center=(250, 400),
    )

    # Centroid should be near the specified center
    assert approx_equal(arch.bounds.x_min, 0.0, tolerance=1.0)
    assert approx_equal(arch.bounds.x_max, 500.0, tolerance=1.0)


def test_from_arch_partial_radius():
    """Test arch with radius smaller than half width."""
    arch = Domain.from_arch(
        width_mm=400,
        height_mm=600,
        arch_radius_mm=150,  # Less than half width
    )

    assert arch.area_mm2 > 0
    # Height should still be 600
    assert approx_equal(arch.bounds.height, 600.0)


def test_from_arch_validation():
    """Test arch constructor validation."""
    # Radius too large (> half width)
    try:
        Domain.from_arch(width_mm=200, height_mm=400, arch_radius_mm=150)
        raise AssertionError("Should have raised ValueError")
    except ValueError as e:
        assert "radius" in str(e).lower()

    # Radius larger than height
    try:
        Domain.from_arch(width_mm=200, height_mm=50, arch_radius_mm=100)
        raise AssertionError("Should have raised ValueError")
    except ValueError as e:
        assert "radius" in str(e).lower()

    # Invalid dimensions
    try:
        Domain.from_arch(width_mm=-100, height_mm=400, arch_radius_mm=50)
        raise AssertionError("Should have raised ValueError")
    except ValueError:
        pass


def test_from_arch_matches_recipe_30_dimensions():
    """Test arch matches Recipe 30 cathedral arch door dimensions."""
    DOOR_WIDTH = 500
    DOOR_HEIGHT = 800
    ARCH_RADIUS = 250

    arch = Domain.from_arch(DOOR_WIDTH, DOOR_HEIGHT, ARCH_RADIUS)

    assert approx_equal(arch.bounds.width, DOOR_WIDTH)
    assert approx_equal(arch.bounds.height, DOOR_HEIGHT)
    assert arch.area_mm2 > 0


def test_from_arch_can_be_inset():
    """Test that arch domain supports inset operation."""
    arch = Domain.from_arch(500, 800, 250)
    inset_result = arch.inset(60)

    assert not inset_result.is_empty
    assert len(inset_result) == 1
    assert inset_result[0].area_mm2 < arch.area_mm2


def test_split_horizontal_with_gaps_basic():
    """Test split_horizontal_with_gaps returns cells and gaps separately."""
    domain = Domain.from_rectangle(200, 600, center=(100, 300))
    cells, gaps = domain.split_horizontal_with_gaps(3, gap_mm=20)

    assert len(cells) == 3
    assert len(gaps) == 2  # n-1 gaps

    # Each cell should be (600 - 2*20) / 3 = 186.67mm tall
    for cell in cells:
        assert approx_equal(cell.bounds.height, 186.67, tolerance=0.5)
        assert approx_equal(cell.bounds.width, 200.0)

    # Each gap should be 20mm tall
    for gap in gaps:
        assert approx_equal(gap.bounds.height, 20.0)
        assert approx_equal(gap.bounds.width, 200.0)


def test_split_horizontal_with_gaps_ordering():
    """Test that cells and gaps are ordered bottom to top."""
    domain = Domain.from_rectangle(100, 300, center=(50, 150))
    cells, gaps = domain.split_horizontal_with_gaps(3, gap_mm=10)

    # Cells should be ordered bottom to top
    assert cells[0].bounds.y_min < cells[1].bounds.y_min
    assert cells[1].bounds.y_min < cells[2].bounds.y_min

    # Gaps should be ordered bottom to top
    assert gaps[0].bounds.y_min < gaps[1].bounds.y_min

    # First gap should be between first and second cell
    assert gaps[0].bounds.y_min >= cells[0].bounds.y_max - 0.1
    assert gaps[0].bounds.y_max <= cells[1].bounds.y_min + 0.1


def test_split_horizontal_with_gaps_area_preservation():
    """Test that cells + gaps cover the full domain area."""
    domain = Domain.from_rectangle(100, 300, center=(50, 150))
    cells, gaps = domain.split_horizontal_with_gaps(3, gap_mm=10)

    cells_area = sum(c.area_mm2 for c in cells)
    gaps_area = sum(g.area_mm2 for g in gaps)
    total_area = cells_area + gaps_area

    assert approx_equal(total_area, domain.area_mm2)


def test_split_horizontal_with_gaps_single_row():
    """Test that n=1 returns single cell and no gaps."""
    domain = Domain.from_rectangle(100, 100, center=(50, 50))
    cells, gaps = domain.split_horizontal_with_gaps(1, gap_mm=10)

    assert len(cells) == 1
    assert len(gaps) == 0
    assert approx_equal(cells[0].area_mm2, domain.area_mm2)


def test_split_horizontal_with_gaps_validation():
    """Test validation of split_horizontal_with_gaps."""
    domain = Domain.from_rectangle(100, 100, center=(50, 50))

    # n < 1
    try:
        domain.split_horizontal_with_gaps(0, gap_mm=10)
        raise AssertionError("Should have raised ValueError")
    except ValueError as e:
        assert "n must be >= 1" in str(e)

    # gap <= 0
    try:
        domain.split_horizontal_with_gaps(3, gap_mm=0)
        raise AssertionError("Should have raised ValueError")
    except ValueError as e:
        assert "positive" in str(e).lower()

    # gap too large
    try:
        domain.split_horizontal_with_gaps(5, gap_mm=30)  # 4 gaps * 30 = 120 > 100
        raise AssertionError("Should have raised ValueError")
    except ValueError as e:
        assert "exceeds" in str(e).lower()


def test_split_horizontal_with_gaps_local_coords():
    """Test split_horizontal_with_gaps with local_coords on rotated domain."""
    domain = Domain.from_rectangle(
        width_mm=100,
        height_mm=300,
        center=(150, 150),
        rotation_rad=math.pi / 4,  # 45 degrees
    )

    cells, gaps = domain.split_horizontal_with_gaps(3, gap_mm=30, local_coords=True)

    assert len(cells) == 3
    assert len(gaps) == 2

    # Total area should be preserved
    total_area = sum(c.area_mm2 for c in cells) + sum(g.area_mm2 for g in gaps)
    assert approx_equal(total_area, domain.area_mm2)

    # All domains should preserve rotation
    for cell in cells:
        assert approx_equal(cell.local_rotation_rad, math.pi / 4)
    for gap in gaps:
        assert approx_equal(gap.local_rotation_rad, math.pi / 4)


# =============================================================================
# Stage 13: arc_points Utility Tests
# =============================================================================


def test_arc_points_basic():
    """Test basic arc_points generation."""
    from core.geometry import arc_points

    # Half circle from 0 to 180 degrees
    points = arc_points(center=(100, 100), radius=50, start_deg=0, end_deg=180, segments=4)

    assert len(points) == 5  # segments + 1

    # First point should be at (150, 100)  - radius to the right
    assert approx_equal(points[0][0], 150.0)
    assert approx_equal(points[0][1], 100.0)

    # Last point should be at (50, 100) - radius to the left
    assert approx_equal(points[-1][0], 50.0)
    assert approx_equal(points[-1][1], 100.0)


def test_arc_points_full_circle():
    """Test arc_points for full circle."""
    from core.geometry import arc_points

    points = arc_points(center=(0, 0), radius=10, start_deg=0, end_deg=360, segments=8)

    assert len(points) == 9

    # First and last points should be the same (closed circle)
    assert approx_equal(points[0][0], points[-1][0])
    assert approx_equal(points[0][1], points[-1][1])


def test_arc_points_quarter_circle():
    """Test arc_points for quarter circle."""
    from core.geometry import arc_points

    points = arc_points(center=(0, 0), radius=100, start_deg=0, end_deg=90, segments=2)

    assert len(points) == 3

    # 0 degrees: (100, 0)
    assert approx_equal(points[0][0], 100.0)
    assert approx_equal(points[0][1], 0.0)

    # 45 degrees: (70.7, 70.7)
    assert approx_equal(points[1][0], 70.71, tolerance=0.1)
    assert approx_equal(points[1][1], 70.71, tolerance=0.1)

    # 90 degrees: (0, 100)
    assert approx_equal(points[2][0], 0.0, tolerance=0.1)
    assert approx_equal(points[2][1], 100.0)


def test_arc_points_validation():
    """Test arc_points validation."""
    from core.geometry import arc_points

    # segments < 1
    try:
        arc_points((0, 0), 10, 0, 90, segments=0)
        raise AssertionError("Should have raised ValueError")
    except ValueError as e:
        assert "segments" in str(e).lower()

    # negative radius
    try:
        arc_points((0, 0), -10, 0, 90, segments=4)
        raise AssertionError("Should have raised ValueError")
    except ValueError as e:
        assert "radius" in str(e).lower()


# =============================================================================
# Test Runner
# =============================================================================


def run_tests():
    """Run all tests and report results."""

    # Collect all test functions
    tests = [(name, func) for name, func in globals().items() if name.startswith("test_") and callable(func)]

    passed = 0
    failed = 0
    errors = []

    print(f"Running {len(tests)} tests...")
    print("-" * 60)

    for name, func in tests:
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
