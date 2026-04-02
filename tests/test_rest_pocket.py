#!/usr/bin/env python3

import pytest

from adapters.ast_to_removal import ast_to_removal_intents
from adapters.removal_to_planner import removal_intents_to_planner_input
from cam.config import Config
from cam.model.machine import Machine
from cam.model.stock import Stock
from cam.planner.passes import plan_passes
from cam.planner.passes.tools import normalize_tool_entries, pick_tool_by_diameter
from layout_ast.layout import Feature, Geometry, Item, LayoutAST, Placement, RestSpec, Sheet
from pml.yaml_parser import PMLParseError, parse_pml_yaml

TOOL_DB = [
    {"name": "1/8_endmill", "diameter": 3.175, "kind": "flat", "rpm": 14000, "feed_xy": 900, "feed_z": 300},
    {"name": "1/4_endmill", "diameter": 6.35, "kind": "flat", "rpm": 12000, "feed_xy": 1200, "feed_z": 400},
    {"name": "1/2_endmill", "diameter": 12.7, "kind": "flat", "rpm": 10000, "feed_xy": 1500, "feed_z": 500},
    {"name": "v_bit_90", "diameter": 6.35, "kind": "v", "rpm": 18000, "feed_xy": 800, "feed_z": 200, "v_angle_deg": 90},
]


def _make_rest_ast(rest: RestSpec | None = None) -> LayoutAST:
    return LayoutAST(
        sheet=Sheet(width_mm=400, height_mm=300, thickness_mm=19, margin_mm=0.0),
        items=(
            Item(
                kind="shape",
                type="Rect",
                geometry=Geometry(data={"w_mm": 200, "h_mm": 150}),
                placement=Placement(center_xy_mm=(200, 150)),
                feature=Feature(type="pocket", depth_mm=12.0, rest=rest),
                shape_id="deep_pocket",
            ),
        ),
    )


class TestRestSpec:
    def test_defaults(self):
        spec = RestSpec(tool_diameter_mm=6.0)
        assert spec.tool_diameter_mm == 6.0
        assert spec.rough_allowance_mm == 0.5
        assert spec.finish_allowance_mm == 0.0

    def test_explicit_values(self):
        spec = RestSpec(tool_diameter_mm=3.175, rough_allowance_mm=0.3, finish_allowance_mm=0.1)
        assert spec.tool_diameter_mm == 3.175
        assert spec.rough_allowance_mm == 0.3
        assert spec.finish_allowance_mm == 0.1

    def test_invalid_tool_diameter(self):
        with pytest.raises(ValueError, match="must be positive"):
            RestSpec(tool_diameter_mm=0.0)
        with pytest.raises(ValueError, match="must be positive"):
            RestSpec(tool_diameter_mm=-1.0)

    def test_invalid_rough_allowance(self):
        with pytest.raises(ValueError, match="must be >= 0"):
            RestSpec(tool_diameter_mm=6.0, rough_allowance_mm=-0.1)

    def test_invalid_finish_allowance(self):
        with pytest.raises(ValueError, match="must be >= 0"):
            RestSpec(tool_diameter_mm=6.0, finish_allowance_mm=-0.1)

    def test_frozen(self):
        spec = RestSpec(tool_diameter_mm=6.0)
        with pytest.raises(AttributeError):
            spec.tool_diameter_mm = 3.0  # type: ignore[misc]


class TestRestIRPropagation:
    def test_rest_on_feature(self):
        rest = RestSpec(tool_diameter_mm=6.35)
        feature = Feature(type="pocket", depth_mm=12.0, rest=rest)
        assert feature.rest is not None
        assert feature.rest.tool_diameter_mm == 6.35

    def test_rest_none_by_default(self):
        feature = Feature(type="pocket", depth_mm=6.0)
        assert feature.rest is None

    def test_rest_propagation_to_removal_intent(self):
        rest = RestSpec(tool_diameter_mm=6.35, rough_allowance_mm=0.3)
        ast = _make_rest_ast(rest=rest)
        intents = ast_to_removal_intents(ast)
        assert len(intents) == 1
        assert intents[0].rest is not None
        assert intents[0].rest.tool_diameter_mm == 6.35
        assert intents[0].rest.rough_allowance_mm == 0.3

    def test_rest_none_not_propagated(self):
        ast = _make_rest_ast(rest=None)
        intents = ast_to_removal_intents(ast)
        assert len(intents) == 1
        assert intents[0].rest is None

    def test_rest_propagation_to_planner_input(self):
        rest = RestSpec(tool_diameter_mm=6.35)
        ast = _make_rest_ast(rest=rest)
        intents = ast_to_removal_intents(ast)
        planner_input = removal_intents_to_planner_input(intents)
        assert len(planner_input.pockets) == 1
        assert planner_input.pockets[0].rest is not None
        assert planner_input.pockets[0].rest.tool_diameter_mm == 6.35

    def test_rest_to_dict_roundtrip(self):
        rest = RestSpec(tool_diameter_mm=6.35, rough_allowance_mm=0.3, finish_allowance_mm=0.1)
        ast = _make_rest_ast(rest=rest)
        intents = ast_to_removal_intents(ast)
        d = intents[0].to_dict()
        assert "rest" in d
        assert d["rest"]["tool_diameter_mm"] == 6.35
        assert d["rest"]["rough_allowance_mm"] == 0.3
        assert d["rest"]["finish_allowance_mm"] == 0.1


