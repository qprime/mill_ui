from __future__ import annotations

import pytest

from nesting.waste_decomposition import (
    PartBounds,
    WasteRect,
    WasteStrategy,
    compute_waste_rectangles,
)


class TestWasteRectProperties:
    def test_area(self):
        r = WasteRect(x=10, y=20, width=30, height=40)
        assert r.area == 1200.0

    def test_right(self):
        r = WasteRect(x=10, y=20, width=30, height=40)
        assert r.right == 40.0

    def test_top(self):
        r = WasteRect(x=10, y=20, width=30, height=40)
        assert r.top == 60.0

    def test_center(self):
        r = WasteRect(x=10, y=20, width=30, height=40)
        assert r.center_x == 25.0
        assert r.center_y == 40.0


class TestPartBoundsProperties:
    def test_right(self):
        p = PartBounds(x=10, y=20, width=30, height=40)
        assert p.right == 40.0

    def test_top(self):
        p = PartBounds(x=10, y=20, width=30, height=40)
        assert p.top == 60.0


class TestComputeWasteNoParts:
    def test_empty_sheet_returns_whole_usable(self):
        result = compute_waste_rectangles(
            sheet_width=1000,
            sheet_height=1000,
            margin=10,
            parts=[],
            min_width=50,
            min_height=50,
        )
        assert len(result) == 1
        r = result[0]
        assert r.x == pytest.approx(10.0)
        assert r.y == pytest.approx(10.0)
        assert r.width == pytest.approx(980.0)
        assert r.height == pytest.approx(980.0)

    def test_zero_margin(self):
        result = compute_waste_rectangles(
            sheet_width=500,
            sheet_height=300,
            margin=0,
            parts=[],
            min_width=10,
            min_height=10,
        )
        assert len(result) == 1
        assert result[0].width == pytest.approx(500.0)
        assert result[0].height == pytest.approx(300.0)


class TestComputeWasteSinglePart:
    def test_centered_part(self):
        result = compute_waste_rectangles(
            sheet_width=1000,
            sheet_height=1000,
            margin=0,
            parts=[PartBounds(x=400, y=400, width=200, height=200)],
            min_width=50,
            min_height=50,
        )
        assert len(result) > 0
        total_waste = sum(r.area for r in result)
        assert total_waste > 0
        full_area = 1000 * 1000
        part_area = 200 * 200
        assert total_waste <= full_area - part_area

    def test_corner_part(self):
        result = compute_waste_rectangles(
            sheet_width=1000,
            sheet_height=1000,
            margin=0,
            parts=[PartBounds(x=0, y=0, width=200, height=200)],
            min_width=50,
            min_height=50,
        )
        assert len(result) > 0

    def test_part_filling_sheet(self):
        result = compute_waste_rectangles(
            sheet_width=1000,
            sheet_height=1000,
            margin=0,
            parts=[PartBounds(x=0, y=0, width=1000, height=1000)],
            min_width=50,
            min_height=50,
        )
        assert len(result) == 0


class TestComputeWasteMultipleParts:
    def test_two_parts_side_by_side(self):
        result = compute_waste_rectangles(
            sheet_width=1000,
            sheet_height=500,
            margin=0,
            parts=[
                PartBounds(x=0, y=0, width=400, height=500),
                PartBounds(x=500, y=0, width=400, height=500),
            ],
            min_width=50,
            min_height=50,
        )
        assert len(result) >= 1
        total_waste = sum(r.area for r in result)
        assert total_waste > 0

    def test_parts_leave_no_waste(self):
        result = compute_waste_rectangles(
            sheet_width=200,
            sheet_height=100,
            margin=0,
            parts=[
                PartBounds(x=0, y=0, width=100, height=100),
                PartBounds(x=100, y=0, width=100, height=100),
            ],
            min_width=50,
            min_height=50,
        )
        assert len(result) == 0


