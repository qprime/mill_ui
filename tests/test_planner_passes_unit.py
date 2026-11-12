from __future__ import annotations

from dataclasses import replace

import pytest
from shapely import get_parts, maximum_inscribed_circle
from shapely.affinity import translate
from shapely.geometry import LineString, box
from shapely.geometry import Point as ShapelyPoint
from shapely.geometry import Polygon as ShapelyPolygon
from shapely.ops import unary_union

from cam.config import Config
from cam.model.machine import Machine
from cam.model.setup import Setup
from cam.model.stock import Stock
from cam.model.tool import Tool
from cam.moves import CutMove, DwellMove, Move, RapidMove, RetractMove, SetFeedMove, SetRpmMove, XYMove
from cam.ops.bore import pocket_circle_concentric
from cam.ops.engrave import engrave_lines
from cam.ops.face import face_zigzag
from cam.ops.pocket import pocket_offset_loops
from cam.planner.params import MIN_STEPDOWN_MM, stepdown_for, stepover_for
from cam.planner.passes import PassAccumulator, plan_passes
from cam.planner.passes.edge import build_edge_cut_plan, plan_edge_feature_passes, vbit_cut_depth, vbit_effective_radius
from cam.planner.passes.merge_shared_edges import _overlap_len, _rect_edges, merge_rect_profiles
from cam.planner.passes.pocket import (
    plan_engrave_passes,
    plan_hole_passes,
    plan_pocket_passes,
)
from cam.planner.passes.summary import _summarise_moves, estimated_runtime_min, summarise_gcode_file
from cam.planner.passes.tools import (
    ToolSelection,
    normalize_tool_entries,
    pass_key,
    pick_tool_for_edge,
    pick_tool_for_engrave,
    pick_tool_for_hole,
    pick_tool_for_pocket,
    pick_tool_for_profile,
    pick_tool_for_region,
    pick_tool_for_roundover,
    stepdown_for_tool,
    stepover_for_tool,
)
from cam.planner.planner_input import (
    EdgeFeatureInput,
    EdgeTreatmentInput,
    FeatureInput,
    GeometryInput,
    IslandInput,
    PlannerInput,
    SurfaceCooling,
)
from ir.removal_intent import (
    BevelSpec,
    Bounds2D,
    ChamferSpec,
    Constraints,
    DepthProfile,
    RemovalIntent,
    RoundoverSpec,
    ShapeGeometry,
    TabConstraint,
)
from layout_ast.layout import FeedsOverride, RestSpec

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
ROUNDOVER_6MM = {
    "name": "6mm_roundover",
    "diameter": 25.4,
    "kind": "roundover",
    "rpm": 16000,
    "feed_xy": 1500,
    "feed_z": 500,
    "roundover_radius_mm": 6.0,
}
ROUNDOVER_10MM = {
    "name": "10mm_roundover",
    "diameter": 25.4,
    "kind": "roundover",
    "rpm": 16000,
    "feed_xy": 1500,
    "feed_z": 500,
    "roundover_radius_mm": 10.0,
}

ALL_TOOLS = normalize_tool_entries([FLAT_3MM, FLAT_6MM, FLAT_6MM_UPCUT, FLAT_12MM, BALL_2MM, V_1MM])
FLAT_ONLY = normalize_tool_entries([FLAT_3MM, FLAT_6MM, FLAT_12MM])
TOOLS_WITH_VBIT = normalize_tool_entries([FLAT_3MM, FLAT_6MM, VBIT_90])
TOOLS_WITH_TWO_VBITS = normalize_tool_entries([FLAT_3MM, VBIT_60, VBIT_90])
TOOLS_WITH_ROUNDOVER = normalize_tool_entries([FLAT_3MM, FLAT_6MM, ROUNDOVER_6MM])
TOOLS_WITH_TWO_ROUNDOVERS = normalize_tool_entries([FLAT_3MM, ROUNDOVER_6MM, ROUNDOVER_10MM])


def _setup(tool_diameter=6.0):
    return Setup(
        stock=Stock(width=300, height=200, thickness=19),
        tool=Tool(name="t", diameter=tool_diameter),
        machine=Machine(),
        safe_z=5.0,
    )


