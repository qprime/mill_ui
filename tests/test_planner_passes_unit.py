from __future__ import annotations

import pytest

from cam.config import Config
from cam.model.machine import Machine
from cam.model.material import Material
from cam.model.setup import Setup
from cam.model.stock import Stock
from cam.model.tool import Tool
from cam.moves import CutMove, RapidMove, RetractMove, XYMove
from cam.ops.bore import pocket_circle_concentric
from cam.ops.engrave import engrave_lines
from cam.ops.face import face_zigzag
from cam.ops.pocket_region import _interval_subtract
from cam.planner.params import stepdown_for, stepover_for
from cam.planner.passes import PassAccumulator
from cam.planner.passes.edge import plan_edge_feature_passes, vbit_cut_depth, vbit_effective_radius
from cam.planner.passes.merge_shared_edges import _overlap_len, _rect_edges
from cam.planner.passes.pocket import (
    plan_engrave_passes,
    plan_hole_passes,
    plan_pocket_passes,
)
from cam.planner.passes.tools import (
    ToolSelection,
    normalize_tool_entries,
    pass_key,
    pick_tool_for_edge,
    pick_tool_for_engrave,
    pick_tool_for_hole,
    pick_tool_for_pocket,
    pick_tool_for_profile,
    stepdown_for_tool,
    stepover_for_tool,
)
from cam.planner.planner_input import EdgeFeatureInput, FeatureInput, GeometryInput
from ir.removal_intent import BevelSpec, ChamferSpec, ShapeGeometry

FLAT_3MM = {"name": "3mm_flat", "diameter": 3.0, "kind": "flat", "rpm": 18000, "feed_xy": 1000, "feed_z": 300}
FLAT_6MM = {"name": "6mm_flat", "diameter": 6.0, "kind": "flat", "rpm": 14000, "feed_xy": 900, "feed_z": 280}
FLAT_6MM_UPCUT = {
    "name": "6mm_upcut",
    "diameter": 6.0,
    "kind": "flat",
    "rpm": 14000,
    "feed_xy": 900,
    "feed_z": 280,
    "rotation": "upcut",
}
FLAT_12MM = {"name": "12mm_flat", "diameter": 12.0, "kind": "flat", "rpm": 10000, "feed_xy": 800, "feed_z": 250}
BALL_2MM = {"name": "2mm_ball", "diameter": 2.0, "kind": "ball", "rpm": 20000, "feed_xy": 600, "feed_z": 200}
V_1MM = {"name": "1mm_v", "diameter": 1.0, "kind": "v", "rpm": 22000, "feed_xy": 500, "feed_z": 150}
VBIT_90 = {
    "name": "90deg_v",
    "diameter": 12.7,
    "kind": "v",
    "rpm": 16000,
    "feed_xy": 1200,
    "feed_z": 400,
    "v_angle_deg": 90,
}
VBIT_60 = {
    "name": "60deg_v",
    "diameter": 12.7,
    "kind": "v",
    "rpm": 16000,
    "feed_xy": 1200,
    "feed_z": 400,
    "v_angle_deg": 60,
}

ALL_TOOLS = normalize_tool_entries([FLAT_3MM, FLAT_6MM, FLAT_6MM_UPCUT, FLAT_12MM, BALL_2MM, V_1MM])
FLAT_ONLY = normalize_tool_entries([FLAT_3MM, FLAT_6MM, FLAT_12MM])
TOOLS_WITH_VBIT = normalize_tool_entries([FLAT_3MM, FLAT_6MM, VBIT_90])
TOOLS_WITH_TWO_VBITS = normalize_tool_entries([FLAT_3MM, VBIT_60, VBIT_90])


def _setup(tool_diameter=6.0):
    return Setup(
        stock=Stock(width=300, height=200, thickness=19),
        tool=Tool(name="t", diameter=tool_diameter),
        material=Material(),
        machine=Machine(),
        safe_z=5.0,
    )


def _accumulator():
    return PassAccumulator(
        material=Material(),
        machine=Machine(),
        stock=Stock(width=300, height=200, thickness=19),
        safe_z=5.0,
        prime_spindle=False,
    )


