
import sys
from nesting.guillotine import (
    FreeRect,
    PlacementResult,
    guillotine_pack,
    _compute_utilization,
)


def test_free_rect_basic():
    print("Running test_free_rect_basic...")
    rect = FreeRect(x=10, y=20, width=100, height=200)
    assert rect.x == 10
    assert rect.y == 20
    assert rect.width == 100
    assert rect.height == 200
    assert rect.area == 20000
    print("  PASSED")


def test_free_rect_can_fit():
    print("Running test_free_rect_can_fit...")
    rect = FreeRect(x=0, y=0, width=100, height=200)


    assert rect.can_fit(100, 200, gap=0)


    assert rect.can_fit(50, 100, gap=0)


    assert not rect.can_fit(150, 100, gap=0)


    assert not rect.can_fit(50, 250, gap=0)


    assert rect.can_fit(90, 190, gap=10)
    assert not rect.can_fit(95, 195, gap=10)

    print("  PASSED")


def test_free_rect_can_fit_rotated():
    print("Running test_free_rect_can_fit_rotated...")
    rect = FreeRect(x=0, y=0, width=100, height=200)


    assert not rect.can_fit(150, 50, gap=0)
    assert rect.can_fit_rotated(150, 50, gap=0)

    print("  PASSED")


def test_single_part_fits():
    print("Running test_single_part_fits...")

    parts = [(100, 200, False, "part1")]
    placements = guillotine_pack(parts, bin_width=200, bin_height=300, gap=0)

    assert len(placements) == 1
    p = placements[0]
    assert p.metadata == "part1"
    assert p.rotated is False

    assert p.x == 50
    assert p.y == 100
    print("  PASSED")


def test_single_part_too_large():
    print("Running test_single_part_too_large...")
    parts = [(500, 500, True, "big")]
    placements = guillotine_pack(parts, bin_width=200, bin_height=300, gap=0)

    assert len(placements) == 0
    print("  PASSED")


def test_single_part_fits_rotated():
    print("Running test_single_part_fits_rotated...")


    parts = [(150, 50, True, "rotatable")]
    placements = guillotine_pack(parts, bin_width=100, bin_height=200, gap=0)

    assert len(placements) == 1
    p = placements[0]
    assert p.rotated is True

    assert p.x == 25
    assert p.y == 75
    print("  PASSED")


def test_rotation_disabled():
    print("Running test_rotation_disabled...")
    parts = [(150, 50, False, "no_rotate")]
    placements = guillotine_pack(parts, bin_width=100, bin_height=200, gap=0)

    assert len(placements) == 0
    print("  PASSED")


def test_multiple_parts_simple():
    print("Running test_multiple_parts_simple...")

    parts = [
        (100, 100, True, "a"),
        (100, 100, True, "b"),
    ]
    placements = guillotine_pack(parts, bin_width=200, bin_height=100, gap=0)

    assert len(placements) == 2

    placed_ids = {p.metadata for p in placements}
    assert placed_ids == {"a", "b"}
    print("  PASSED")


def test_multiple_parts_stacked():
    print("Running test_multiple_parts_stacked...")

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
    print("Running test_gap_between_parts...")


    parts = [
        (95, 100, True, "a"),
        (95, 100, True, "b"),
    ]
    placements = guillotine_pack(parts, bin_width=200, bin_height=105, gap=5)

    assert len(placements) == 2
    print("  PASSED")


def test_gap_prevents_fit():
    print("Running test_gap_prevents_fit...")


    parts = [
        (100, 100, True, "a"),
        (100, 100, True, "b"),
    ]
    placements = guillotine_pack(parts, bin_width=200, bin_height=110, gap=10)


    assert len(placements) == 1
    print("  PASSED")


def test_sorting_by_area():
    print("Running test_sorting_by_area...")

    parts = [
        (50, 50, True, "small1"),
        (200, 200, True, "big"),
        (50, 50, True, "small2"),
    ]
    placements = guillotine_pack(
        parts, bin_width=250, bin_height=250, gap=0, sort_by_area=True
    )


    assert len(placements) >= 2

    assert any(p.metadata == "big" for p in placements)
    print("  PASSED")