def _accumulator(ramp_angle=3.0):
    return PassAccumulator(
        machine=Machine(),
        stock=Stock(width=300, height=200, thickness=19),
        safe_z=5.0,
        prime_spindle=False,
        ramp_angle_deg=ramp_angle,
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


def _square_ring(width: float) -> ShapelyPolygon:
    inner = 100.0 - width
    return ShapelyPolygon(
        [(-100.0, -100.0), (100.0, -100.0), (100.0, 100.0), (-100.0, 100.0)],
        [[(-inner, -inner), (inner, -inner), (inner, inner), (-inner, inner)]],
    )


class TestPickToolForRegion:
    def test_picks_largest_tool_that_keeps_ring_topology(self):
        tool = pick_tool_for_region(FLAT_ONLY, _square_ring(10.0), cleanup_offset_mm=0.25)
        assert tool is not None
        assert tool.name == "6mm_flat"

    def test_rejects_tool_that_fits_only_ring_corners(self):
        tool = pick_tool_for_region(FLAT_ONLY, _square_ring(12.0), cleanup_offset_mm=0.25)
        assert tool is not None
        assert tool.name == "6mm_flat"

    def test_plain_strip_picks_tool_below_width(self):
        strip = ShapelyPolygon([(0.0, 0.0), (100.0, 0.0), (100.0, 4.0), (0.0, 4.0)])
        tool = pick_tool_for_region(FLAT_ONLY, strip, cleanup_offset_mm=0.25)
        assert tool is not None
        assert tool.name == "3mm_flat"

    def test_empty_region_returns_none(self):
        assert pick_tool_for_region(FLAT_ONLY, ShapelyPolygon(), cleanup_offset_mm=0.25) is None

    def test_returns_none_when_no_tool_fits(self):
        assert pick_tool_for_region(FLAT_ONLY, _square_ring(3.0), cleanup_offset_mm=0.25) is None

    def test_prefers_upcut_like_pick_tool_for_pocket(self):
        tools = normalize_tool_entries([FLAT_6MM, FLAT_6MM_UPCUT, FLAT_12MM])
        tool = pick_tool_for_region(tools, _square_ring(10.0), cleanup_offset_mm=0.25)
        assert tool is not None
        assert tool.name == "6mm_upcut"


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

    def test_stepdown_clamped_from_subfloor_depth_per_pass(self):
        tool = ToolSelection(name="t", diameter=6.0, kind="flat", rpm=1, feed_xy=1, feed_z=1, depth_per_pass=0.001)
        assert stepdown_for_tool(tool) == MIN_STEPDOWN_MM

    def test_stepdown_clamped_from_tiny_diameter(self):
        tool = ToolSelection(name="t", diameter=0.005, kind="flat", rpm=1, feed_xy=1, feed_z=1)
        assert stepdown_for_tool(tool) == MIN_STEPDOWN_MM


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
        edges = _rect_edges(50, 50, 20, 10, 0)
        assert len(edges) == 4

    def test_edge_orientations(self):
        edges = _rect_edges(50, 50, 20, 10, 0)
        v_edges = [e for e in edges if e.orient == "v"]
        h_edges = [e for e in edges if e.orient == "h"]
        assert len(v_edges) == 2
        assert len(h_edges) == 2

    def test_edge_coordinates(self):
        edges = _rect_edges(50, 50, 20, 10, 0)
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


class TestRectangleProfilePlanning:
    @staticmethod
    def _plan(feature, *, merge=True, profile_opts=None):
        features = (feature,) if isinstance(feature, FeatureInput) else tuple(feature)
        return plan_passes(
            PlannerInput(profiles=features, kerf_width_mm=3.0),
            config=Config(merge_epsilon_mm=0.1 if merge else 0.0),
            tool_db=FLAT_ONLY,
            machine=Machine(),
            stock=Stock(300, 200, 19),
            profile_opts=profile_opts,
        )[0]

    @pytest.mark.parametrize("merge", [True, False])
    @pytest.mark.parametrize(
        "side,minimum,maximum", [("inside", 76.5, 123.5), ("outside", 73.5, 126.5), ("on", 75, 125)]
    )
    def test_closed_rectangle_honors_profile_side(self, side, minimum, maximum, merge):
        feature = replace(_feature("Rect", {"w_mm": 50, "h_mm": 30}, (100, 100), 6), side=side)

        (record,) = self._plan(feature, merge=merge)

        xs = [move.x for move in record.moves if isinstance(move, CutMove) and move.x is not None]
        assert min(xs) == pytest.approx(minimum)
        assert max(xs) == pytest.approx(maximum)
        assert record.count == 1

    def test_isolated_rectangle_uses_ramped_closed_profile(self):
        feature = replace(_feature("Rect", {"w_mm": 100, "h_mm": 60}, (100, 100), 6), side="outside")
        (record,) = self._plan(feature)
        x = y = None
        for move in record.moves:
            if not isinstance(move, (RapidMove, CutMove)):
                continue
            target = (move.x if move.x is not None else x, move.y if move.y is not None else y)
            if isinstance(move, CutMove) and move.z is not None and move.z < 0:
                assert target != (x, y)
                break
            x, y = target
        else:
            pytest.fail("Profile has no cutting entry")
        assert record.count == 1

    def test_inside_profile_smaller_than_cutter_fails_explicitly(self):
        feature = replace(_feature("Rect", {"w_mm": 2, "h_mm": 30}, (100, 100), 6), side="inside")

        with pytest.raises(ValueError, match="no positive centerline dimensions"):
            self._plan(feature)

    @pytest.mark.parametrize("holding", ["tabs", "onion_skin_mm"])
    @pytest.mark.parametrize("global_option", [False, True])
    def test_allowances_preserve_holding_through_finish(self, holding, global_option):
        from cam.planner.planner_input import TabsInput

        feature = replace(
            _feature("Rect", {"w_mm": 100, "h_mm": 60}, (100, 100), 19),
            side="outside",
            edge_treatment=EdgeTreatmentInput(type="allowance", rough_allowance_mm=0.5, finish_allowance_mm=0.2),
        )
        options = {
            holding: {"count": 4, "height_mm": 2, "width_mm": 8} if holding == "tabs" else 0.3,
            "cut_through_mm": 0.2,
        }
        if not global_option:
            feature = (
                replace(feature, tabs=TabsInput(4, 2, 8)) if holding == "tabs" else replace(feature, onion_skin_mm=0.3)
            )
            options = {"cut_through_mm": 0.2}

        passes = self._plan(feature, profile_opts=options)

        assert [record.op for record in passes] == (
            ["profile", "profile_finish"] if holding == "tabs" else ["profile", "profile_finish", "release"]
        )
        rough_depth = min(end[2] for _, end in _cut_segments(passes[0].moves))
        assert rough_depth == pytest.approx(-17 if holding == "tabs" else -18.7)
        finish_depth = min(end[2] for _, end in _cut_segments(passes[1].moves))
        assert finish_depth == pytest.approx(-19.2 if holding == "tabs" else -18.7)
        if holding == "onion_skin_mm":
            assert min(end[2] for _, end in _cut_segments(passes[-1].moves)) == pytest.approx(-19.2)

    def test_plain_onion_skin_uses_nominal_depth_and_one_cut_through(self):
        feature = replace(
            _feature("Rect", {"w_mm": 100, "h_mm": 60}, (100, 100), 19), side="outside", onion_skin_mm=0.3
        )

        rough, release = self._plan(feature, profile_opts={"cut_through_mm": 0.2})

        assert rough.op == "profile" and release.op == "release"
        assert min(end[2] for _, end in _cut_segments(rough.moves)) == pytest.approx(-18.7)
        assert min(end[2] for _, end in _cut_segments(release.moves)) == pytest.approx(-19.2)

    @pytest.mark.parametrize("corner_tab", [False, True])
    @pytest.mark.parametrize("allowance", [False, True])
    def test_cutter_footprint_preserves_tabs_during_entry_and_corner_traversal(self, corner_tab, allowance):
        from cam.planner.planner_input import TabsInput

        feature = replace(
            _feature("Rect", {"w_mm": 40 if corner_tab else 30, "h_mm": 40 if corner_tab else 20}, (100, 100), 19),
            side="outside",
            tabs=TabsInput(1 if corner_tab else 4, 2, 10),
        )
        bridges = (
            [box(121.25, 118.75, 121.75, 119.25), box(118.75, 121.25, 119.25, 121.75)]
            if corner_tab
            else [
                box(97.25, 88.25, 97.75, 88.75),
                box(116.25, 97.25, 116.75, 97.75),
                box(102.25, 111.25, 102.75, 111.75),
                box(83.25, 102.25, 83.75, 102.75),
            ]
        )

        if allowance:
            feature = replace(
                feature,
                edge_treatment=EdgeTreatmentInput(type="allowance", rough_allowance_mm=0.5, finish_allowance_mm=0.0),
            )
        passes = self._plan(feature, profile_opts={"cut_through_mm": 0.2})

        for start, end in _cut_segments([move for record in passes for move in record.moves]):
            if min(start[2], end[2]) < -17 - 1e-6:
                swept = LineString([start[:2], end[:2]]).buffer(1.5)
                assert all(swept.intersection(bridge).area < 1e-6 for bridge in bridges)

    @pytest.mark.parametrize(
        "shape,geometry",
        [
            ("Rect", {"w_mm": 80, "h_mm": 50}),
            ("Circle", {"diameter_mm": 60}),
            ("Polygon", {"points": [(-40, -25), (40, -25), (30, 25), (-30, 25)]}),
            ("RoundedRect", {"w_mm": 80, "h_mm": 50}),
        ],
    )
    @pytest.mark.parametrize("side", ["inside", "outside"])
    @pytest.mark.parametrize("holding", ["tabs", "onion"])
    def test_all_shape_paths_share_holding_schedule(self, shape, geometry, side, holding):
        from cam.planner.planner_input import TabsInput

        feature = _feature(shape, geometry, (100, 100), 19)
        feature = replace(
            feature,
            geometry=replace(feature.geometry, geometry=replace(feature.geometry.geometry, radius_mm=5)),
            side=side,
            edge_treatment=EdgeTreatmentInput(type="allowance", rough_allowance_mm=0.5, finish_allowance_mm=0),
            tabs=TabsInput(4, 2, 8) if holding == "tabs" else None,
            onion_skin_mm=0.3 if holding == "onion" else None,
            feeds_override=FeedsOverride(rpm=12000, feed_xy=650, depth_per_pass=1),
        )

        passes = self._plan(feature, profile_opts={"cut_through_mm": 0.2})

        assert [p.op for p in passes] == (
            ["profile", "profile_finish"] if holding == "tabs" else ["profile", "profile_finish", "release"]
        )
        assert all(move.rpm == 12000 for p in passes for move in p.moves if isinstance(move, SetRpmMove))
        assert all(move.feed == 650 for p in passes for move in p.moves if isinstance(move, SetFeedMove))
        assert min(end[2] for _, end in _cut_segments(passes[0].moves)) == pytest.approx(
            -17 if holding == "tabs" else -18.7
        )
        assert min(end[2] for _, end in _cut_segments(passes[-1].moves)) == pytest.approx(-19.2)

    @pytest.mark.parametrize("per_tool", [False, True])
    def test_release_stays_after_other_tool_finishing_in_output_groups(self, per_tool):
        from cam.pipeline import gcode_file_groups

        feature = replace(
            _feature("Rect", {"w_mm": 100, "h_mm": 60}, (100, 100), 19),
            side="outside",
            onion_skin_mm=0.3,
            edge_treatment=EdgeTreatmentInput(type="allowance", rough_allowance_mm=0.5, finish_allowance_mm=0),
        )
        passes = self._plan(feature, profile_opts={"cut_through_mm": 0.2})
        other_acc = _accumulator()
        other_finish = other_acc.get_record("finish", normalize_tool_entries([FLAT_6MM])[0])
        records = [*passes[:-1], other_finish, passes[-1]]

        groups = gcode_file_groups(records, per_tool=per_tool)

        assert groups[-1][0].startswith("release-")
        assert all(p.op == "release" for p in groups[-1][1])
        assert all(p.op != "release" for _, group in groups[:-1] for p in group)

    @pytest.mark.parametrize("side,rough_min,finish_min", [("outside", 73.0, 73.3), ("inside", 77.0, 76.7)])
    def test_allowances_and_feed_overrides_survive_dispatch(self, side, rough_min, finish_min):
        feature = replace(
            _feature("Rect", {"w_mm": 50, "h_mm": 30}, (100, 100), 6),
            side=side,
            feeds_override=FeedsOverride(feed_xy=650, feed_z=120, depth_per_pass=1),
            edge_treatment=EdgeTreatmentInput(type="allowance", rough_allowance_mm=0.5, finish_allowance_mm=0.2),
        )

        passes = self._plan(feature)

        assert [record.op for record in passes] == ["profile", "finish"]
        for record, expected_min in zip(passes, [rough_min, finish_min], strict=True):
            xs = [move.x for move in record.moves if isinstance(move, CutMove) and move.x is not None]
            assert min(xs) == pytest.approx(expected_min)
            assert record.tool_selection.feed_xy == 650
            assert record.tool_selection.feed_z == 120
            assert record.tool_selection.depth_per_pass == 1
            assert record.count == 1

    @pytest.mark.parametrize("offset_y", [0.0, 20.0])
    @pytest.mark.parametrize("transpose", [False, True])
    def test_shared_cut_preserves_both_nominal_rectangles(self, offset_y, transpose):
        a = replace(_feature("Rect", {"w_mm": 100, "h_mm": 60}, (60, 80), 6, id="a"), side="outside")
        b = replace(a, id="b", center_xy_mm=(163, 80 + offset_y))
        materials: tuple[ShapelyPolygon, ...] = (box(10, 50, 110, 110), box(113, 50 + offset_y, 213, 110 + offset_y))
        if transpose:
            geometry = GeometryInput(shape="Rect", geometry=ShapeGeometry(w_mm=60, h_mm=100))
            a, b = (replace(p, center_xy_mm=p.center_xy_mm[::-1], geometry=geometry) for p in (a, b))
            materials = tuple(
                box(region.bounds[1], region.bounds[0], region.bounds[3], region.bounds[2]) for region in materials
            )

        (record,) = self._plan((a, b))

        assert record.count == 2
        shared = []
        axis = int(transpose)
        along = 1 - axis
        seam_start = max(region.bounds[along] for region in materials) - 1.5
        seam_end = min(region.bounds[along + 2] for region in materials) + 1.5
        for start, end in _cut_segments(record.moves):
            if min(start[2], end[2]) >= 0:
                continue
            line = LineString([start[:2], end[:2]])
            for material in materials:
                assert line.buffer(1.5).intersection(material).area < 1e-6
            if (
                abs(start[axis] - 111.5) < 1e-9
                and abs(end[axis] - 111.5) < 1e-9
                and start[along] != end[along]
                and min(start[along], end[along]) >= seam_start - 1e-9
                and max(start[along], end[along]) <= seam_end + 1e-9
            ):
                shared.append((start, end))
        assert shared
        assert len({end[2] for _, end in shared}) == len(shared)

    @pytest.mark.parametrize("ring", [False, True])
    def test_connected_groups_preserve_all_seams_and_hole_boundaries(self, ring):
        cells = ((x, y) for x in range(3 if ring else 2) for y in range(3 if ring else 2))
        profiles = tuple(
            replace(
                _feature("Rect", {"w_mm": 100, "h_mm": 60}, (60 + x * 103, 50 + y * 63), 6, id=f"{x},{y}"),
                side="outside",
            )
            for x, y in cells
            if not ring or (x, y) != (1, 1)
        )

        (group,) = merge_rect_profiles(profiles, tool_diameter_mm=3, config=Config())

        assert group.profile_indices == tuple(range(len(profiles)))
        assert len(group.seams) == (8 if ring else 4)
        assert len(group.outlines) == (2 if ring else 1)
        assert all(shape.points[0] == shape.points[-1] for shape in group.outlines)

    def test_clearance_uses_selected_tool_instead_of_requested_kerf(self):
        a = replace(_feature("Rect", {"w_mm": 100, "h_mm": 60}, (60, 80), 6, id="a"), side="outside")
        b = replace(a, id="b", center_xy_mm=(164, 80))

        with pytest.raises(ValueError, match=r"need 6\.000000mm"):
            plan_passes(
                PlannerInput(profiles=(a, b), kerf_width_mm=3),
                config=Config(),
                tool_db=normalize_tool_entries([FLAT_6MM]),
                machine=Machine(),
                stock=Stock(300, 200, 19),
            )

    @pytest.mark.parametrize("gap", [0.0, 1.0, 2.99])
    @pytest.mark.parametrize("merge", [True, False])
    def test_insufficient_kerf_gap_is_rejected(self, gap, merge):
        a = replace(_feature("Rect", {"w_mm": 100, "h_mm": 60}, (60, 80), 6, id="a"), side="outside")
        b = replace(a, id="b", center_xy_mm=(160 + gap, 80))

        with pytest.raises(ValueError, match="preserve nominal dimensions"):
            self._plan((a, b), merge=merge)

    def test_nearby_offset_centerlines_are_not_snapped_together(self):
        a = replace(_feature("Rect", {"w_mm": 100, "h_mm": 60}, (60, 80), 6, id="a"), side="outside")
        b = replace(a, id="b", center_xy_mm=(163.05, 80))

        (record,) = self._plan((a, b))

        assert record.count == 2
        xs = {move.x for move in record.moves if isinstance(move, CutMove) and move.x is not None}
        assert any(abs(x - 111.5) < 1e-9 for x in xs)
        assert any(abs(x - 111.55) < 1e-9 for x in xs)

    @pytest.mark.parametrize("gap,valid", [(3.5, False), (3.75, True)])
    def test_clearance_reserves_both_parts_allowance_stock(self, gap, valid):
        a = replace(
            _feature("Rect", {"w_mm": 100, "h_mm": 60}, (60, 80), 6, id="a"),
            side="outside",
            edge_treatment=EdgeTreatmentInput(type="allowance", rough_allowance_mm=0.5),
        )
        b = replace(
            a,
            id="b",
            center_xy_mm=(160 + gap, 80),
            edge_treatment=EdgeTreatmentInput(type="allowance", rough_allowance_mm=0.25),
        )

        if valid:
            assert [record.count for record in self._plan((a, b))] == [2, 2]
        else:
            with pytest.raises(ValueError, match="after profile allowances"):
                self._plan((a, b))

    def test_mixed_profile_overrides_use_each_features_setup(self):
        a = replace(_feature("Rect", {"w_mm": 50, "h_mm": 30}, (60, 80), 6, id="a"), side="outside")
        b = replace(
            a, id="b", center_xy_mm=(163, 80), feeds_override=FeedsOverride(rpm=12000, feed_xy=650, depth_per_pass=1)
        )

        (record,) = self._plan((a, b))

        assert [move.rpm for move in record.moves if isinstance(move, SetRpmMove)] == [18000, 12000]
        feeds = {move.feed for move in record.moves if isinstance(move, SetFeedMove)}
        assert feeds == {1000, 650}

    @pytest.mark.parametrize("option", ["depth", "feeds", "allowance", "tabs", "onion_skin"])
    def test_incompatible_profiles_do_not_share_seams(self, option):
        from cam.planner.planner_input import TabsInput

        a = replace(_feature("Rect", {"w_mm": 100, "h_mm": 60}, (60, 80), 6, id="a"), side="outside")
        b = replace(a, id="b", center_xy_mm=(163, 80))
        if option == "depth":
            b = replace(b, depth_mm=3)
        elif option == "feeds":
            b = replace(b, feeds_override=FeedsOverride(feed_xy=650))
        elif option == "allowance":
            b = replace(
                b, edge_treatment=EdgeTreatmentInput(type="allowance", rough_allowance_mm=0, finish_allowance_mm=0)
            )
        elif option == "tabs":
            b = replace(b, tabs=TabsInput(count=4, height_mm=2, width_mm=8))
        else:
            b = replace(b, onion_skin_mm=0.3)
        passes, summary, _, _ = plan_passes(
            PlannerInput(profiles=(a, b), kerf_width_mm=3),
            config=Config(),
            tool_db=FLAT_ONLY,
            machine=Machine(),
            stock=Stock(300, 200, 19),
        )

        assert passes
        assert summary["merged_seams"] == 0


_RING_CENTER = (150.0, 100.0)


def _ring_feature(width: float, *, id: str = "ring", **kwargs) -> FeatureInput:
    ring = _square_ring(width)
    shape_geometry = ShapeGeometry(
        points=tuple((float(x), float(y)) for x, y in ring.exterior.coords[:-1]),
        holes=tuple(tuple((float(x), float(y)) for x, y in interior.coords[:-1]) for interior in ring.interiors),
    )
    return FeatureInput(
        id=id,
        shape="Polygon",
        geometry=GeometryInput(shape="Polygon", geometry=shape_geometry),
        center_xy_mm=_RING_CENTER,
        depth_mm=3.0,
        **kwargs,
    )


def _placed_ring(width: float) -> ShapelyPolygon:
    return translate(_square_ring(width), *_RING_CENTER)


def _cut_segments(moves) -> list[tuple[tuple[float, float, float], tuple[float, float, float]]]:
    x: float | None = None
    y: float | None = None
    z: float | None = None
    segments: list[tuple[tuple[float, float, float], tuple[float, float, float]]] = []
    for move in moves:
        if isinstance(move, (RapidMove, CutMove)):
            px, py, pz = x, y, z
            x = move.x if move.x is not None else x
            y = move.y if move.y is not None else y
            z = move.z if move.z is not None else z
            if (
                isinstance(move, CutMove)
                and px is not None
                and py is not None
                and pz is not None
                and x is not None
                and y is not None
                and z is not None
            ):
                segments.append(((px, py, pz), (x, y, z)))
        elif isinstance(move, RetractMove):
            z = move.z
    return segments


def _cut_positions(moves) -> list[tuple[float, float, float]]:
    return [end for _, end in _cut_segments(moves) if end[2] < 0.0]


class TestPlanPocketPasses:
    @pytest.mark.parametrize("ramp_angle", [0.0, 3.0])
    @pytest.mark.parametrize("width,height", [(80.0, 40.0), (40.0, 80.0)])
    def test_spiral_clears_the_complete_machinable_pocket_at_every_depth(self, ramp_angle, width, height):
        acc = _accumulator(ramp_angle)
        pocket = _feature("Rect", {"w_mm": width, "h_mm": height}, (100, 100), 6)
        plan_pocket_passes((pocket,), accumulator=acc, tool_db=FLAT_ONLY, config=Config(ramp_angle_deg=ramp_angle))
        (record,) = acc.passes()
        radius = record.tool_selection.diameter / 2
        nominal = box(100 - width / 2, 100 - height / 2, 100 + width / 2, 100 + height / 2)
        machinable = nominal.buffer(-radius, join_style="mitre").buffer(radius, quad_segs=64)
        for depth in [-3.0, -6.0]:
            segments = [
                LineString([a[:2], b[:2]])
                for a, b in _cut_segments(record.moves)
                if abs(a[2] - depth) < 1e-8 and abs(b[2] - depth) < 1e-8 and a[:2] != b[:2]
            ]
            removed = unary_union(segments).buffer(radius, quad_segs=64)
            assert machinable.difference(removed.buffer(1e-7)).area < 1e-5
            assert removed.difference(nominal.buffer(1e-7)).area < 1e-5

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

    def test_holed_polygon_pocket_stays_out_of_hole(self):
        acc = _accumulator()
        plan_pocket_passes((_ring_feature(10.0),), accumulator=acc, tool_db=FLAT_ONLY, config=Config())
        (record,) = acc.passes()
        radius = record.tool_selection.diameter / 2.0
        region = _placed_ring(10.0)
        positions = _cut_positions(record.moves)
        assert positions
        for x, y, _ in positions:
            point = ShapelyPoint(x, y)
            assert region.contains(point)
            assert region.boundary.distance(point) >= radius - 1e-6

    def test_holed_polygon_pocket_clears_ring(self):
        tools = normalize_tool_entries([{**FLAT_12MM, "stepover_percent": 90.0}])
        acc = _accumulator()
        plan_pocket_passes((_ring_feature(30.0),), accumulator=acc, tool_db=tools, config=Config())
        (record,) = acc.passes()
        radius = record.tool_selection.diameter / 2.0
        cuts = _cut_segments(record.moves)
        final_z = min(end[2] for _, end in cuts)
        segments = [
            LineString([(ax, ay), (bx, by)]).buffer(radius)
            for (ax, ay, az), (bx, by, bz) in cuts
            if az == final_z and bz == final_z and (ax, ay) != (bx, by)
        ]
        uncut = _placed_ring(30.0).difference(unary_union(segments))
        worst = max((maximum_inscribed_circle(piece).length for piece in get_parts(uncut)), default=0.0)
        assert worst <= 0.1716 * radius + 0.01

    def test_narrow_polygon_pocket_uses_small_tool(self):
        acc = _accumulator()
        strip = _feature("Polygon", {"points": [[-50, -2], [50, -2], [50, 2], [-50, 2]]}, (150.0, 100.0), 3.0)
        plan_pocket_passes((strip,), accumulator=acc, tool_db=FLAT_ONLY, config=Config())
        (record,) = acc.passes()
        assert record.tool_selection.diameter == 3.0
        assert _cut_positions(record.moves)

    def test_plain_concave_polygon_pocket_clears_walls(self):
        acc = _accumulator()
        l_points = [[-50, -50], [50, -50], [50, -10], [-10, -10], [-10, 50], [-50, 50]]
        pocket = _feature("Polygon", {"points": l_points}, _RING_CENTER, 3.0)
        plan_pocket_passes((pocket,), accumulator=acc, tool_db=FLAT_ONLY, config=Config())
        (record,) = acc.passes()
        radius = record.tool_selection.diameter / 2.0
        region = translate(ShapelyPolygon(l_points), *_RING_CENTER)
        positions = _cut_positions(record.moves)
        assert positions
        for x, y, _ in positions:
            point = ShapelyPoint(x, y)
            assert region.contains(point)
            assert region.boundary.distance(point) >= radius - 1e-6

    def test_polygon_pocket_without_fitting_tool_warns_and_skips(self):
        acc = _accumulator()
        plan_pocket_passes((_ring_feature(3.0),), accumulator=acc, tool_db=FLAT_ONLY, config=Config())
        assert acc.passes() == []
        (warning,) = acc.warnings
        assert "no flat tool in the tool library fits" in warning
        assert "3.000 mm" in warning

    def test_rect_pocket_without_fitting_tool_warns_and_skips(self):
        acc = _accumulator()
        pocket = _feature("Rect", {"w_mm": 2.5, "h_mm": 50.0}, (150.0, 100.0), 3.0)
        plan_pocket_passes((pocket,), accumulator=acc, tool_db=FLAT_ONLY, config=Config())
        assert acc.passes() == []
        (warning,) = acc.warnings
        assert "no flat tool in the tool library fits" in warning

    def test_circle_pocket_without_fitting_tool_warns_and_skips(self):
        acc = _accumulator()
        pocket = _feature("Circle", {"diameter_mm": 3.0}, (150.0, 100.0), 3.0)
        plan_pocket_passes((pocket,), accumulator=acc, tool_db=FLAT_ONLY, config=Config())
        assert acc.passes() == []
        (warning,) = acc.warnings
        assert "no flat tool in the tool library fits" in warning

    def test_rect_pocket_just_wider_than_tool_still_cuts(self):
        acc = _accumulator()
        pocket = _feature("Rect", {"w_mm": 6.4, "h_mm": 50.0}, (150.0, 100.0), 3.0)
        plan_pocket_passes((pocket,), accumulator=acc, tool_db=normalize_tool_entries([FLAT_6MM]), config=Config())
        (record,) = acc.passes()
        assert _cut_positions(record.moves)
        assert acc.warnings == []

    def test_rect_pocket_with_island_stays_out_of_island(self):
        acc = _accumulator()
        island = IslandInput(x_min=120.0, x_max=180.0, y_min=70.0, y_max=130.0)
        pocket = replace(_feature("Rect", {"w_mm": 200.0, "h_mm": 160.0}, _RING_CENTER, 3.0), islands=(island,))
        plan_pocket_passes((pocket,), accumulator=acc, tool_db=FLAT_ONLY, config=Config())
        (record,) = acc.passes()
        radius = record.tool_selection.diameter / 2.0
        region = box(50.0, 20.0, 250.0, 180.0).difference(box(120.0, 70.0, 180.0, 130.0))
        positions = _cut_positions(record.moves)
        assert positions
        for x, y, _ in positions:
            point = ShapelyPoint(x, y)
            assert region.contains(point)
            assert region.boundary.distance(point) >= radius - 1e-6

    def test_islands_covering_pocket_warn_and_skip(self):
        acc = _accumulator()
        island = IslandInput(x_min=0.0, x_max=300.0, y_min=0.0, y_max=200.0)
        pocket = replace(
            _feature("Rect", {"w_mm": 50.0, "h_mm": 50.0}, _RING_CENTER, 3.0, id="covered"), islands=(island,)
        )
        plan_pocket_passes((pocket,), accumulator=acc, tool_db=FLAT_ONLY, config=Config())
        assert acc.passes() == []
        assert acc.warnings == ["Pocket 'covered': islands cover the whole pocket — feature skipped"]

    def test_holed_polygon_with_surface_cooling_raises(self):
        acc = _accumulator()
        pocket = _ring_feature(10.0, id="cooled_ring", surface_cooling=SurfaceCooling())
        with pytest.raises(ValueError, match="Pocket 'cooled_ring': holes are not supported with surface_cooling"):
            plan_pocket_passes((pocket,), accumulator=acc, tool_db=FLAT_ONLY, config=Config())

    def test_polygon_allowance_stays_inside_polygon(self):
        acc = _accumulator()
        l_points = [[-50, -50], [50, -50], [50, -10], [-10, -10], [-10, 50], [-50, 50]]
        pocket = replace(
            _feature("Polygon", {"points": l_points}, _RING_CENTER, 3.0),
            edge_treatment=EdgeTreatmentInput(type="allowance", rough_allowance_mm=0.5, finish_allowance_mm=0.1),
        )
        plan_pocket_passes((pocket,), accumulator=acc, tool_db=FLAT_ONLY, config=Config())
        records = {record.op: record for record in acc.passes()}
        region = translate(ShapelyPolygon(l_points), *_RING_CENTER)
        radius = records["pocket"].tool_selection.diameter / 2.0
        rough = _cut_positions(records["pocket"].moves)
        finish = _cut_positions(records["finish"].moves)
        assert rough
        assert finish
        for x, y, _ in rough:
            point = ShapelyPoint(x, y)
            assert region.contains(point)
            assert region.boundary.distance(point) >= radius + 0.5 - 1e-6
        for x, y, _ in finish:
            point = ShapelyPoint(x, y)
            assert region.contains(point)
            assert region.boundary.distance(point) == pytest.approx(radius + 0.1, abs=1e-6)

    def test_holed_polygon_allowance_leaves_stock_then_finishes(self):
        acc = _accumulator()
        pocket = _ring_feature(
            30.0, edge_treatment=EdgeTreatmentInput(type="allowance", rough_allowance_mm=0.5, finish_allowance_mm=0.0)
        )
        plan_pocket_passes((pocket,), accumulator=acc, tool_db=FLAT_ONLY, config=Config())
        records = {record.op: record for record in acc.passes()}
        region = _placed_ring(30.0)
        radius = records["pocket"].tool_selection.diameter / 2.0
        rough_distances = [
            region.boundary.distance(ShapelyPoint(x, y)) for x, y, _ in _cut_positions(records["pocket"].moves)
        ]
        finish_distances = [
            region.boundary.distance(ShapelyPoint(x, y)) for x, y, _ in _cut_positions(records["finish"].moves)
        ]
        assert min(rough_distances) >= radius + 0.5 - 1e-6
        assert min(finish_distances) == pytest.approx(radius, abs=1e-6)

    def test_island_splitting_pocket_cuts_both_regions(self):
        acc = _accumulator()
        island = IslandInput(x_min=130.0, x_max=170.0, y_min=0.0, y_max=200.0)
        pocket = replace(_feature("Rect", {"w_mm": 200.0, "h_mm": 100.0}, (150.0, 100.0), 3.0), islands=(island,))
        plan_pocket_passes((pocket,), accumulator=acc, tool_db=FLAT_ONLY, config=Config())
        (record,) = acc.passes()
        radius = record.tool_selection.diameter / 2.0
        region = box(50.0, 50.0, 250.0, 150.0).difference(box(130.0, 0.0, 170.0, 200.0))
        positions = _cut_positions(record.moves)
        assert any(x < 130.0 for x, _, _ in positions)
        assert any(x > 170.0 for x, _, _ in positions)
        for x, y, _ in positions:
            point = ShapelyPoint(x, y)
            assert region.contains(point)
            assert region.boundary.distance(point) >= radius - 1e-6


_TRIANGLE_CENTER = (150.0, 100.0)
_TRIANGLE_POINTS = [(-50.0, -20.0), (50.0, -20.0), (-30.0, 20.0)]


def _rest_triangle(**kwargs) -> FeatureInput:
    pocket: FeatureInput = _feature("Polygon", {"points": _TRIANGLE_POINTS}, _TRIANGLE_CENTER, 3.0, id="tri")
    return replace(pocket, rest=RestSpec(tool_diameter_mm=3.0), **kwargs)


def _placed_triangle() -> ShapelyPolygon:
    return translate(ShapelyPolygon(_TRIANGLE_POINTS), *_TRIANGLE_CENTER)


def _swept_area(record):
    radius = record.tool_selection.diameter / 2.0
    lines = [LineString([a[:2], b[:2]]) for a, b in _cut_segments(record.moves) if b[2] < 0.0 and a[:2] != b[:2]]
    return unary_union(lines).buffer(radius)


def _assert_clear_of_walls(record, region, clearance: float) -> None:
    positions = _cut_positions(record.moves)
    assert positions
    for x, y, _ in positions:
        point = ShapelyPoint(x, y)
        assert region.contains(point)
        assert region.boundary.distance(point) >= clearance - 1e-6


class TestRegionRestPocket:
    def _plan(self, pocket: FeatureInput) -> PassAccumulator:
        acc: PassAccumulator = _accumulator()
        plan_pocket_passes((pocket,), accumulator=acc, tool_db=FLAT_ONLY, config=Config())
        return acc

    def _records(self, acc: PassAccumulator) -> dict:
        return {record.op: record for record in acc.passes()}

    def test_polygon_rest_stays_inside_polygon(self):
        records = self._records(self._plan(_rest_triangle()))
        assert set(records) == {"pocket", "pocket_rest"}
        assert records["pocket"].tool_selection.diameter == 12.0
        assert records["pocket_rest"].tool_selection.diameter == 3.0
        _assert_clear_of_walls(records["pocket"], _placed_triangle(), 6.0 + 0.5)
        _assert_clear_of_walls(records["pocket_rest"], _placed_triangle(), 1.5)

    def test_polygon_rest_clears_reachable_corners(self):
        records = self._records(self._plan(_rest_triangle()))
        cut = unary_union([_swept_area(record) for record in records.values()])
        target = _placed_triangle().buffer(-1.5, join_style="round").buffer(1.5, join_style="round")
        assert target.difference(cut).buffer(-0.02).is_empty

    def test_polygon_rest_is_cheaper_than_full_small_pocket(self):
        rest = self._records(self._plan(_rest_triangle()))["pocket_rest"]
        full = pocket_offset_loops(
            _placed_triangle(),
            rest.setup,
            depth_mm=3.0,
            stepover=stepover_for_tool(rest.tool_selection),
            stepdown=stepdown_for_tool(rest.tool_selection),
        )
        assert len(_cut_segments(rest.moves)) < len(_cut_segments(full))

    def test_polygon_rest_skips_rest_pass_when_nothing_remains(self):
        disc = [(float(x), float(y)) for x, y in ShapelyPoint(0.0, 0.0).buffer(40.0).exterior.coords[:-1]]
        pocket = replace(
            _feature("Polygon", {"points": disc}, _TRIANGLE_CENTER, 3.0, id="disc"),
            rest=RestSpec(tool_diameter_mm=3.0, rough_allowance_mm=0.0),
        )
        acc = self._plan(pocket)
        (record,) = acc.passes()
        assert record.op == "pocket"
        assert record.tool_selection.diameter == 12.0
        assert acc.warnings == []

    def test_polygon_rest_falls_back_when_no_larger_tool_fits(self):
        square = [(-3.0, -3.0), (3.0, -3.0), (3.0, 3.0), (-3.0, 3.0)]
        pocket = replace(
            _feature("Polygon", {"points": square}, _TRIANGLE_CENTER, 3.0, id="small"),
            rest=RestSpec(tool_diameter_mm=3.0),
        )
        acc = self._plan(pocket)
        (record,) = acc.passes()
        assert record.op == "pocket"
        assert record.tool_selection.diameter == 3.0
        assert acc.warnings == []
        _assert_clear_of_walls(record, translate(ShapelyPolygon(square), *_TRIANGLE_CENTER), 1.5)

    def test_holed_polygon_with_rest_cuts_around_hole(self):
        records = self._records(self._plan(_ring_feature(20.0, id="rest_ring", rest=RestSpec(tool_diameter_mm=3.0))))
        assert set(records) == {"pocket", "pocket_rest"}
        _assert_clear_of_walls(records["pocket"], _placed_ring(20.0), 6.0 + 0.5)
        _assert_clear_of_walls(records["pocket_rest"], _placed_ring(20.0), 1.5)

    def test_rect_with_island_and_rest_cuts_around_island(self):
        island = IslandInput(x_min=120.0, x_max=180.0, y_min=70.0, y_max=130.0)
        pocket = replace(
            _feature("Rect", {"w_mm": 200.0, "h_mm": 160.0}, _RING_CENTER, 3.0, id="rest_rect"),
            islands=(island,),
            rest=RestSpec(tool_diameter_mm=3.0),
        )
        records = self._records(self._plan(pocket))
        region = box(50.0, 20.0, 250.0, 180.0).difference(box(120.0, 70.0, 180.0, 130.0))
        assert set(records) == {"pocket", "pocket_rest"}
        _assert_clear_of_walls(records["pocket"], region, 6.0 + 0.5)
        _assert_clear_of_walls(records["pocket_rest"], region, 1.5)

    def test_polygon_rest_with_allowance_edge_treatment_raises(self):
        pocket = _rest_triangle(
            edge_treatment=EdgeTreatmentInput(type="allowance", rough_allowance_mm=0.5, finish_allowance_mm=0.0)
        )
        with pytest.raises(ValueError, match="Cannot combine"):
            self._plan(pocket)


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
    @pytest.mark.parametrize("ramp", [None, 10.0])
    def test_ir_start_depth_offsets_cutting_but_preserves_safe_z(self, ramp):
        from adapters.removal_to_planner import _intent_to_feature_input

        intent = RemovalIntent(
            region_id="engrave_floor",
            bounds=Bounds2D(50, 150, 50, 50),
            depth_profile=DepthProfile.constant(z_top=-4, z_bottom=-7),
            hint_type="engrave",
            shape="Line",
            shape_geometry=ShapeGeometry(start=(-50, 0), end=(50, 0)),
            ramp_mm=ramp,
        )
        acc = _accumulator()
        plan_engrave_passes((_intent_to_feature_input(intent),), accumulator=acc, tool_db=ALL_TOOLS)
        moves = acc.passes()[0].moves
        zs = [m.z for m in moves if isinstance(m, CutMove) and m.z is not None]
        assert min(zs) == -7
        assert max(zs) == (-4 if ramp is not None else -7)
        assert all(m.z == 5 for m in moves if isinstance(m, (RapidMove, RetractMove)))

    @pytest.mark.parametrize("ramp", [None, 5.0])
    def test_grouped_engraving_keeps_each_features_feeds_and_rpm(self, ramp):
        base = _feature("Line", {"start": [0, 0], "end": [20, 0]}, (50, 50), 1)
        first = replace(base, ramp_mm=ramp, feeds_override=FeedsOverride(rpm=8000, feed_xy=120, feed_z=40))
        second = replace(base, ramp_mm=ramp, feeds_override=FeedsOverride(rpm=10000, feed_xy=250, feed_z=80))
        third = replace(base, ramp_mm=ramp)
        acc = _accumulator()
        plan_engrave_passes((first, second, third), accumulator=acc, tool_db=ALL_TOOLS)
        records = acc.passes()
        assert len(records) == 1
        assert records[0].count == 3
        moves = records[0].moves
        assert [m.rpm for m in moves if isinstance(m, SetRpmMove)] == [8000, 10000, V_1MM["rpm"]]
        assert [m.feed for m in moves if isinstance(m, SetFeedMove)] == [
            120,
            120,
            250,
            250,
            V_1MM["feed_xy"],
            V_1MM["feed_xy"],
        ]
        assert [m.feed for m in moves if isinstance(m, CutMove) and m.feed is not None] == [40, 80, V_1MM["feed_z"]]

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
    @pytest.mark.parametrize("side", ["inside", "outside"])
    def test_chamfer_tip_follows_nominal_edge_and_reaches_declared_cross_section(self, side):
        entry = _edge_feature(
            "Rect", {"w_mm": 50, "h_mm": 30}, (100, 75), 6, ChamferSpec(width_mm=6, angle_deg=45), side=side
        )
        plan = build_edge_cut_plan(entry, TOOLS_WITH_TWO_VBITS)
        assert plan.tool.v_angle_deg == 90
        assert plan.depth_mm == pytest.approx(6)
        assert min(p.x for p in plan.shape.points) == pytest.approx(75)
        assert max(p.x for p in plan.shape.points) == pytest.approx(125)
        assert vbit_effective_radius(plan.depth_mm, plan.tool.v_angle_deg) == pytest.approx(6)

    def test_chamfer_angle_is_measured_from_the_stock_surface(self):
        tools = normalize_tool_entries([VBIT_60, VBIT_90, {**VBIT_90, "name": "120deg_v", "v_angle_deg": 120}])
        entry = _edge_feature("Rect", {"w_mm": 50, "h_mm": 30}, (100, 75), 2, ChamferSpec(width_mm=2, angle_deg=30))
        plan = build_edge_cut_plan(entry, tools)
        assert plan.tool.v_angle_deg == 120
        assert plan.depth_mm == pytest.approx(2 / 3**0.5)
        assert vbit_effective_radius(plan.depth_mm, plan.tool.v_angle_deg) == pytest.approx(2)

    def test_chamfer_rejects_nearest_bit_that_would_change_width(self):
        entry = _edge_feature("Rect", {"w_mm": 50, "h_mm": 30}, (100, 75), 2, ChamferSpec(width_mm=2, angle_deg=30))
        with pytest.raises(ValueError, match="cannot cut requested chamfer"):
            build_edge_cut_plan(entry, TOOLS_WITH_TWO_VBITS)

    def test_chamfer_must_fit_the_selected_cutter_radius(self):
        entry = _edge_feature("Rect", {"w_mm": 50, "h_mm": 30}, (100, 75), 8, ChamferSpec(width_mm=8, angle_deg=45))
        with pytest.raises(ValueError, match="exceeds cutter radius"):
            build_edge_cut_plan(entry, TOOLS_WITH_VBIT)

    @pytest.mark.parametrize("angle", [0, 90, -5])
    def test_chamfer_rejects_invalid_surface_angle(self, angle):
        entry = _edge_feature("Rect", {"w_mm": 50, "h_mm": 30}, (100, 75), 2, ChamferSpec(width_mm=2, angle_deg=angle))
        with pytest.raises(ValueError, match="chamfer angle"):
            build_edge_cut_plan(entry, TOOLS_WITH_VBIT)

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

    @pytest.mark.parametrize(
        "spec,shape,tools,message",
        [
            (None, "Rect", TOOLS_WITH_VBIT, "no edge_feature spec"),
            ("invalid", "Rect", TOOLS_WITH_VBIT, "unknown spec type"),
            (ChamferSpec(width_mm=2, angle_deg=45), "Rect", FLAT_ONLY, "no V-bit with 90.0°"),
            (
                ChamferSpec(width_mm=2, angle_deg=45),
                "Rect",
                normalize_tool_entries([{**VBIT_90, "v_angle_deg": 0}]),
                "v_angle_deg must be positive",
            ),
            (ChamferSpec(width_mm=2, angle_deg=45), "Hexagon", TOOLS_WITH_VBIT, "unsupported shape"),
            (RoundoverSpec(radius_mm=6.0), "Rect", FLAT_ONLY, "no roundover bit with 6.0mm radius"),
            (RoundoverSpec(radius_mm=6), "Hexagon", TOOLS_WITH_ROUNDOVER, "unsupported shape"),
            (ChamferSpec(width_mm=0, angle_deg=45), "Rect", TOOLS_WITH_VBIT, "cut depth must be positive"),
        ],
    )
    def test_unmachinable_edge_is_an_error(self, spec, shape, tools, message):
        acc = _accumulator()
        entry = _edge_feature(shape, {"w_mm": 50, "h_mm": 30}, (100, 75), 6, spec, id="required_edge")

        plan_edge_feature_passes((entry,), accumulator=acc, tool_db=tools)

        assert len(acc.errors) == 1
        assert "required_edge" in acc.errors[0]
        assert message in acc.errors[0]
        assert not acc.warnings
        assert not acc.passes()

    def test_collects_each_edge_error_and_retains_valid_passes(self):
        acc = _accumulator()
        base = _edge_feature(
            "Rect", {"w_mm": 50, "h_mm": 30}, (100, 75), 6, ChamferSpec(width_mm=2, angle_deg=45), id="valid"
        )
        missing_tool = replace(base, id="missing_tool", edge_feature=RoundoverSpec(radius_mm=6))
        missing_spec = replace(base, id="missing_spec", edge_feature=None)

        plan_edge_feature_passes((missing_tool, base, missing_spec), accumulator=acc, tool_db=TOOLS_WITH_VBIT)

        assert len(acc.errors) == 2
        assert "missing_tool" in acc.errors[0]
        assert "missing_spec" in acc.errors[1]
        assert sum(record.count for record in acc.passes()) == 1

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
        assert key == ("profile", 6.0, "flat", None, None, None)

    def test_different_roundover_radii_different_keys(self):
        tool_6 = ToolSelection(
            name="r6", diameter=25.4, kind="roundover", rpm=16000, feed_xy=1500, feed_z=500, roundover_radius_mm=6.0
        )
        tool_10 = ToolSelection(
            name="r10", diameter=25.4, kind="roundover", rpm=16000, feed_xy=1500, feed_z=500, roundover_radius_mm=10.0
        )
        assert pass_key("edge", tool_6) != pass_key("edge", tool_10)


class TestPickToolForRoundover:
    def test_selects_closest_radius(self):
        tool = pick_tool_for_roundover(TOOLS_WITH_TWO_ROUNDOVERS, radius_mm=6.0)
        assert tool.roundover_radius_mm == 6.0

    def test_no_roundover_bits_raises(self):
        with pytest.raises(ValueError, match="roundover bit"):
            pick_tool_for_roundover(FLAT_ONLY, radius_mm=6.0)

    def test_single_roundover_bit(self):
        tool = pick_tool_for_roundover(TOOLS_WITH_ROUNDOVER, radius_mm=6.0)
        assert tool.roundover_radius_mm == 6.0

    def test_ignores_flat_tools(self):
        tool = pick_tool_for_roundover(TOOLS_WITH_ROUNDOVER, radius_mm=6.0)
        assert tool.kind == "roundover"

    def test_radius_mismatch_raises(self):
        with pytest.raises(ValueError, match="No roundover bit with radius near"):
            pick_tool_for_roundover(TOOLS_WITH_ROUNDOVER, radius_mm=20.0)


class TestPlanRoundoverPasses:
    def test_roundover_produces_edge_record(self):
        acc = _accumulator()
        entries = (
            _edge_feature("Rect", {"w_mm": 50.0, "h_mm": 30.0}, (100.0, 75.0), 6.0, RoundoverSpec(radius_mm=6.0)),
        )
        plan_edge_feature_passes(entries, accumulator=acc, tool_db=TOOLS_WITH_ROUNDOVER)
        records = acc.passes()
        assert len(records) == 1
        assert records[0].op == "edge"
        assert len(records[0].moves) > 0

    def test_wrong_roundover_radius_is_an_error(self):
        acc = _accumulator()
        entries = (
            _edge_feature("Rect", {"w_mm": 50.0, "h_mm": 30.0}, (100.0, 75.0), 6.0, RoundoverSpec(radius_mm=10.0)),
        )
        plan_edge_feature_passes(entries, accumulator=acc, tool_db=TOOLS_WITH_ROUNDOVER)
        assert len(acc.passes()) == 0
        assert len(acc.errors) == 1
        assert "no roundover bit with 10.0mm radius" in acc.errors[0]

    def test_roundover_inside_offset(self):
        acc = _accumulator()
        entries = (
            _edge_feature(
                "Rect",
                {"w_mm": 50.0, "h_mm": 30.0},
                (100.0, 75.0),
                6.0,
                RoundoverSpec(radius_mm=6.0),
                side="inside",
            ),
        )
        plan_edge_feature_passes(entries, accumulator=acc, tool_db=TOOLS_WITH_ROUNDOVER)
        records = acc.passes()
        assert len(records) == 1
        assert len(records[0].moves) > 0


SUMMARY_TOOL = ToolSelection(name="t", diameter=6.35, kind="flat", rpm=18000, feed_xy=1200.0, feed_z=300.0)


class TestMoveTiming:
    def test_cut_time_uses_per_move_and_modal_feed(self):
        moves: list[Move] = [
            SetFeedMove(feed=600.0),
            RapidMove(x=0.0, y=0.0, z=5.0),
            CutMove(z=-1.0),
            CutMove(x=100.0, feed=1200.0),
            RetractMove(z=5.0),
            DwellMove(seconds=2.0),
            RapidMove(x=0.0),
        ]

        metrics = _summarise_moves(moves, SUMMARY_TOOL)

        assert metrics["cut_time_s"] == pytest.approx(0.6 + 5.0)
        assert metrics["rapid_distance_xy_mm"] == pytest.approx(100.0)
        assert metrics["rapid_distance_z_mm"] == pytest.approx(6.0)
        assert metrics["dwell_time_s"] == pytest.approx(2.0)
        assert metrics["max_depth_mm"] == pytest.approx(1.0)

    def test_cut_time_falls_back_to_tool_feeds_before_any_feed_is_set(self):
        moves: list[Move] = [RapidMove(x=0.0, y=0.0, z=5.0), CutMove(z=-1.0), CutMove(x=60.0)]

        metrics = _summarise_moves(moves, SUMMARY_TOOL)

        assert metrics["cut_time_s"] == pytest.approx(6.0 / 300.0 * 60.0 + 60.0 / 1200.0 * 60.0)

    def test_retract_updates_z_for_the_next_plunge(self):
        moves: list[Move] = [RapidMove(x=0.0, y=0.0, z=-2.0), RetractMove(z=5.0), CutMove(z=-2.0, feed=700.0)]

        metrics = _summarise_moves(moves, SUMMARY_TOOL)

        assert metrics["plunge_travel_mm"] == pytest.approx(7.0)
        assert metrics["cut_time_s"] == pytest.approx(7.0 / 700.0 * 60.0)

    def test_runtime_adds_cut_rapid_and_dwell_time(self):
        metrics = {
            "rapid_distance_xy_mm": 5000.0,
            "rapid_distance_z_mm": 1000.0,
            "cut_time_s": 120.0,
            "dwell_time_s": 30.0,
        }

        assert estimated_runtime_min(metrics) == pytest.approx(4.5)

    def test_gcode_file_summary_joins_ops_and_times_the_merged_moves(self):
        acc = _accumulator()
        pocket = acc.get_record("pocket", SUMMARY_TOOL)
        pocket.add_moves([RapidMove(x=0.0, y=0.0, z=5.0), CutMove(z=-1.0, feed=600.0), CutMove(x=1200.0, feed=1200.0)])
        dogbone = acc.get_record("dogbone", SUMMARY_TOOL)
        dogbone.add_moves([RetractMove(z=5.0), RapidMove(x=0.0), CutMove(z=-1.0, feed=600.0)])

        entry = summarise_gcode_file("6.35mm.nc", [pocket, dogbone])

        expected_s = 0.6 + 60.0 + 0.6 + (1200.0 / 5000.0 + 6.0 / 1000.0) * 60.0
        assert entry == {
            "filename": "6.35mm.nc",
            "operation": "pocket, dogbone",
            "tool_diameter_mm": 6.35,
            "rpm": 18000,
            "feed_xy_mm_min": 1200.0,
            "feed_z_mm_min": 300.0,
            "stepdown_mm": None,
            "max_depth_mm": 1.0,
            "feature_count": 0,
            "strategy": "raster_pocket, dogbone",
            "estimated_runtime_min": round(expected_s / 60.0, 1),
        }


def _profile_intent(constraints: Constraints) -> RemovalIntent:
    return RemovalIntent(
        region_id="profile_part",
        bounds=Bounds2D(x_min=0.0, x_max=100.0, y_min=0.0, y_max=50.0),
        depth_profile=DepthProfile(mode="constant", z_top=0.0, z_bottom=-19.0),
        hint_type="profile",
        constraints=constraints,
    )


class TestGcodeFileStrategy:
    def _entry(self, op: str, intents: list[RemovalIntent]) -> dict:
        record = _accumulator().get_record(op, SUMMARY_TOOL)
        record.add_moves([RapidMove(x=0.0, y=0.0, z=5.0), CutMove(z=-1.0, feed=300.0)], increment=2)
        return summarise_gcode_file(f"{op}.nc", [record], profile_intents=intents, cut_through_mm=0.2)

    def test_profile_with_onion_skin(self):
        entry = self._entry("profile", [_profile_intent(Constraints(onion_skin_mm=0.3))])

        assert entry["strategy"] == "onion_skin_then_finish"
        assert entry["holding"] == "onion_skin 0.3mm"
        assert entry["cut_through_mm"] == 0.2
        assert entry["feature_count"] == 2

    def test_profile_with_tabs(self):
        tabs = TabConstraint(count=4, height_mm=3.0, width_mm=None)
        entry = self._entry("profile", [_profile_intent(Constraints(tabs=tabs))])

        assert entry["strategy"] == "tabbed_profile"
        assert entry["holding"] == "tabs 4x3mm"

    def test_profile_without_holding(self):
        entry = self._entry("profile", [_profile_intent(Constraints())])

        assert entry["strategy"] == "contour"
        assert "holding" not in entry

    def test_release_summary_describes_only_onion_skin_removal(self):
        entry = self._entry(
            "release",
            [
                _profile_intent(Constraints(onion_skin_mm=0.3)),
                _profile_intent(Constraints(tabs=TabConstraint(count=4, height_mm=3, width_mm=None))),
            ],
        )

        assert entry["strategy"] == "onion_skin_release"
        assert entry["holding"] == "onion_skin 0.3mm"
        assert entry["cut_through_mm"] == 0.2

    def test_allowance_finish_summary_retains_holding(self):
        entry = self._entry(
            "profile_finish", [_profile_intent(Constraints(tabs=TabConstraint(count=4, height_mm=3, width_mm=None)))]
        )

        assert entry["strategy"] == "allowance_finish"
        assert entry["holding"] == "tabs 4x3mm"

    def test_bore_is_helical_and_carries_no_profile_fields(self):
        entry = self._entry("bore", [])

        assert entry["strategy"] == "helical_bore"
        assert "cut_through_mm" not in entry
        assert "holding" not in entry

    def test_unlabeled_op_uses_op_name(self):
        assert self._entry("corner_cleanup", [])["strategy"] == "corner_cleanup"