class TestPickToolForPocket:
    def test_prefers_upcut_over_conventional(self):
        tool = pick_tool_for_pocket(ALL_TOOLS, required_width_mm=None, cleanup_offset_mm=0.0)
        assert tool.rotation == "upcut"

    def test_largest_tool_fitting_width(self):
        tool = pick_tool_for_pocket(FLAT_ONLY, required_width_mm=10.0, cleanup_offset_mm=0.0)
        assert tool.diameter == 6.0

    def test_clearance_with_cleanup_offset(self):
        tool = pick_tool_for_pocket(FLAT_ONLY, required_width_mm=10.0, cleanup_offset_mm=2.0)
        assert tool.diameter == 6.0

    def test_falls_back_when_no_tool_within_clearance(self):
        tool = pick_tool_for_pocket(FLAT_ONLY, required_width_mm=4.0, cleanup_offset_mm=0.0)
        assert tool.diameter == 3.0

    def test_no_width_constraint_picks_largest(self):
        tool = pick_tool_for_pocket(FLAT_ONLY, required_width_mm=None, cleanup_offset_mm=0.0)
        assert tool.diameter == 12.0

    def test_no_flat_tools_raises(self):
        with pytest.raises(ValueError, match="No flat tools"):
            pick_tool_for_pocket(normalize_tool_entries([BALL_2MM]), required_width_mm=None, cleanup_offset_mm=0.0)


class TestPickToolForProfile:
    def test_matches_kerf(self):
        tool = pick_tool_for_profile(FLAT_ONLY, kerf_mm=6.0)
        assert tool.diameter == 6.0

    def test_closest_to_kerf(self):
        tool = pick_tool_for_profile(FLAT_ONLY, kerf_mm=5.0)
        assert tool.diameter == 6.0

    def test_no_kerf_picks_smallest(self):
        tool = pick_tool_for_profile(FLAT_ONLY, kerf_mm=None)
        assert tool.diameter == 3.0

    def test_no_flat_tools_raises(self):
        with pytest.raises(ValueError, match="does not contain a flat tool"):
            pick_tool_for_profile(normalize_tool_entries([BALL_2MM]), kerf_mm=None)


class TestPickToolForHole:
    def test_largest_fitting_tool(self):
        tool = pick_tool_for_hole(FLAT_ONLY, hole_diameter_mm=8.0)
        assert tool.diameter == 6.0

    def test_exact_match(self):
        tool = pick_tool_for_hole(FLAT_ONLY, hole_diameter_mm=6.0)
        assert tool.diameter == 6.0

    def test_no_fitting_tool_falls_back_to_smallest(self):
        tool = pick_tool_for_hole(FLAT_ONLY, hole_diameter_mm=2.0)
        assert tool.diameter == 3.0

    def test_no_flat_tools_raises(self):
        with pytest.raises(ValueError, match="flat tool"):
            pick_tool_for_hole(normalize_tool_entries([BALL_2MM]), hole_diameter_mm=5.0)


class TestPickToolForEngrave:
    def test_prefers_ball_or_v(self):
        tool = pick_tool_for_engrave(ALL_TOOLS)
        assert tool.kind in {"ball", "v"}

    def test_picks_smallest_specialty_tool(self):
        tool = pick_tool_for_engrave(ALL_TOOLS)
        assert tool.diameter == 1.0

    def test_falls_back_to_flat_when_no_specialty(self):
        tool = pick_tool_for_engrave(FLAT_ONLY)
        assert tool.kind == "flat"
        assert tool.diameter == 3.0


class TestStepdownForTool:
    def test_uses_depth_per_pass_when_set(self):
        tool = ToolSelection(name="t", diameter=6.0, kind="flat", rpm=1, feed_xy=1, feed_z=1, depth_per_pass=2.0)
        assert stepdown_for_tool(tool) == 2.0

    def test_falls_back_to_half_diameter_capped(self):
        tool = ToolSelection(name="t", diameter=6.0, kind="flat", rpm=1, feed_xy=1, feed_z=1)
        assert stepdown_for_tool(tool) == 3.0

    def test_cap_at_3mm(self):
        tool = ToolSelection(name="t", diameter=12.0, kind="flat", rpm=1, feed_xy=1, feed_z=1)
        assert stepdown_for_tool(tool) == 3.0

    def test_zero_depth_per_pass_uses_fallback(self):
        tool = ToolSelection(name="t", diameter=6.0, kind="flat", rpm=1, feed_xy=1, feed_z=1, depth_per_pass=0.0)
        assert stepdown_for_tool(tool) == 3.0

    def test_small_tool(self):
        tool = ToolSelection(name="t", diameter=1.0, kind="flat", rpm=1, feed_xy=1, feed_z=1)
        assert stepdown_for_tool(tool) == 0.5


