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
from cam.moves import CutMove, RapidMove, RetractMove, XYMove
from cam.ops.bore import pocket_circle_concentric
from cam.ops.engrave import engrave_lines
from cam.ops.face import face_zigzag
from cam.planner.params import MIN_STEPDOWN_MM, stepdown_for, stepover_for
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
)
from ir.removal_intent import BevelSpec, ChamferSpec, RoundoverSpec, ShapeGeometry
from layout_ast.layout import RestSpec

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


def _accumulator():
    return PassAccumulator(
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

    def test_pocket_with_island_and_rest_raises(self):
        acc = _accumulator()
        island = IslandInput(x_min=120.0, x_max=180.0, y_min=70.0, y_max=130.0)
        pocket = replace(
            _feature("Rect", {"w_mm": 200.0, "h_mm": 160.0}, _RING_CENTER, 3.0, id="rest_rect"),
            islands=(island,),
            rest=RestSpec(tool_diameter_mm=3.0),
        )
        with pytest.raises(ValueError, match="Pocket 'rest_rect': islands are not supported with rest"):
            plan_pocket_passes((pocket,), accumulator=acc, tool_db=FLAT_ONLY, config=Config())

    def test_holed_polygon_with_rest_raises(self):
        acc = _accumulator()
        pocket = _ring_feature(10.0, id="rest_ring", rest=RestSpec(tool_diameter_mm=3.0))
        with pytest.raises(ValueError, match="Pocket 'rest_ring': holes are not supported with rest"):
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

    def test_no_vbit_warns(self):
        acc = _accumulator()
        entries = (
            _edge_feature(
                "Rect", {"w_mm": 50.0, "h_mm": 30.0}, (100.0, 75.0), 6.0, ChamferSpec(width_mm=2.0, angle_deg=45.0)
            ),
        )
        plan_edge_feature_passes(entries, accumulator=acc, tool_db=FLAT_ONLY)
        assert len(acc.warnings) == 1
        assert "no V-bit" in acc.warnings[0]

    def test_no_roundover_bit_warns(self):
        acc = _accumulator()
        entries = (
            _edge_feature("Rect", {"w_mm": 50.0, "h_mm": 30.0}, (100.0, 75.0), 6.0, RoundoverSpec(radius_mm=6.0)),
        )
        plan_edge_feature_passes(entries, accumulator=acc, tool_db=FLAT_ONLY)
        assert len(acc.warnings) == 1
        assert "no roundover bit" in acc.warnings[0]

    def test_unsupported_shape_warns(self):
        acc = _accumulator()
        entries = (
            _edge_feature(
                "Hexagon", {"w_mm": 50.0, "h_mm": 30.0}, (100.0, 75.0), 6.0, ChamferSpec(width_mm=2.0, angle_deg=45.0)
            ),
        )
        plan_edge_feature_passes(entries, accumulator=acc, tool_db=TOOLS_WITH_VBIT)
        assert len(acc.passes()) == 0
        assert len(acc.warnings) == 1
        assert "unsupported shape" in acc.warnings[0].lower()

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

    def test_no_roundover_bit_skips(self):
        acc = _accumulator()
        entries = (
            _edge_feature("Rect", {"w_mm": 50.0, "h_mm": 30.0}, (100.0, 75.0), 6.0, RoundoverSpec(radius_mm=6.0)),
        )
        plan_edge_feature_passes(entries, accumulator=acc, tool_db=FLAT_ONLY)
        assert len(acc.passes()) == 0

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
