"""Comprehensive tests for coordinate transforms between domain-local and sheet-space.

This test module covers Stage 2 of the domain/generator system:
- Identity transform (zero rotation, origin at 0,0)
- Translation only
- Rotation only
- Combined rotation and translation
- Round-trip preservation
- Batch transform efficiency
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from domains import Domain
from domains.transforms import (
    local_to_sheet,
    sheet_to_local,
    local_to_sheet_batch,
    sheet_to_local_batch,
    transform_boundary,
    compose_transforms,
    get_rotation_between,
    get_translation_between,
)


# =============================================================================
# Test Helpers
# =============================================================================

def approx_equal(a: float, b: float, tolerance: float = 1e-9) -> bool:
    """Check if two floats are approximately equal within tolerance."""
    return abs(a - b) <= tolerance


def point_approx_equal(
    p1: tuple[float, float],
    p2: tuple[float, float],
    tolerance: float = 1e-9,
) -> bool:
    """Check if two points are approximately equal."""
    return approx_equal(p1[0], p2[0], tolerance) and approx_equal(p1[1], p2[1], tolerance)


# =============================================================================
# Identity Transform Tests (no rotation, origin at 0,0)
# =============================================================================

def test_identity_transform_local_to_sheet():
    """Test local_to_sheet with identity transform (no rotation, origin at 0,0)."""
    domain = Domain.from_rectangle(width_mm=100, height_mm=100, center=(0, 0))

    # Local origin should map to sheet origin
    result = local_to_sheet((0, 0), domain)
    assert point_approx_equal(result, (0, 0)), f"Expected (0, 0), got {result}"

    # Positive x should map to positive x
    result = local_to_sheet((10, 0), domain)
    assert point_approx_equal(result, (10, 0)), f"Expected (10, 0), got {result}"

    # Positive y should map to positive y
    result = local_to_sheet((0, 10), domain)
    assert point_approx_equal(result, (0, 10)), f"Expected (0, 10), got {result}"

    # Arbitrary point
    result = local_to_sheet((25, 35), domain)
    assert point_approx_equal(result, (25, 35)), f"Expected (25, 35), got {result}"


def test_identity_transform_sheet_to_local():
    """Test sheet_to_local with identity transform."""
    domain = Domain.from_rectangle(width_mm=100, height_mm=100, center=(0, 0))

    result = sheet_to_local((0, 0), domain)
    assert point_approx_equal(result, (0, 0)), f"Expected (0, 0), got {result}"

    result = sheet_to_local((25, 35), domain)
    assert point_approx_equal(result, (25, 35)), f"Expected (25, 35), got {result}"


# =============================================================================
# Translation Only Tests
# =============================================================================

def test_translation_only_local_to_sheet():
    """Test local_to_sheet with translation only (no rotation)."""
    domain = Domain.from_rectangle(width_mm=100, height_mm=100, center=(200, 150))

    # Local origin should map to domain center
    result = local_to_sheet((0, 0), domain)
    assert point_approx_equal(result, (200, 150)), f"Expected (200, 150), got {result}"

    # Offset from local origin
    result = local_to_sheet((10, 20), domain)
    assert point_approx_equal(result, (210, 170)), f"Expected (210, 170), got {result}"

    # Negative offset
    result = local_to_sheet((-50, -25), domain)
    assert point_approx_equal(result, (150, 125)), f"Expected (150, 125), got {result}"


def test_translation_only_sheet_to_local():
    """Test sheet_to_local with translation only."""
    domain = Domain.from_rectangle(width_mm=100, height_mm=100, center=(200, 150))

    # Domain center should map to local origin
    result = sheet_to_local((200, 150), domain)
    assert point_approx_equal(result, (0, 0)), f"Expected (0, 0), got {result}"

    # Sheet origin
    result = sheet_to_local((0, 0), domain)
    assert point_approx_equal(result, (-200, -150)), f"Expected (-200, -150), got {result}"

    # Arbitrary sheet point
    result = sheet_to_local((250, 175), domain)
    assert point_approx_equal(result, (50, 25)), f"Expected (50, 25), got {result}"


# =============================================================================
# Rotation Only Tests
# =============================================================================

def test_rotation_is_counter_clockwise_positive():
    """Verify rotation direction: positive angles rotate counter-clockwise.

    This is a CONTRACT TEST - the design document specifies CCW-positive rotation.
    A sign error here would mirror patterns in woodworking, causing physical defects.

    Mathematical convention: +90° (π/2 radians) rotates:
    - +X axis → +Y axis direction
    - +Y axis → -X axis direction

    Visual: Looking down at sheet (Z up), positive rotation goes left/CCW.
    """
    domain = Domain.from_rectangle(
        width_mm=100, height_mm=100,
        center=(0, 0),
        rotation_rad=math.pi / 2  # +90 degrees
    )

    # Point on +X axis should rotate to +Y axis (CCW)
    result = local_to_sheet((10, 0), domain)
    assert result[0] < 0.001, f"X should be ~0 after +90° CCW, got {result[0]}"
    assert result[1] > 9.99, f"Y should be ~10 after +90° CCW, got {result[1]}"

    # Point on +Y axis should rotate to -X axis (CCW)
    result = local_to_sheet((0, 10), domain)
    assert result[0] < -9.99, f"X should be ~-10 after +90° CCW, got {result[0]}"
    assert result[1] < 0.001, f"Y should be ~0 after +90° CCW, got {result[1]}"

    # Verify inverse: negative rotation is clockwise
    domain_cw = Domain.from_rectangle(
        width_mm=100, height_mm=100,
        center=(0, 0),
        rotation_rad=-math.pi / 2  # -90 degrees (CW)
    )

    # Point on +X axis should rotate to -Y axis (CW)
    result = local_to_sheet((10, 0), domain_cw)
    assert result[0] < 0.001, f"X should be ~0 after -90° CW, got {result[0]}"
    assert result[1] < -9.99, f"Y should be ~-10 after -90° CW, got {result[1]}"




def test_rotation_90_degrees():
    """Test transform with 90 degree rotation."""
    domain = Domain.from_rectangle(
        width_mm=100, height_mm=100,
        center=(0, 0),
        rotation_rad=math.pi / 2  # 90 degrees CCW
    )

    # Local +X should map to sheet +Y
    result = local_to_sheet((10, 0), domain)
    assert point_approx_equal(result, (0, 10)), f"Expected (0, 10), got {result}"

    # Local +Y should map to sheet -X
    result = local_to_sheet((0, 10), domain)
    assert point_approx_equal(result, (-10, 0)), f"Expected (-10, 0), got {result}"


def test_rotation_45_degrees():
    """Test transform with 45 degree rotation."""
    domain = Domain.from_rectangle(
        width_mm=100, height_mm=100,
        center=(0, 0),
        rotation_rad=math.pi / 4  # 45 degrees CCW
    )

    # Local (10, 0) should rotate 45 degrees
    result = local_to_sheet((10, 0), domain)
    expected_x = 10 * math.cos(math.pi / 4)
    expected_y = 10 * math.sin(math.pi / 4)
    assert point_approx_equal(result, (expected_x, expected_y)), \
        f"Expected ({expected_x}, {expected_y}), got {result}"


def test_rotation_180_degrees():
    """Test transform with 180 degree rotation."""
    domain = Domain.from_rectangle(
        width_mm=100, height_mm=100,
        center=(0, 0),
        rotation_rad=math.pi  # 180 degrees
    )

    # Local +X should map to sheet -X
    result = local_to_sheet((10, 0), domain)
    assert point_approx_equal(result, (-10, 0)), f"Expected (-10, 0), got {result}"

    # Local +Y should map to sheet -Y
    result = local_to_sheet((0, 10), domain)
    assert point_approx_equal(result, (0, -10)), f"Expected (0, -10), got {result}"


def test_rotation_negative_angle():
    """Test transform with negative (clockwise) rotation."""
    domain = Domain.from_rectangle(
        width_mm=100, height_mm=100,
        center=(0, 0),
        rotation_rad=-math.pi / 2  # 90 degrees CW
    )

    # Local +X should map to sheet -Y
    result = local_to_sheet((10, 0), domain)
    assert point_approx_equal(result, (0, -10)), f"Expected (0, -10), got {result}"


def test_rotation_inverse():
    """Test that sheet_to_local correctly inverts rotation."""
    domain = Domain.from_rectangle(
        width_mm=100, height_mm=100,
        center=(0, 0),
        rotation_rad=math.pi / 4
    )

    # Transform to sheet then back should give original
    original = (10, 5)
    sheet_pt = local_to_sheet(original, domain)
    back = sheet_to_local(sheet_pt, domain)
    assert point_approx_equal(back, original), f"Expected {original}, got {back}"


# =============================================================================
# Combined Rotation and Translation Tests
# =============================================================================

def test_combined_transform():
    """Test transform with both rotation and translation."""
    domain = Domain.from_rectangle(
        width_mm=100, height_mm=100,
        center=(200, 150),
        rotation_rad=math.pi / 2  # 90 degrees CCW
    )

    # Local origin maps to domain center
    result = local_to_sheet((0, 0), domain)
    assert point_approx_equal(result, (200, 150)), f"Expected (200, 150), got {result}"

    # Local +X (after rotation) maps to sheet +Y direction from center
    result = local_to_sheet((10, 0), domain)
    assert point_approx_equal(result, (200, 160)), f"Expected (200, 160), got {result}"

    # Local +Y (after rotation) maps to sheet -X direction from center
    result = local_to_sheet((0, 10), domain)
    assert point_approx_equal(result, (190, 150)), f"Expected (190, 150), got {result}"


def test_combined_transform_arbitrary():
    """Test combined transform with arbitrary rotation angle."""
    angle = math.pi / 6  # 30 degrees
    center = (100, 80)
    domain = Domain.from_rectangle(
        width_mm=100, height_mm=100,
        center=center,
        rotation_rad=angle
    )

    # Local point (10, 5)
    lx, ly = 10, 5
    cos_a = math.cos(angle)
    sin_a = math.sin(angle)

    # Expected: rotate then translate
    expected_x = center[0] + lx * cos_a - ly * sin_a
    expected_y = center[1] + lx * sin_a + ly * cos_a

    result = local_to_sheet((lx, ly), domain)
    assert point_approx_equal(result, (expected_x, expected_y)), \
        f"Expected ({expected_x}, {expected_y}), got {result}"


# =============================================================================
# Round-Trip Preservation Tests
# =============================================================================

def test_roundtrip_no_rotation():
    """Test round-trip preserves coordinates without rotation."""
    domain = Domain.from_rectangle(width_mm=100, height_mm=100, center=(200, 150))

    original = (25.5, -10.3)
    sheet_pt = local_to_sheet(original, domain)
    back = sheet_to_local(sheet_pt, domain)

    assert point_approx_equal(back, original, tolerance=1e-10), \
        f"Round-trip failed: {original} -> {sheet_pt} -> {back}"


def test_roundtrip_with_rotation():
    """Test round-trip preserves coordinates with rotation."""
    domain = Domain.from_rectangle(
        width_mm=100, height_mm=100,
        center=(200, 150),
        rotation_rad=math.pi / 3  # 60 degrees
    )

    original = (25.5, -10.3)
    sheet_pt = local_to_sheet(original, domain)
    back = sheet_to_local(sheet_pt, domain)

    assert point_approx_equal(back, original, tolerance=1e-10), \
        f"Round-trip failed: {original} -> {sheet_pt} -> {back}"


def test_roundtrip_multiple_points():
    """Test round-trip with multiple points."""
    domain = Domain.from_rectangle(
        width_mm=100, height_mm=100,
        center=(100, 100),
        rotation_rad=math.pi / 4
    )

    test_points = [
        (0, 0),
        (50, 0),
        (0, 50),
        (-25, 30),
        (100, -50),
        (0.001, 0.001),  # Very small
        (1000, 1000),    # Large
    ]

    for original in test_points:
        sheet_pt = local_to_sheet(original, domain)
        back = sheet_to_local(sheet_pt, domain)
        assert point_approx_equal(back, original, tolerance=1e-9), \
            f"Round-trip failed for {original}: got {back}"


def test_roundtrip_sheet_first():
    """Test round-trip starting from sheet coordinates."""
    domain = Domain.from_rectangle(
        width_mm=100, height_mm=100,
        center=(200, 150),
        rotation_rad=math.pi / 5
    )

    original = (250, 175)
    local_pt = sheet_to_local(original, domain)
    back = local_to_sheet(local_pt, domain)

    assert point_approx_equal(back, original, tolerance=1e-10), \
        f"Round-trip failed: {original} -> {local_pt} -> {back}"


# =============================================================================
# Batch Transform Tests
# =============================================================================

def test_batch_local_to_sheet():
    """Test batch transformation from local to sheet."""
    domain = Domain.from_rectangle(width_mm=100, height_mm=100, center=(200, 150))

    points = [(0, 0), (10, 0), (0, 10), (10, 10)]
    results = local_to_sheet_batch(points, domain)

    assert len(results) == 4
    assert point_approx_equal(results[0], (200, 150))
    assert point_approx_equal(results[1], (210, 150))
    assert point_approx_equal(results[2], (200, 160))
    assert point_approx_equal(results[3], (210, 160))


def test_batch_sheet_to_local():
    """Test batch transformation from sheet to local."""
    domain = Domain.from_rectangle(width_mm=100, height_mm=100, center=(200, 150))

    points = [(200, 150), (210, 150), (200, 160), (210, 160)]
    results = sheet_to_local_batch(points, domain)

    assert len(results) == 4
    assert point_approx_equal(results[0], (0, 0))
    assert point_approx_equal(results[1], (10, 0))
    assert point_approx_equal(results[2], (0, 10))
    assert point_approx_equal(results[3], (10, 10))


def test_batch_empty_list():
    """Test batch transform with empty list."""
    domain = Domain.from_rectangle(width_mm=100, height_mm=100, center=(200, 150))

    results = local_to_sheet_batch([], domain)
    assert results == []

    results = sheet_to_local_batch([], domain)
    assert results == []


def test_batch_with_rotation():
    """Test batch transform with rotation."""
    domain = Domain.from_rectangle(
        width_mm=100, height_mm=100,
        center=(0, 0),
        rotation_rad=math.pi / 2  # 90 degrees
    )

    points = [(10, 0), (0, 10)]
    results = local_to_sheet_batch(points, domain)

    # (10, 0) rotated 90 CCW -> (0, 10)
    assert point_approx_equal(results[0], (0, 10))
    # (0, 10) rotated 90 CCW -> (-10, 0)
    assert point_approx_equal(results[1], (-10, 0))


def test_batch_matches_individual():
    """Test that batch results match individual transforms."""
    domain = Domain.from_rectangle(
        width_mm=100, height_mm=100,
        center=(200, 150),
        rotation_rad=math.pi / 7
    )

    points = [(0, 0), (10, 20), (-5, 15), (100, -50)]

    batch_results = local_to_sheet_batch(points, domain)
    individual_results = [local_to_sheet(p, domain) for p in points]

    for batch, individual in zip(batch_results, individual_results):
        assert point_approx_equal(batch, individual), \
            f"Batch {batch} != individual {individual}"


def test_batch_tuple_input():
    """Test that batch accepts tuple input."""
    domain = Domain.from_rectangle(width_mm=100, height_mm=100, center=(0, 0))

    # Input as tuple of tuples
    points = ((10, 0), (0, 10))
    results = local_to_sheet_batch(points, domain)

    assert len(results) == 2
    assert point_approx_equal(results[0], (10, 0))


# =============================================================================
# Transform Boundary Tests
# =============================================================================

def test_transform_boundary_to_sheet():
    """Test transforming a complete boundary to sheet space."""
    domain = Domain.from_rectangle(width_mm=100, height_mm=100, center=(200, 150))

    # Square boundary centered at local origin
    local_boundary = ((-10, -10), (10, -10), (10, 10), (-10, 10))
    sheet_boundary = transform_boundary(local_boundary, domain, to_sheet=True)

    assert len(sheet_boundary) == 4
    assert point_approx_equal(sheet_boundary[0], (190, 140))
    assert point_approx_equal(sheet_boundary[1], (210, 140))
    assert point_approx_equal(sheet_boundary[2], (210, 160))
    assert point_approx_equal(sheet_boundary[3], (190, 160))


def test_transform_boundary_to_local():
    """Test transforming a boundary to local space."""
    domain = Domain.from_rectangle(width_mm=100, height_mm=100, center=(200, 150))

    sheet_boundary = ((190, 140), (210, 140), (210, 160), (190, 160))
    local_boundary = transform_boundary(sheet_boundary, domain, to_sheet=False)

    assert len(local_boundary) == 4
    assert point_approx_equal(local_boundary[0], (-10, -10))
    assert point_approx_equal(local_boundary[1], (10, -10))
    assert point_approx_equal(local_boundary[2], (10, 10))
    assert point_approx_equal(local_boundary[3], (-10, 10))


# =============================================================================
# Compose Transforms Tests
# =============================================================================

def test_compose_same_domain():
    """Test composing transforms with the same domain gives identity."""
    domain = Domain.from_rectangle(
        width_mm=100, height_mm=100,
        center=(200, 150),
        rotation_rad=0.5
    )

    original = (10, 20)
    result = compose_transforms(original, domain, domain)

    assert point_approx_equal(result, original), \
        f"Expected {original}, got {result}"


def test_compose_different_domains():
    """Test composing transforms between different domains."""
    domain1 = Domain.from_rectangle(width_mm=100, height_mm=100, center=(100, 100))
    domain2 = Domain.from_rectangle(width_mm=100, height_mm=100, center=(200, 150))

    # Point at domain1's origin
    result = compose_transforms((0, 0), domain1, domain2)

    # (0, 0) in domain1 local = (100, 100) in sheet
    # (100, 100) in sheet = (-100, -50) in domain2 local
    assert point_approx_equal(result, (-100, -50)), \
        f"Expected (-100, -50), got {result}"


def test_compose_with_rotation():
    """Test composing transforms with different rotations."""
    domain1 = Domain.from_rectangle(
        width_mm=100, height_mm=100,
        center=(0, 0),
        rotation_rad=0
    )
    domain2 = Domain.from_rectangle(
        width_mm=100, height_mm=100,
        center=(0, 0),
        rotation_rad=math.pi / 2  # 90 degrees
    )

    # (10, 0) in domain1 = (10, 0) in sheet (no rotation)
    # (10, 0) in sheet = (0, -10) in domain2 (rotated 90 CW from sheet to local)
    result = compose_transforms((10, 0), domain1, domain2)
    assert point_approx_equal(result, (0, -10)), \
        f"Expected (0, -10), got {result}"


# =============================================================================
# Utility Function Tests
# =============================================================================

def test_get_rotation_between():
    """Test getting rotation difference between domains."""
    domain1 = Domain.from_rectangle(
        width_mm=100, height_mm=100,
        center=(0, 0),
        rotation_rad=0.5
    )
    domain2 = Domain.from_rectangle(
        width_mm=100, height_mm=100,
        center=(0, 0),
        rotation_rad=1.2
    )

    rotation = get_rotation_between(domain1, domain2)
    assert approx_equal(rotation, 0.7), f"Expected 0.7, got {rotation}"


def test_get_translation_between():
    """Test getting translation vector between domains."""
    domain1 = Domain.from_rectangle(width_mm=100, height_mm=100, center=(100, 50))
    domain2 = Domain.from_rectangle(width_mm=100, height_mm=100, center=(200, 150))

    translation = get_translation_between(domain1, domain2)
    assert point_approx_equal(translation, (100, 100)), \
        f"Expected (100, 100), got {translation}"


# =============================================================================
# Edge Cases
# =============================================================================

def test_very_small_rotation():
    """Test transform with very small rotation angle."""
    domain = Domain.from_rectangle(
        width_mm=100, height_mm=100,
        center=(0, 0),
        rotation_rad=1e-10
    )

    # Should effectively be identity
    result = local_to_sheet((100, 0), domain)
    assert point_approx_equal(result, (100, 0), tolerance=1e-8), \
        f"Expected (100, 0), got {result}"


def test_full_rotation_360_degrees():
    """Test transform with full 360 degree rotation."""
    domain = Domain.from_rectangle(
        width_mm=100, height_mm=100,
        center=(0, 0),
        rotation_rad=2 * math.pi
    )

    # Full rotation should be identity
    result = local_to_sheet((10, 5), domain)
    assert point_approx_equal(result, (10, 5), tolerance=1e-10), \
        f"Expected (10, 5), got {result}"


def test_large_coordinates():
    """Test transform with large coordinate values."""
    domain = Domain.from_rectangle(
        width_mm=100, height_mm=100,
        center=(1e6, 1e6),
        rotation_rad=math.pi / 4
    )

    original = (1000, 2000)
    sheet_pt = local_to_sheet(original, domain)
    back = sheet_to_local(sheet_pt, domain)

    # Allow slightly larger tolerance for large numbers
    assert point_approx_equal(back, original, tolerance=1e-6), \
        f"Round-trip failed: {original} -> {back}"


def test_negative_coordinates():
    """Test transform with negative coordinates."""
    domain = Domain.from_rectangle(
        width_mm=100, height_mm=100,
        center=(-200, -150),
        rotation_rad=-math.pi / 4
    )

    original = (-50, -25)
    sheet_pt = local_to_sheet(original, domain)
    back = sheet_to_local(sheet_pt, domain)

    assert point_approx_equal(back, original, tolerance=1e-10), \
        f"Round-trip failed: {original} -> {back}"


def test_domain_at_boundary_vertices():
    """Test transforms at domain boundary vertices."""
    domain = Domain.from_rectangle(width_mm=100, height_mm=100, center=(50, 50))

    # Corner of domain in local coordinates (50, 50) from center
    corner_local = (50, 50)
    corner_sheet = local_to_sheet(corner_local, domain)

    # Should map to (100, 100) in sheet space
    assert point_approx_equal(corner_sheet, (100, 100)), \
        f"Expected (100, 100), got {corner_sheet}"


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

    print(f"Running {len(tests)} transform tests...")
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