class TestStepoverForTool:
    def test_uses_stepover_percent_when_set(self):
        tool = ToolSelection(name="t", diameter=10.0, kind="flat", rpm=1, feed_xy=1, feed_z=1, stepover_percent=50.0)
        assert stepover_for_tool(tool) == 5.0

    def test_falls_back_to_40_percent(self):
        tool = ToolSelection(name="t", diameter=10.0, kind="flat", rpm=1, feed_xy=1, feed_z=1)
        assert stepover_for_tool(tool) == pytest.approx(4.0)

    def test_zero_stepover_percent_uses_fallback(self):
        tool = ToolSelection(name="t", diameter=10.0, kind="flat", rpm=1, feed_xy=1, feed_z=1, stepover_percent=0.0)
        assert stepover_for_tool(tool) == pytest.approx(4.0)


class TestStepdownFor:
    def test_half_diameter(self):
        assert stepdown_for(tool_diameter=6.0) == 3.0

    def test_capped(self):
        assert stepdown_for(tool_diameter=10.0, cap_mm=3.0) == 3.0

    def test_cap_larger_than_half(self):
        assert stepdown_for(tool_diameter=4.0, cap_mm=5.0) == 2.0


class TestStepoverFor:
    def test_default_ratio(self):
        assert stepover_for(tool_diameter=10.0) == pytest.approx(4.0)

    def test_custom_ratio(self):
        assert stepover_for(tool_diameter=10.0, ratio=0.6) == pytest.approx(6.0)


class TestIntervalSubtract:
    def test_no_overlap(self):
        assert _interval_subtract([(0, 10)], (15, 20)) == [(0, 10)]

    def test_full_cover(self):
        assert _interval_subtract([(2, 8)], (0, 10)) == []

    def test_left_trim(self):
        result = _interval_subtract([(0, 10)], (0, 5))
        assert len(result) == 1
        assert result[0] == pytest.approx((5, 10), abs=1e-9)

    def test_right_trim(self):
        result = _interval_subtract([(0, 10)], (5, 10))
        assert len(result) == 1
        assert result[0] == pytest.approx((0, 5), abs=1e-9)

    def test_split(self):
        result = _interval_subtract([(0, 10)], (3, 7))
        assert len(result) == 2
        assert result[0] == pytest.approx((0, 3), abs=1e-9)
        assert result[1] == pytest.approx((7, 10), abs=1e-9)

    def test_multiple_base_intervals(self):
        result = _interval_subtract([(0, 5), (10, 20)], (12, 15))
        assert len(result) == 3
        assert result[0] == pytest.approx((0, 5), abs=1e-9)
        assert result[1] == pytest.approx((10, 12), abs=1e-9)
        assert result[2] == pytest.approx((15, 20), abs=1e-9)

    def test_empty_base(self):
        assert _interval_subtract([], (0, 5)) == []


class TestPocketCircleConcentric:
    def test_produces_moves(self):
        setup = _setup(tool_diameter=3.0)
        moves = pocket_circle_concentric(
            (50.0, 50.0),
            20.0,
            setup,
            depth_mm=5.0,
            stepover_mm=1.0,
            stepdown_mm=2.0,
        )
        assert len(moves) > 0

    def test_cutting_moves_reach_target_depth(self):
        setup = _setup(tool_diameter=3.0)
        moves = pocket_circle_concentric(
            (50.0, 50.0),
            20.0,
            setup,
            depth_mm=5.0,
            stepover_mm=1.0,
            stepdown_mm=2.0,
        )
        cut_zs = [m.z for m in moves if isinstance(m, CutMove) and m.z is not None]
        assert min(cut_zs) == pytest.approx(-5.0, abs=0.01)

    def test_zero_wall_radius_returns_empty(self):
        setup = _setup(tool_diameter=20.0)
        moves = pocket_circle_concentric(
            (50.0, 50.0),
            20.0,
            setup,
            depth_mm=5.0,
            stepover_mm=1.0,
            stepdown_mm=2.0,
        )
        assert moves == []

    def test_retracts_above_safe_z(self):
        setup = _setup(tool_diameter=3.0)
        moves = pocket_circle_concentric(
            (50.0, 50.0),
            20.0,
            setup,
            depth_mm=5.0,
            stepover_mm=1.0,
            stepdown_mm=2.0,
        )
        retracts = [m for m in moves if isinstance(m, RetractMove)]
        assert all(m.z >= setup.safe_z for m in retracts)