class TestRestPlannerPasses:
    def _run_planner(self, rest: RestSpec):
        ast = _make_rest_ast(rest=rest)
        intents = ast_to_removal_intents(ast)
        planner_input = removal_intents_to_planner_input(intents)

        config = Config(safe_z_mm=6.0)
        machine = Machine()
        stock = Stock(width=400, height=300, thickness=19)

        return plan_passes(
            planner_input,
            config=config,
            tool_db=normalize_tool_entries(TOOL_DB),
            machine=machine,
            stock=stock,
        )

    def test_two_records(self):
        passes, *_ = self._run_planner(RestSpec(tool_diameter_mm=6.35))
        ops = [p.op for p in passes]
        assert "pocket" in ops
        assert "pocket_rest" in ops

    def test_different_tools(self):
        passes, *_ = self._run_planner(RestSpec(tool_diameter_mm=6.35))
        pocket_pass = next(p for p in passes if p.op == "pocket")
        rest_pass = next(p for p in passes if p.op == "pocket_rest")
        assert pocket_pass.tool_selection.diameter == 12.7
        assert rest_pass.tool_selection.diameter == 6.35

    def test_rough_has_moves(self):
        passes, *_ = self._run_planner(RestSpec(tool_diameter_mm=6.35))
        pocket_pass = next(p for p in passes if p.op == "pocket")
        assert len(pocket_pass.moves) > 0

    def test_rest_has_moves(self):
        passes, *_ = self._run_planner(RestSpec(tool_diameter_mm=6.35))
        rest_pass = next(p for p in passes if p.op == "pocket_rest")
        assert len(rest_pass.moves) > 0

    def test_rest_fewer_moves_than_full_pocket(self):
        passes_rest, *_ = self._run_planner(RestSpec(tool_diameter_mm=6.35))
        rest_pass = next(p for p in passes_rest if p.op == "pocket_rest")
        pocket_pass = next(p for p in passes_rest if p.op == "pocket")
        assert len(rest_pass.moves) < len(pocket_pass.moves)

    def test_finish_tool_must_be_smaller(self):
        with pytest.raises(ValueError, match="must be smaller"):
            self._run_planner(RestSpec(tool_diameter_mm=12.7))

    def test_finish_tool_not_found(self):
        ast = _make_rest_ast(rest=RestSpec(tool_diameter_mm=5.0))
        intents = ast_to_removal_intents(ast)
        planner_input = removal_intents_to_planner_input(intents)
        config = Config(safe_z_mm=6.0)
        machine = Machine()
        stock = Stock(width=400, height=300, thickness=19)

        with pytest.raises(ValueError, match="not found"):
            plan_passes(
                planner_input,
                config=config,
                tool_db=normalize_tool_entries(TOOL_DB),
                machine=machine,
                stock=stock,
            )

    def test_rest_tool_must_fit_pocket(self):
        small_ast = LayoutAST(
            sheet=Sheet(width_mm=200, height_mm=200, thickness_mm=19, margin_mm=0.0),
            items=(
                Item(
                    kind="shape",
                    type="Rect",
                    geometry=Geometry(data={"w_mm": 6, "h_mm": 6}),
                    placement=Placement(center_xy_mm=(100, 100)),
                    feature=Feature(type="pocket", depth_mm=3.0, rest=RestSpec(tool_diameter_mm=6.35)),
                    shape_id="tiny_pocket",
                ),
            ),
        )
        intents = ast_to_removal_intents(small_ast)
        planner_input = removal_intents_to_planner_input(intents)
        config = Config(safe_z_mm=6.0)
        machine = Machine()
        stock = Stock(width=200, height=200, thickness=19)

        with pytest.raises(ValueError, match="must be less than"):
            plan_passes(
                planner_input,
                config=config,
                tool_db=normalize_tool_entries(TOOL_DB),
                machine=machine,
                stock=stock,
            )

    def test_rest_rejects_circle(self):
        circle_ast = LayoutAST(
            sheet=Sheet(width_mm=200, height_mm=200, thickness_mm=19, margin_mm=0.0),
            items=(
                Item(
                    kind="shape",
                    type="Circle",
                    geometry=Geometry(data={"diameter_mm": 50}),
                    placement=Placement(center_xy_mm=(100, 100)),
                    feature=Feature(type="pocket", depth_mm=6.0, rest=RestSpec(tool_diameter_mm=3.175)),
                    shape_id="circle_pocket",
                ),
            ),
        )
        intents = ast_to_removal_intents(circle_ast)
        planner_input = removal_intents_to_planner_input(intents)
        config = Config(safe_z_mm=6.0)
        machine = Machine()
        stock = Stock(width=200, height=200, thickness=19)

        with pytest.raises(ValueError, match="only supported for rectangular"):
            plan_passes(
                planner_input,
                config=config,
                tool_db=normalize_tool_entries(TOOL_DB),
                machine=machine,
                stock=stock,
            )

    def test_rest_rejects_rounded_rect(self):
        rr_ast = LayoutAST(
            sheet=Sheet(width_mm=200, height_mm=200, thickness_mm=19, margin_mm=0.0),
            items=(
                Item(
                    kind="shape",
                    type="RoundedRect",
                    geometry=Geometry(data={"w_mm": 80, "h_mm": 60, "radius_mm": 5}),
                    placement=Placement(center_xy_mm=(100, 100)),
                    feature=Feature(type="pocket", depth_mm=6.0, rest=RestSpec(tool_diameter_mm=3.175)),
                    shape_id="rr_pocket",
                ),
            ),
        )
        intents = ast_to_removal_intents(rr_ast)
        planner_input = removal_intents_to_planner_input(intents)
        config = Config(safe_z_mm=6.0)
        machine = Machine()
        stock = Stock(width=200, height=200, thickness=19)

        with pytest.raises(ValueError, match="only supported for rectangular"):
            plan_passes(
                planner_input,
                config=config,
                tool_db=normalize_tool_entries(TOOL_DB),
                machine=machine,
                stock=stock,
            )

    def test_rest_perimeter_profile_in_finish_pass(self):
        passes, *_ = self._run_planner(RestSpec(tool_diameter_mm=3.175))
        rest_pass = next(p for p in passes if p.op == "pocket_rest")
        assert rest_pass.count >= 1

    def test_rest_corner_regions(self):
        passes, *_ = self._run_planner(RestSpec(tool_diameter_mm=3.175))
        rest_pass = next(p for p in passes if p.op == "pocket_rest")
        assert len(rest_pass.moves) > 0
        xs = [m.x for m in rest_pass.moves if hasattr(m, "x") and m.x is not None]
        ys = [m.y for m in rest_pass.moves if hasattr(m, "y") and m.y is not None]
        assert len(xs) > 0
        assert len(ys) > 0