def test_real_world_doors():
    print("Running test_real_world_doors...")

    door_w, door_h = 457, 597
    parts = [
        (door_w, door_h, True, f"door{i}") for i in range(4)
    ]


    usable_w = 1245 - 20
    usable_h = 1232 - 20

    placements = guillotine_pack(parts, bin_width=usable_w, bin_height=usable_h, gap=6)


    assert len(placements) == 4


    for i, p1 in enumerate(placements):
        for j, p2 in enumerate(placements):
            if i >= j:
                continue

            w1 = door_h if p1.rotated else door_w
            h1 = door_w if p1.rotated else door_h
            w2 = door_h if p2.rotated else door_w
            h2 = door_w if p2.rotated else door_h


            left1, right1 = p1.x - w1/2, p1.x + w1/2
            left2, right2 = p2.x - w2/2, p2.x + w2/2
            bottom1, top1 = p1.y - h1/2, p1.y + h1/2
            bottom2, top2 = p2.y - h2/2, p2.y + h2/2


            overlaps_x = not (right1 <= left2 or right2 <= left1)
            overlaps_y = not (top1 <= bottom2 or top2 <= bottom1)
            assert not (overlaps_x and overlaps_y), f"Overlap between {p1.metadata} and {p2.metadata}"

    print("  PASSED")


def test_real_world_mixed_sizes():
    print("Running test_real_world_mixed_sizes...")

    parts = []

    for i in range(4):
        parts.append((457, 597, True, f"door{i}"))

    for i in range(7):
        parts.append((254, 152, True, f"drawer{i}"))

    usable_w = 1225
    usable_h = 1212

    placements = guillotine_pack(parts, bin_width=usable_w, bin_height=usable_h, gap=6)


    placed_doors = sum(1 for p in placements if "door" in p.metadata)
    placed_drawers = sum(1 for p in placements if "drawer" in p.metadata)


    assert placed_doors == 4, f"Expected 4 doors, got {placed_doors}"


    assert placed_drawers >= 3, f"Expected at least 3 drawers, got {placed_drawers}"
    print(f"  Placed {placed_doors} doors + {placed_drawers} drawers")
    print("  PASSED")


def test_utilization_calculation():
    print("Running test_utilization_calculation...")
    parts = [(100, 100, True, "square")]
    placements = guillotine_pack(parts, bin_width=200, bin_height=200, gap=0)

    util = _compute_utilization(placements, parts, bin_width=200, bin_height=200)

    assert abs(util - 0.25) < 0.001
    print("  PASSED")


def test_utilization_multiple_parts():
    print("Running test_utilization_multiple_parts...")
    parts = [
        (100, 100, True, "a"),
        (100, 100, True, "b"),
    ]
    placements = guillotine_pack(parts, bin_width=200, bin_height=100, gap=0)

    util = _compute_utilization(placements, parts, bin_width=200, bin_height=100)

    assert abs(util - 1.0) < 0.001
    print("  PASSED")


def test_empty_bin():
    print("Running test_empty_bin...")
    parts = [(100, 100, True, "part")]
    placements = guillotine_pack(parts, bin_width=0, bin_height=100, gap=0)
    assert len(placements) == 0

    placements = guillotine_pack(parts, bin_width=100, bin_height=0, gap=0)
    assert len(placements) == 0
    print("  PASSED")


def test_empty_parts_list():
    print("Running test_empty_parts_list...")
    parts = []
    placements = guillotine_pack(parts, bin_width=1000, bin_height=1000, gap=0)
    assert len(placements) == 0
    print("  PASSED")


def test_placements_within_bounds():
    print("Running test_placements_within_bounds...")
    parts = [
        (100, 200, True, "a"),
        (150, 100, True, "b"),
        (80, 80, True, "c"),
    ]
    bin_w, bin_h = 300, 300
    placements = guillotine_pack(parts, bin_width=bin_w, bin_height=bin_h, gap=5)

    for p in placements:

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