class TestComputeWasteMinDimensions:
    def test_small_gaps_filtered(self):
        result = compute_waste_rectangles(
            sheet_width=200,
            sheet_height=200,
            margin=0,
            parts=[PartBounds(x=0, y=0, width=190, height=200)],
            min_width=50,
            min_height=50,
        )
        assert len(result) == 0

    def test_large_gaps_kept(self):
        result = compute_waste_rectangles(
            sheet_width=200,
            sheet_height=200,
            margin=0,
            parts=[PartBounds(x=0, y=0, width=100, height=200)],
            min_width=50,
            min_height=50,
        )
        assert len(result) >= 1


class TestComputeWasteMargin:
    def test_margin_reduces_usable(self):
        with_margin = compute_waste_rectangles(
            sheet_width=1000,
            sheet_height=1000,
            margin=100,
            parts=[],
            min_width=50,
            min_height=50,
        )
        without_margin = compute_waste_rectangles(
            sheet_width=1000,
            sheet_height=1000,
            margin=0,
            parts=[],
            min_width=50,
            min_height=50,
        )
        assert with_margin[0].area < without_margin[0].area

    def test_margin_larger_than_sheet(self):
        result = compute_waste_rectangles(
            sheet_width=100,
            sheet_height=100,
            margin=60,
            parts=[],
            min_width=50,
            min_height=50,
        )
        assert len(result) == 0


class TestComputeWasteStrategies:
    def test_guillotine_strategy(self):
        result = compute_waste_rectangles(
            sheet_width=1000,
            sheet_height=1000,
            margin=0,
            parts=[PartBounds(x=100, y=100, width=200, height=200)],
            min_width=50,
            min_height=50,
            strategy=WasteStrategy.SIMPLE,
        )
        assert len(result) > 0

    def test_maxrects_strategy(self):
        result = compute_waste_rectangles(
            sheet_width=1000,
            sheet_height=1000,
            margin=0,
            parts=[PartBounds(x=100, y=100, width=200, height=200)],
            min_width=50,
            min_height=50,
            strategy=WasteStrategy.LARGEST,
        )
        assert len(result) > 0

    def test_sorted_by_area_descending(self):
        result = compute_waste_rectangles(
            sheet_width=1000,
            sheet_height=1000,
            margin=0,
            parts=[
                PartBounds(x=200, y=0, width=100, height=1000),
                PartBounds(x=600, y=0, width=100, height=1000),
            ],
            min_width=50,
            min_height=50,
        )
        for i in range(len(result) - 1):
            assert result[i].area >= result[i + 1].area


class TestComputeWasteToolClearance:
    def test_tool_clearance(self):
        no_clearance = compute_waste_rectangles(
            sheet_width=1000,
            sheet_height=1000,
            margin=0,
            parts=[PartBounds(x=100, y=100, width=200, height=200)],
            min_width=50,
            min_height=50,
            tool_clearance=0,
        )
        with_clearance = compute_waste_rectangles(
            sheet_width=1000,
            sheet_height=1000,
            margin=0,
            parts=[PartBounds(x=100, y=100, width=200, height=200)],
            min_width=50,
            min_height=50,
            tool_clearance=10,
        )
        no_total = sum(r.area for r in no_clearance)
        with_total = sum(r.area for r in with_clearance)
        assert with_total <= no_total


class TestComputeWasteNoOverlap:
    def test_waste_rects_dont_overlap_parts(self):
        parts = [
            PartBounds(x=100, y=100, width=200, height=200),
            PartBounds(x=400, y=300, width=150, height=150),
        ]
        result = compute_waste_rectangles(
            sheet_width=1000,
            sheet_height=1000,
            margin=0,
            parts=parts,
            min_width=50,
            min_height=50,
        )
        for wr in result:
            for part in parts:
                overlaps = not (
                    wr.x + wr.width <= part.x
                    or part.x + part.width <= wr.x
                    or wr.y + wr.height <= part.y
                    or part.y + part.height <= wr.y
                )
                assert not overlaps, (
                    f"Waste rect ({wr.x},{wr.y},{wr.width},{wr.height}) "
                    f"overlaps part ({part.x},{part.y},{part.width},{part.height})"
                )