class TestEngraveLines:
    def test_single_line(self):
        setup = _setup()
        moves = engrave_lines([[(0, 0), (10, 10)]], setup, z=-0.3)
        assert any(isinstance(m, CutMove) for m in moves)

    def test_depth(self):
        setup = _setup()
        moves = engrave_lines([[(0, 0), (10, 10)]], setup, z=-0.5)
        plunge_zs = [m.z for m in moves if isinstance(m, CutMove) and m.z is not None]
        assert plunge_zs[0] == pytest.approx(-0.5)

    def test_empty_polyline_skipped(self):
        setup = _setup()
        moves = engrave_lines([[]], setup, z=-0.3)
        assert not any(isinstance(m, CutMove) for m in moves)

    def test_multiple_polylines(self):
        setup = _setup()
        moves = engrave_lines(
            [[(0, 0), (10, 0)], [(20, 20), (30, 20)]],
            setup,
            z=-0.3,
        )
        rapids = [m for m in moves if isinstance(m, RapidMove)]
        assert len(rapids) >= 2


class TestFaceZigzag:
    def test_produces_moves(self):
        setup = _setup()
        moves = face_zigzag(100, 50, setup, step=10.0, depth_mm=0.5)
        assert len(moves) > 0

    def test_covers_height(self):
        setup = _setup()
        moves = face_zigzag(100, 50, setup, step=10.0, depth_mm=0.5)
        cut_ys = [m.y for m in moves if isinstance(m, XYMove) and m.y is not None]
        assert max(cut_ys) >= 50.0

    def test_serpentine_direction(self):
        setup = _setup()
        moves = face_zigzag(100, 50, setup, step=25.0, depth_mm=0.5)
        rapid_xs = [m.x for m in moves if isinstance(m, RapidMove) and m.x is not None]
        assert rapid_xs[0] == pytest.approx(0.0)
        assert rapid_xs[1] == pytest.approx(100.0)


class TestRectEdges:
    def test_four_edges(self):
        edges = _rect_edges(50, 50, 20, 10, "r1")
        assert len(edges) == 4

    def test_edge_orientations(self):
        edges = _rect_edges(50, 50, 20, 10, "r1")
        v_edges = [e for e in edges if e.orient == "v"]
        h_edges = [e for e in edges if e.orient == "h"]
        assert len(v_edges) == 2
        assert len(h_edges) == 2

    def test_edge_coordinates(self):
        edges = _rect_edges(50, 50, 20, 10, "r1")
        v_coords = sorted(e.coord for e in edges if e.orient == "v")
        h_coords = sorted(e.coord for e in edges if e.orient == "h")
        assert v_coords == pytest.approx([40.0, 60.0])
        assert h_coords == pytest.approx([45.0, 55.0])


class TestOverlapLen:
    def test_full_overlap(self):
        assert _overlap_len(0, 10, 0, 10) == pytest.approx(10.0)

    def test_partial_overlap(self):
        assert _overlap_len(0, 10, 5, 15) == pytest.approx(5.0)

    def test_no_overlap(self):
        assert _overlap_len(0, 5, 10, 15) == pytest.approx(0.0)

    def test_contained(self):
        assert _overlap_len(0, 20, 5, 10) == pytest.approx(5.0)

    def test_touching(self):
        assert _overlap_len(0, 5, 5, 10) == pytest.approx(0.0)


def _feature(shape, geometry, center, depth, start_depth=0.0, id="test"):
    points_raw = geometry.get("points")
    points = tuple((float(p[0]), float(p[1])) for p in points_raw) if points_raw else None
    start_raw = geometry.get("start")
    start = (float(start_raw[0]), float(start_raw[1])) if start_raw else None
    end_raw = geometry.get("end")
    end = (float(end_raw[0]), float(end_raw[1])) if end_raw else None
    shape_geometry = ShapeGeometry(
        w_mm=float(geometry["w_mm"]) if "w_mm" in geometry else None,
        h_mm=float(geometry["h_mm"]) if "h_mm" in geometry else None,
        diameter_mm=float(geometry["diameter_mm"]) if "diameter_mm" in geometry else None,
        points=points,
        start=start,
        end=end,
    )
    return FeatureInput(
        id=id,
        shape=shape,
        geometry=GeometryInput(shape=shape, geometry=shape_geometry),
        center_xy_mm=center,
        depth_mm=depth,
        start_depth_mm=start_depth,
    )