class TestRestAndEdgeTreatmentExclusion:
    def test_rest_and_allowance_mutually_exclusive(self):
        from cam.planner.planner_input import EdgeTreatmentInput, FeatureInput, GeometryInput, PlannerInput
        from ir.removal_intent import ShapeGeometry

        entry = FeatureInput(
            id="test_pocket",
            shape="Rect",
            geometry=GeometryInput(
                shape="Rect",
                geometry=ShapeGeometry(w_mm=200.0, h_mm=150.0),
            ),
            center_xy_mm=(200.0, 150.0),
            depth_mm=12.0,
            rest=RestSpec(tool_diameter_mm=6.35),
            edge_treatment=EdgeTreatmentInput(type="allowance", rough_allowance_mm=0.5),
        )
        planner_input = PlannerInput(pockets=(entry,))
        config = Config(safe_z_mm=6.0)
        machine = Machine()
        stock = Stock(width=400, height=300, thickness=19)

        with pytest.raises(ValueError, match="Cannot combine"):
            plan_passes(
                planner_input,
                config=config,
                tool_db=normalize_tool_entries(TOOL_DB),
                machine=machine,
                stock=stock,
            )


class TestRestPMLParsing:
    def test_simple_form(self):
        pml = """
Sheet:
  width: 400mm
  height: 300mm
  thickness: 19mm
children:
  - Rect:
      id: pocket1
      at:
        x: 200mm
        y: 150mm
        width: 200mm
        height: 150mm
      feature:
        type: pocket
        depth: 12mm
        rest_tool: 6mm
"""
        ast = parse_pml_yaml(pml)
        from resolution.layout_resolver import resolve_layout

        layout = resolve_layout(ast)
        items = layout.items
        pocket = next(i for i in items if i.shape_id == "pocket1")
        assert pocket.feature is not None
        assert pocket.feature.rest is not None
        assert pocket.feature.rest.tool_diameter_mm == 6.0
        assert pocket.feature.rest.rough_allowance_mm == 0.5
        assert pocket.feature.rest.finish_allowance_mm == 0.0

    def test_explicit_form(self):
        pml = """
Sheet:
  width: 400mm
  height: 300mm
  thickness: 19mm
children:
  - Rect:
      id: pocket1
      at:
        x: 200mm
        y: 150mm
        width: 200mm
        height: 150mm
      feature:
        type: pocket
        depth: 12mm
        rest:
          tool: 6mm
          rough_allowance: 0.3mm
          finish_allowance: 0.1mm
"""
        ast = parse_pml_yaml(pml)
        from resolution.layout_resolver import resolve_layout

        layout = resolve_layout(ast)
        items = layout.items
        pocket = next(i for i in items if i.shape_id == "pocket1")
        assert pocket.feature is not None
        assert pocket.feature.rest is not None
        assert pocket.feature.rest.tool_diameter_mm == 6.0
        assert pocket.feature.rest.rough_allowance_mm == 0.3
        assert pocket.feature.rest.finish_allowance_mm == 0.1

    def test_both_forms_error(self):
        pml = """
Sheet:
  width: 400mm
  height: 300mm
  thickness: 19mm
children:
  - Rect:
      feature:
        type: pocket
        depth: 12mm
        rest_tool: 6mm
        rest:
          tool: 3mm
"""
        with pytest.raises(PMLParseError, match="Cannot specify both"):
            parse_pml_yaml(pml)

    def test_no_rest(self):
        pml = """
Sheet:
  width: 400mm
  height: 300mm
  thickness: 19mm
children:
  - Rect:
      feature:
        type: pocket
        depth: 6mm
"""
        ast = parse_pml_yaml(pml)
        from resolution.layout_resolver import resolve_layout

        layout = resolve_layout(ast)
        items = layout.items
        pocket = next(i for i in items if i.feature and i.feature.type == "pocket")
        assert pocket.feature is not None
        assert pocket.feature.rest is None


