"""Tests for guillotine bin packing algorithm (Phase 2).

Run from repository root: PYTHONPATH=. python3 -m tests.test_guillotine
"""

import sys
from nesting.guillotine import (
    FreeRect,
    PlacementResult,
    guillotine_pack,
    _compute_utilization,
)


def test_free_rect_basic():
    """Test FreeRect properties."""
    print("Running test_free_rect_basic...")
    rect = FreeRect(x=10, y=20, width=100, height=200)
    assert rect.x == 10
    assert rect.y == 20
    assert rect.width == 100
    assert rect.height == 200
    assert rect.area == 20000
    print("  PASSED")


def test_free_rect_can_fit():
    """Test can_fit method."""
    print("Running test_free_rect_can_fit...")
    rect = FreeRect(x=0, y=0, width=100, height=200)

    # Exact fit
    assert rect.can_fit(100, 200, gap=0)

    # Smaller part
    assert rect.can_fit(50, 100, gap=0)

    # Too wide
    assert not rect.can_fit(150, 100, gap=0)

    # Too tall
    assert not rect.can_fit(50, 250, gap=0)

    # With gap
    assert rect.can_fit(90, 190, gap=10)  # 90+10=100, 190+10=200
    assert not rect.can_fit(95, 195, gap=10)  # Would exceed

    print("  PASSED")


def test_free_rect_can_fit_rotated():
    """Test can_fit_rotated method."""
    print("Running test_free_rect_can_fit_rotated...")
    rect = FreeRect(x=0, y=0, width=100, height=200)

    # 150x50 doesn't fit normally, but rotated (50x150) does
    assert not rect.can_fit(150, 50, gap=0)
    assert rect.can_fit_rotated(150, 50, gap=0)  # Becomes 50x150

    print("  PASSED")


def test_single_part_fits():
    """Single part that fits in bin."""
    print("Running test_single_part_fits...")
    # Use non-square part with rotation disabled to ensure predictable placement
    parts = [(100, 200, False, "part1")]  # allow_rotation=False
    placements = guillotine_pack(parts, bin_width=200, bin_height=300, gap=0)

    assert len(placements) == 1
    p = placements[0]
    assert p.metadata == "part1"
    assert p.rotated is False
    # Center should be at (50, 100) for bottom-left placement
    assert p.x == 50
    assert p.y == 100
    print("  PASSED")


def test_single_part_too_large():
    """Single part that doesn't fit."""
    print("Running test_single_part_too_large...")
    parts = [(500, 500, True, "big")]
    placements = guillotine_pack(parts, bin_width=200, bin_height=300, gap=0)

    assert len(placements) == 0
    print("  PASSED")


def test_single_part_fits_rotated():
    """Part only fits when rotated."""
    print("Running test_single_part_fits_rotated...")
    # Bin is 100 wide x 200 tall
    # Part is 150 wide x 50 tall - doesn't fit
    # Rotated: 50 wide x 150 tall - fits!
    parts = [(150, 50, True, "rotatable")]
    placements = guillotine_pack(parts, bin_width=100, bin_height=200, gap=0)

    assert len(placements) == 1
    p = placements[0]
    assert p.rotated is True
    # After rotation: 50x150, center at (25, 75)
    assert p.x == 25
    assert p.y == 75
    print("  PASSED")


def test_rotation_disabled():
    """Part doesn't fit when rotation is disabled."""
    print("Running test_rotation_disabled...")
    parts = [(150, 50, False, "no_rotate")]  # allow_rotation=False
    placements = guillotine_pack(parts, bin_width=100, bin_height=200, gap=0)

    assert len(placements) == 0
    print("  PASSED")


def test_multiple_parts_simple():
    """Multiple parts that fit side by side."""
    print("Running test_multiple_parts_simple...")
    # Two 100x100 parts in a 200x100 bin
    parts = [
        (100, 100, True, "a"),
        (100, 100, True, "b"),
    ]
    placements = guillotine_pack(parts, bin_width=200, bin_height=100, gap=0)

    assert len(placements) == 2
    # Both should be placed
    placed_ids = {p.metadata for p in placements}
    assert placed_ids == {"a", "b"}
    print("  PASSED")