class TestPlanPocketPasses:
    def test_rect_pocket(self):
        acc = _accumulator()
        pockets = (_feature("Rect", {"w_mm": 50.0, "h_mm": 30.0}, (100.0, 75.0), 6.0),)
        plan_pocket_passes(pockets, accumulator=acc, tool_db=FLAT_ONLY, config=Config())
        records = acc.passes()
        assert len(records) == 1
        assert records[0].op == "pocket"
        assert records[0].count == 1
        assert len(records[0].moves) > 0

    def test_circle_pocket(self):
        acc = _accumulator()
        pockets = (_feature("Circle", {"diameter_mm": 20.0}, (100.0, 75.0), 6.0),)
        plan_pocket_passes(pockets, accumulator=acc, tool_db=FLAT_ONLY, config=Config())
        records = acc.passes()
        assert len(records) == 1
        assert records[0].op == "pocket"
        assert len(records[0].moves) > 0

    def test_zero_depth_produces_no_moves(self):
        acc = _accumulator()
        pockets = (_feature("Rect", {"w_mm": 50.0, "h_mm": 30.0}, (100.0, 75.0), 0.0),)
        plan_pocket_passes(pockets, accumulator=acc, tool_db=FLAT_ONLY, config=Config())
        records = acc.passes()
        total_moves = sum(len(r.moves) for r in records)
        assert total_moves == 0

    def test_start_depth_offset(self):
        acc = _accumulator()
        pockets = (_feature("Rect", {"w_mm": 50.0, "h_mm": 30.0}, (100.0, 75.0), 10.0, start_depth=4.0),)
        plan_pocket_passes(pockets, accumulator=acc, tool_db=FLAT_ONLY, config=Config())
        records = acc.passes()
        assert len(records) == 1

    def test_empty_pockets_list(self):
        acc = _accumulator()
        plan_pocket_passes((), accumulator=acc, tool_db=FLAT_ONLY, config=Config())
        assert len(acc.passes()) == 0

    def test_unknown_shape_produces_no_moves(self):
        acc = _accumulator()
        pockets = (_feature("Hexagon", {}, (100.0, 75.0), 6.0),)
        plan_pocket_passes(pockets, accumulator=acc, tool_db=FLAT_ONLY, config=Config())
        total_moves = sum(len(r.moves) for r in acc.passes())
        assert total_moves == 0


class TestPlanHolePasses:
    def test_drill_strategy_for_matching_diameter(self):
        acc = _accumulator()
        holes = (_feature("Circle", {"diameter_mm": 3.0}, (50.0, 50.0), 10.0),)
        plan_hole_passes(holes, accumulator=acc, tool_db=FLAT_ONLY)
        records = acc.passes()
        assert len(records) == 1
        assert records[0].op == "drill"

    def test_bore_strategy_for_medium_hole(self):
        acc = _accumulator()
        holes = (_feature("Circle", {"diameter_mm": 8.0}, (50.0, 50.0), 10.0),)
        plan_hole_passes(holes, accumulator=acc, tool_db=FLAT_ONLY)
        records = acc.passes()
        assert len(records) == 1
        assert records[0].op == "bore"

    def test_pocket_strategy_for_large_hole(self):
        acc = _accumulator()
        holes = (_feature("Circle", {"diameter_mm": 40.0}, (50.0, 50.0), 10.0),)
        plan_hole_passes(holes, accumulator=acc, tool_db=FLAT_ONLY)
        records = acc.passes()
        assert len(records) == 1
        assert records[0].op == "pocket"

    def test_non_circle_hole_skipped(self):
        acc = _accumulator()
        holes = (_feature("Rect", {"w_mm": 5.0, "h_mm": 5.0}, (50.0, 50.0), 10.0),)
        plan_hole_passes(holes, accumulator=acc, tool_db=FLAT_ONLY)
        assert len(acc.passes()) == 0