class TestRestPMLFormatting:
    def test_format_simple_rest(self):
        from pml.yaml_formatter import format_feature

        feature = Feature(type="pocket", depth_mm=12.0, rest=RestSpec(tool_diameter_mm=6.0))
        result = format_feature(feature)
        assert "rest_tool" in result
        assert result["rest_tool"] == "6mm"
        assert "rest" not in result

    def test_format_explicit_rest(self):
        from pml.yaml_formatter import format_feature

        feature = Feature(
            type="pocket",
            depth_mm=12.0,
            rest=RestSpec(tool_diameter_mm=6.0, rough_allowance_mm=0.3),
        )
        result = format_feature(feature)
        assert "rest" in result
        assert "rest_tool" not in result
        assert result["rest"]["tool"] == "6mm"
        assert result["rest"]["rough_allowance"] == "0.3mm"

    def test_format_no_rest(self):
        from pml.yaml_formatter import format_feature

        feature = Feature(type="pocket", depth_mm=6.0)
        result = format_feature(feature)
        assert "rest" not in result
        assert "rest_tool" not in result


class TestPickToolByDiameter:
    def test_exact_match(self):
        tools = normalize_tool_entries(TOOL_DB)
        tool = pick_tool_by_diameter(tools, 6.35)
        assert tool.diameter == 6.35

    def test_kind_filter(self):
        tools = normalize_tool_entries(TOOL_DB)
        tool = pick_tool_by_diameter(tools, 6.35, kind="flat")
        assert tool.diameter == 6.35
        assert tool.kind == "flat"

    def test_kind_filter_excludes(self):
        tools = normalize_tool_entries(TOOL_DB)
        with pytest.raises(ValueError, match="not found"):
            pick_tool_by_diameter(tools, 6.35, kind="ball")

    def test_not_found(self):
        tools = normalize_tool_entries(TOOL_DB)
        with pytest.raises(ValueError, match="not found"):
            pick_tool_by_diameter(tools, 99.0)


class TestRestCapabilitiesAudit:
    def test_rest_counted(self):
        from cam.planner.capabilities import audit_constraints

        rest = RestSpec(tool_diameter_mm=6.35)
        ast = _make_rest_ast(rest=rest)
        intents = ast_to_removal_intents(ast)
        result = audit_constraints(intents)
        rest_entry = next((e for e in result.entries if e.constraint == "rest"), None)
        assert rest_entry is not None
        assert rest_entry.count == 1

    def test_rest_not_counted_when_none(self):
        from cam.planner.capabilities import audit_constraints

        ast = _make_rest_ast(rest=None)
        intents = ast_to_removal_intents(ast)
        result = audit_constraints(intents)
        rest_entry = next((e for e in result.entries if e.constraint == "rest"), None)
        assert rest_entry is not None
        assert rest_entry.count == 0