def test_multiple_parts_stacked():
    """Multiple parts that stack vertically."""
    print("Running test_multiple_parts_stacked...")
    # Three 100x100 parts in a 100x300 bin
    parts = [
        (100, 100, True, "a"),
        (100, 100, True, "b"),
        (100, 100, True, "c"),
    ]
    placements = guillotine_pack(parts, bin_width=100, bin_height=300, gap=0)

    assert len(placements) == 3
    placed_ids = {p.metadata for p in placements}
    assert placed_ids == {"a", "b", "c"}
    print("  PASSED")


def test_gap_between_parts():
    """Parts with kerf gap between them."""
    print("Running test_gap_between_parts...")
    # Two 95x100 parts with 5mm gap in 200x100 bin
    # Should fit: 95 + 5 + 95 + 5 = 200
    parts = [
        (95, 100, True, "a"),
        (95, 100, True, "b"),
    ]
    placements = guillotine_pack(parts, bin_width=200, bin_height=105, gap=5)

    assert len(placements) == 2
    print("  PASSED")


def test_gap_prevents_fit():
    """Gap makes parts not fit."""
    print("Running test_gap_prevents_fit...")
    # Two 100x100 parts with 10mm gap in 200x100 bin
    # Won't fit: 100 + 10 + 100 + 10 = 220 > 200
    parts = [
        (100, 100, True, "a"),
        (100, 100, True, "b"),
    ]
    placements = guillotine_pack(parts, bin_width=200, bin_height=110, gap=10)

    # Only one should fit (first one placed, second doesn't fit)
    assert len(placements) == 1
    print("  PASSED")


def test_sorting_by_area():
    """Large parts placed first for better packing."""
    print("Running test_sorting_by_area...")
    # Mix of sizes - without sorting, small parts might fragment space
    parts = [
        (50, 50, True, "small1"),
        (200, 200, True, "big"),
        (50, 50, True, "small2"),
    ]
    placements = guillotine_pack(
        parts, bin_width=250, bin_height=250, gap=0, sort_by_area=True
    )

    # Big should be placed first, then smalls fit in remaining space
    assert len(placements) >= 2  # At least big + 1 small
    # Verify big was placed
    assert any(p.metadata == "big" for p in placements)
    print("  PASSED")


def test_real_world_doors():
    """Simulate packing cabinet doors on a sheet."""
    print("Running test_real_world_doors...")
    # 4 doors (457x597) on 1225x1212 usable area (half-sheet with margins)
    door_w, door_h = 457, 597
    parts = [
        (door_w, door_h, True, f"door{i}") for i in range(4)
    ]

    # Usable area after 10mm margins on 1245x1232 sheet
    usable_w = 1245 - 20  # 1225
    usable_h = 1232 - 20  # 1212

    placements = guillotine_pack(parts, bin_width=usable_w, bin_height=usable_h, gap=6)

    # Should fit all 4 doors (2x2 grid)
    # 2 doors wide: 457 + 6 + 457 = 920 < 1225
    # 2 doors tall: 597 + 6 + 597 = 1200 < 1212
    assert len(placements) == 4

    # Verify no overlaps (rough check via bounds)
    for i, p1 in enumerate(placements):
        for j, p2 in enumerate(placements):
            if i >= j:
                continue
            # Get dimensions (accounting for rotation)
            w1 = door_h if p1.rotated else door_w
            h1 = door_w if p1.rotated else door_h
            w2 = door_h if p2.rotated else door_w
            h2 = door_w if p2.rotated else door_h

            # Check bounds don't overlap (with tolerance for gap)
            left1, right1 = p1.x - w1/2, p1.x + w1/2
            left2, right2 = p2.x - w2/2, p2.x + w2/2
            bottom1, top1 = p1.y - h1/2, p1.y + h1/2
            bottom2, top2 = p2.y - h2/2, p2.y + h2/2

            # They should not overlap
            overlaps_x = not (right1 <= left2 or right2 <= left1)
            overlaps_y = not (top1 <= bottom2 or top2 <= bottom1)
            assert not (overlaps_x and overlaps_y), f"Overlap between {p1.metadata} and {p2.metadata}"

    print("  PASSED")