class TestPlanEngravePasses:
    def test_polyline_engrave(self):
        acc = _accumulator()
        engraves = (_feature("polyline", {"points": [[0, 0], [10, 0], [10, 10]]}, (50.0, 50.0), 0.3),)
        plan_engrave_passes(engraves, accumulator=acc, tool_db=ALL_TOOLS)
        records = acc.passes()
        assert len(records) == 1
        assert records[0].op == "engrave"

    def test_rect_engrave(self):
        acc = _accumulator()
        engraves = (_feature("rect", {"w_mm": 20.0, "h_mm": 10.0}, (50.0, 50.0), 0.3),)
        plan_engrave_passes(engraves, accumulator=acc, tool_db=ALL_TOOLS)
        records = acc.passes()
        assert len(records) == 1

    def test_line_engrave(self):
        acc = _accumulator()
        engraves = (_feature("line", {"start": [0, 0], "end": [20, 0]}, (50.0, 50.0), 0.3),)
        plan_engrave_passes(engraves, accumulator=acc, tool_db=ALL_TOOLS)
        records = acc.passes()
        assert len(records) == 1

    def test_unknown_shape_skipped(self):
        acc = _accumulator()
        engraves = (_feature("arc", {}, (50.0, 50.0), 0.3),)
        plan_engrave_passes(engraves, accumulator=acc, tool_db=ALL_TOOLS)
        assert len(acc.passes()) == 0

    def test_default_depth(self):
        acc = _accumulator()
        engraves = (_feature("line", {"start": [0, 0], "end": [10, 0]}, (0.0, 0.0), 0.0),)
        plan_engrave_passes(engraves, accumulator=acc, tool_db=ALL_TOOLS)
        records = acc.passes()
        assert len(records) == 1
        zs = [m.z for m in records[0].moves if isinstance(m, CutMove) and m.z is not None]
        assert zs[0] == pytest.approx(-0.3)


def _edge_feature(shape, geometry, center, depth, edge_feature, side="outside", start_depth=0.0, id="test_edge"):
    points_raw = geometry.get("points")
    points = tuple((float(p[0]), float(p[1])) for p in points_raw) if points_raw else None
    start_raw = geometry.get("start")
    start = (float(start_raw[0]), float(start_raw[1])) if start_raw else None
    end_raw = geometry.get("end")
    end = (float(end_raw[0]), float(end_raw[1])) if end_raw else None
    shape_geometry = ShapeGeometry(
        w_mm=float(geometry["w_mm"]) if "w_mm" in geometry else None,
        h_mm=float(geometry["h_mm"]) if "h_mm" in geometry else None,
        diameter_mm=float(geometry["diameter_mm"]) if "diameter_mm" in geometry else None,
        points=points,
        start=start,
        end=end,
    )
    return EdgeFeatureInput(
        id=id,
        shape=shape,
        geometry=GeometryInput(shape=shape, geometry=shape_geometry),
        center_xy_mm=center,
        depth_mm=depth,
        start_depth_mm=start_depth,
        side=side,
        edge_feature=edge_feature,
    )


class TestVbitGeometry:
    def test_45_degree_chamfer(self):
        assert vbit_cut_depth(10.0, 45.0) == pytest.approx(10.0)

    def test_30_degree_chamfer(self):
        assert vbit_cut_depth(10.0, 30.0) == pytest.approx(5.7735, abs=0.001)

    def test_60_degree_chamfer(self):
        assert vbit_cut_depth(10.0, 60.0) == pytest.approx(17.3205, abs=0.001)

    def test_zero_angle_returns_width(self):
        assert vbit_cut_depth(10.0, 0.0) == pytest.approx(10.0)

    def test_90_angle_returns_width(self):
        assert vbit_cut_depth(10.0, 90.0) == pytest.approx(10.0)

    def test_negative_angle_returns_width(self):
        assert vbit_cut_depth(10.0, -5.0) == pytest.approx(10.0)

    def test_90_degree_vbit(self):
        assert vbit_effective_radius(10.0, 90.0) == pytest.approx(10.0)

    def test_60_degree_vbit(self):
        assert vbit_effective_radius(10.0, 60.0) == pytest.approx(5.7735, abs=0.001)

    def test_120_degree_vbit(self):
        assert vbit_effective_radius(10.0, 120.0) == pytest.approx(17.3205, abs=0.001)