def test_real_world_mixed_sizes():
    """Mix of door and drawer sizes."""
    print("Running test_real_world_mixed_sizes...")
    # 4 doors + 7 drawers like Recipe 16
    parts = []
    # Doors
    for i in range(4):
        parts.append((457, 597, True, f"door{i}"))
    # Drawers
    for i in range(7):
        parts.append((254, 152, True, f"drawer{i}"))

    usable_w = 1225
    usable_h = 1212

    placements = guillotine_pack(parts, bin_width=usable_w, bin_height=usable_h, gap=6)

    # Count placed doors and drawers
    placed_doors = sum(1 for p in placements if "door" in p.metadata)
    placed_drawers = sum(1 for p in placements if "drawer" in p.metadata)

    # Should fit all 4 doors
    assert placed_doors == 4, f"Expected 4 doors, got {placed_doors}"

    # Guillotine may not pack as optimally as manual layout
    # Just verify reasonable packing (at least some drawers fit)
    assert placed_drawers >= 3, f"Expected at least 3 drawers, got {placed_drawers}"
    print(f"  Placed {placed_doors} doors + {placed_drawers} drawers")
    print("  PASSED")


def test_utilization_calculation():
    """Test utilization computation."""
    print("Running test_utilization_calculation...")
    parts = [(100, 100, True, "square")]
    placements = guillotine_pack(parts, bin_width=200, bin_height=200, gap=0)

    util = _compute_utilization(placements, parts, bin_width=200, bin_height=200)
    # 100x100 / 200x200 = 10000 / 40000 = 0.25
    assert abs(util - 0.25) < 0.001
    print("  PASSED")


def test_utilization_multiple_parts():
    """Test utilization with multiple parts."""
    print("Running test_utilization_multiple_parts...")
    parts = [
        (100, 100, True, "a"),
        (100, 100, True, "b"),
    ]
    placements = guillotine_pack(parts, bin_width=200, bin_height=100, gap=0)

    util = _compute_utilization(placements, parts, bin_width=200, bin_height=100)
    # 2 * 10000 / 20000 = 1.0 (perfect packing)
    assert abs(util - 1.0) < 0.001
    print("  PASSED")


def test_empty_bin():
    """Empty bin returns no placements."""
    print("Running test_empty_bin...")
    parts = [(100, 100, True, "part")]
    placements = guillotine_pack(parts, bin_width=0, bin_height=100, gap=0)
    assert len(placements) == 0

    placements = guillotine_pack(parts, bin_width=100, bin_height=0, gap=0)
    assert len(placements) == 0
    print("  PASSED")


def test_empty_parts_list():
    """Empty parts list returns no placements."""
    print("Running test_empty_parts_list...")
    parts = []
    placements = guillotine_pack(parts, bin_width=1000, bin_height=1000, gap=0)
    assert len(placements) == 0
    print("  PASSED")


def test_placements_within_bounds():
    """All placements should be within bin bounds."""
    print("Running test_placements_within_bounds...")
    parts = [
        (100, 200, True, "a"),
        (150, 100, True, "b"),
        (80, 80, True, "c"),
    ]
    bin_w, bin_h = 300, 300
    placements = guillotine_pack(parts, bin_width=bin_w, bin_height=bin_h, gap=5)

    for p in placements:
        # Find original dimensions
        for w, h, _, meta in parts:
            if meta == p.metadata:
                actual_w = h if p.rotated else w
                actual_h = w if p.rotated else h
                break

        left = p.x - actual_w / 2
        right = p.x + actual_w / 2
        bottom = p.y - actual_h / 2
        top = p.y + actual_h / 2

        assert left >= 0, f"{p.metadata} left edge {left} < 0"
        assert bottom >= 0, f"{p.metadata} bottom edge {bottom} < 0"
        assert right <= bin_w, f"{p.metadata} right edge {right} > {bin_w}"
        assert top <= bin_h, f"{p.metadata} top edge {top} > {bin_h}"

    print("  PASSED")


def run_all_tests():
    """Run all tests."""
    print("=" * 60)
    print("Phase 2: Guillotine Bin Packer Tests")
    print("=" * 60)

    tests = [
        test_free_rect_basic,
        test_free_rect_can_fit,
        test_free_rect_can_fit_rotated,
        test_single_part_fits,
        test_single_part_too_large,
        test_single_part_fits_rotated,
        test_rotation_disabled,
        test_multiple_parts_simple,
        test_multiple_parts_stacked,
        test_gap_between_parts,
        test_gap_prevents_fit,
        test_sorting_by_area,
        test_real_world_doors,
        test_real_world_mixed_sizes,
        test_utilization_calculation,
        test_utilization_multiple_parts,
        test_empty_bin,
        test_empty_parts_list,
        test_placements_within_bounds,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"  FAILED: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print()
    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