class TestPickToolForEdge:
    def test_selects_closest_angle(self):
        tool = pick_tool_for_edge(TOOLS_WITH_TWO_VBITS, angle_deg=90.0)
        assert tool.v_angle_deg == 90.0

    def test_no_vbits_raises(self):
        with pytest.raises(ValueError, match="V-bit"):
            pick_tool_for_edge(FLAT_ONLY, angle_deg=90.0)

    def test_single_vbit(self):
        tool = pick_tool_for_edge(TOOLS_WITH_VBIT, angle_deg=60.0)
        assert tool.v_angle_deg == 90.0

    def test_ignores_flat_tools(self):
        tool = pick_tool_for_edge(TOOLS_WITH_VBIT, angle_deg=90.0)
        assert tool.kind == "v"


class TestPlanEdgeFeaturePasses:
    def test_chamfer_produces_edge_record(self):
        acc = _accumulator()
        entries = (
            _edge_feature(
                "Rect", {"w_mm": 50.0, "h_mm": 30.0}, (100.0, 75.0), 6.0, ChamferSpec(width_mm=2.0, angle_deg=45.0)
            ),
        )
        plan_edge_feature_passes(entries, accumulator=acc, tool_db=TOOLS_WITH_VBIT)
        records = acc.passes()
        assert len(records) == 1
        assert records[0].op == "edge"
        assert len(records[0].moves) > 0

    def test_bevel_produces_edge_record(self):
        acc = _accumulator()
        entries = (
            _edge_feature(
                "Rect",
                {"w_mm": 50.0, "h_mm": 30.0},
                (100.0, 75.0),
                6.0,
                BevelSpec(width_mm=2.0, angle_deg=45.0, inner_depth_mm=1.0),
            ),
        )
        plan_edge_feature_passes(entries, accumulator=acc, tool_db=TOOLS_WITH_VBIT)
        records = acc.passes()
        assert len(records) == 1
        assert records[0].op == "edge"
        assert len(records[0].moves) > 0

    def test_no_vbit_skips(self):
        acc = _accumulator()
        entries = (
            _edge_feature(
                "Rect", {"w_mm": 50.0, "h_mm": 30.0}, (100.0, 75.0), 6.0, ChamferSpec(width_mm=2.0, angle_deg=45.0)
            ),
        )
        plan_edge_feature_passes(entries, accumulator=acc, tool_db=FLAT_ONLY)
        assert len(acc.passes()) == 0

    def test_none_spec_skips(self):
        acc = _accumulator()
        entries = (_edge_feature("Rect", {"w_mm": 50.0, "h_mm": 30.0}, (100.0, 75.0), 6.0, None),)
        plan_edge_feature_passes(entries, accumulator=acc, tool_db=TOOLS_WITH_VBIT)
        assert len(acc.passes()) == 0

    def test_inside_offset_negative(self):
        acc = _accumulator()
        entries = (
            _edge_feature(
                "Rect",
                {"w_mm": 50.0, "h_mm": 30.0},
                (100.0, 75.0),
                6.0,
                ChamferSpec(width_mm=2.0, angle_deg=45.0),
                side="inside",
            ),
        )
        plan_edge_feature_passes(entries, accumulator=acc, tool_db=TOOLS_WITH_VBIT)
        records = acc.passes()
        assert len(records) == 1
        assert len(records[0].moves) > 0

    def test_outside_offset_positive(self):
        acc = _accumulator()
        entries = (
            _edge_feature(
                "Rect",
                {"w_mm": 50.0, "h_mm": 30.0},
                (100.0, 75.0),
                6.0,
                ChamferSpec(width_mm=2.0, angle_deg=45.0),
                side="outside",
            ),
        )
        plan_edge_feature_passes(entries, accumulator=acc, tool_db=TOOLS_WITH_VBIT)
        records = acc.passes()
        assert len(records) == 1
        assert len(records[0].moves) > 0


class TestPassKey:
    def test_different_v_angles_different_keys(self):
        tool_90 = ToolSelection(
            name="v90", diameter=12.7, kind="v", rpm=16000, feed_xy=1200, feed_z=400, v_angle_deg=90.0
        )
        tool_60 = ToolSelection(
            name="v60", diameter=12.7, kind="v", rpm=16000, feed_xy=1200, feed_z=400, v_angle_deg=60.0
        )
        assert pass_key("edge", tool_90) != pass_key("edge", tool_60)

    def test_flat_tools_unaffected(self):
        tool = ToolSelection(name="flat", diameter=6.0, kind="flat", rpm=14000, feed_xy=900, feed_z=280)
        key = pass_key("profile", tool)
        assert key == ("profile", 6.0, "flat", None, None)
