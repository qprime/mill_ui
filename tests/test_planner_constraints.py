from __future__ import annotations

from cam.moves import CutMove, Move, RapidMove, SetRpmMove
from cam.pipeline import run_pipeline
from cam.planner.capabilities import (
    PLANNER_CAPABILITIES,
    ConstraintSupport,
    audit_constraints,
)
from ir.removal_intent import (
    Bounds2D,
    Constraints,
    DepthProfile,
    KeepoutRegion,
    RemovalIntent,
    TabConstraint,
)
from pml.yaml_parser import parse_pml_yaml
from resolution.layout_resolver import resolve_layout
from validation.toolpath_checks import (
    verify_toolpath_avoids_keepouts,
)


class TestConstraintAudit:
    def test_audit_no_constraints(self):
        intent = RemovalIntent(
            region_id="test",
            bounds=Bounds2D(x_min=0, x_max=100, y_min=0, y_max=100),
            depth_profile=DepthProfile.constant(z_top=0, z_bottom=-10),
        )
        result = audit_constraints([intent])
        assert not result.has_errors()
        assert len(result.warnings) == 0

    def test_audit_tabs_honored(self):
        intent = RemovalIntent(
            region_id="test",
            bounds=Bounds2D(x_min=0, x_max=100, y_min=0, y_max=100),
            depth_profile=DepthProfile.constant(z_top=0, z_bottom=-10),
            constraints=Constraints(tabs=TabConstraint(count=4, height_mm=3, width_mm=10)),
        )
        result = audit_constraints([intent])
        assert not result.has_errors()
        tabs_entry = next((e for e in result.entries if e.constraint == "tabs"), None)
        assert tabs_entry is not None
        assert tabs_entry.count == 1
        assert tabs_entry.status == ConstraintSupport.HONORED

    def test_audit_keepouts_honored(self):
        keepout = KeepoutRegion(
            bounds=Bounds2D(x_min=40, x_max=60, y_min=40, y_max=60),
            reason="clamp",
        )
        intent = RemovalIntent(
            region_id="test",
            bounds=Bounds2D(x_min=0, x_max=100, y_min=0, y_max=100),
            depth_profile=DepthProfile.constant(z_top=0, z_bottom=-10),
            constraints=Constraints(keepouts=(keepout,)),
        )
        result = audit_constraints([intent])
        assert not result.has_errors()
        keepouts_entry = next((e for e in result.entries if e.constraint == "keepouts"), None)
        assert keepouts_entry is not None
        assert keepouts_entry.count == 1
        assert keepouts_entry.safety_critical is True

    def test_audit_v_carve_not_implemented(self):
        intent = RemovalIntent(
            region_id="test",
            bounds=Bounds2D(x_min=0, x_max=100, y_min=0, y_max=100),
            depth_profile=DepthProfile.v_carve(z_top=0, z_bottom=-10, v_angle_deg=60),
        )
        result = audit_constraints([intent])
        assert not result.has_errors()
        assert len(result.warnings) == 1
        assert "v_carve" in result.warnings[0]

    def test_audit_multiple_intents(self):
        intent1 = RemovalIntent(
            region_id="test1",
            bounds=Bounds2D(x_min=0, x_max=100, y_min=0, y_max=100),
            depth_profile=DepthProfile.constant(z_top=0, z_bottom=-10),
            constraints=Constraints(tabs=TabConstraint(count=4, height_mm=3, width_mm=10)),
        )
        keepout = KeepoutRegion(
            bounds=Bounds2D(x_min=200, x_max=220, y_min=200, y_max=220),
            reason="fixture",
        )
        intent2 = RemovalIntent(
            region_id="test2",
            bounds=Bounds2D(x_min=150, x_max=250, y_min=150, y_max=250),
            depth_profile=DepthProfile.constant(z_top=0, z_bottom=-10),
            constraints=Constraints(keepouts=(keepout,)),
        )
        result = audit_constraints([intent1, intent2])
        assert not result.has_errors()


class TestToolpathKeepoutVerification:
    def test_no_keepouts_passes(self):
        moves = [
            CutMove(x=10, y=10, z=-5),
            CutMove(x=20, y=20, z=-5),
        ]
        result = verify_toolpath_avoids_keepouts(moves, [])
        assert not result.has_violations()

    def test_move_outside_keepout_passes(self):
        moves = [
            CutMove(x=10, y=10, z=-5),
            CutMove(x=20, y=20, z=-5),
        ]
        keepouts = [
            {"x_min": 50, "x_max": 60, "y_min": 50, "y_max": 60, "reason": "clamp"},
        ]
        result = verify_toolpath_avoids_keepouts(moves, keepouts)
        assert not result.has_violations()

    def test_move_inside_keepout_fails(self):
        moves = [
            CutMove(x=10, y=10, z=-5),
            CutMove(x=55, y=55, z=-5),
        ]
        keepouts = [
            {"x_min": 50, "x_max": 60, "y_min": 50, "y_max": 60, "reason": "clamp"},
        ]
        result = verify_toolpath_avoids_keepouts(moves, keepouts)
        assert result.has_violations()
        assert len(result.keepout_violations) == 1
        assert result.keepout_violations[0].keepout_reason == "clamp"

    def test_tool_radius_expansion(self):
        moves = [
            CutMove(x=45, y=55, z=-5),
        ]
        keepouts = [
            {"x_min": 50, "x_max": 60, "y_min": 50, "y_max": 60, "reason": "clamp"},
        ]
        result_no_radius = verify_toolpath_avoids_keepouts(moves, keepouts, tool_radius_mm=0)
        assert not result_no_radius.has_violations()

        result_with_radius = verify_toolpath_avoids_keepouts(moves, keepouts, tool_radius_mm=10)
        assert result_with_radius.has_violations()

    def test_multiple_keepouts(self):
        moves = [
            CutMove(x=55, y=55, z=-5),
        ]
        keepouts = [
            {"x_min": 10, "x_max": 20, "y_min": 10, "y_max": 20, "reason": "clamp1"},
            {"x_min": 50, "x_max": 60, "y_min": 50, "y_max": 60, "reason": "clamp2"},
        ]
        result = verify_toolpath_avoids_keepouts(moves, keepouts)
        assert result.has_violations()
        assert result.keepout_violations[0].keepout_reason == "clamp2"

    def test_moves_without_xy_ignored(self):
        moves: list[Move] = [
            SetRpmMove(rpm=10000),
            RapidMove(z=5),
            CutMove(x=55, y=55, z=-5),
        ]
        keepouts = [
            {"x_min": 50, "x_max": 60, "y_min": 50, "y_max": 60, "reason": "clamp"},
        ]
        result = verify_toolpath_avoids_keepouts(moves, keepouts)
        assert result.has_violations()
        assert len(result.keepout_violations) == 1


class TestPipelineKeepoutIntegration:
    def test_pipeline_with_keepout_pocket_outside(self):
        pml = """
Sheet:
  width: 400mm
  height: 400mm
  thickness: 19mm

children:
  - Rect:
      id: panel
      w: 100mm
      h: 100mm
      x: 50mm
      y: 50mm
      feature:
        type: pocket
        depth: 6mm
"""
        ast = parse_pml_yaml(pml)
        flat = resolve_layout(ast)
        result = run_pipeline(flat, generate_svg=False)
        assert len(result.errors) == 0

    def test_constraint_audit_in_metrics(self):
        pml = """
Sheet:
  width: 400mm
  height: 400mm
  thickness: 19mm

children:
  - Rect:
      id: panel
      w: 100mm
      h: 100mm
      feature:
        type: profile
        depth: through
        tab_count: 4
        tab_height: 3mm
"""
        ast = parse_pml_yaml(pml)
        flat = resolve_layout(ast)
        result = run_pipeline(flat, generate_svg=False)
        assert "constraint_audit" in result.metrics
        audit = result.metrics["constraint_audit"]
        assert "tabs" in audit
        assert audit["tabs"]["status"] == "honored"
        assert audit["tabs"]["count"] == 1


class TestPlannerCapabilitiesRegistry:
    def test_all_critical_constraints_have_capability(self):
        critical = ["constraints.keepouts"]
        for key in critical:
            assert key in PLANNER_CAPABILITIES
            assert PLANNER_CAPABILITIES[key].safety_critical is True

    def test_tabs_honored(self):
        assert "constraints.tabs" in PLANNER_CAPABILITIES
        assert PLANNER_CAPABILITIES["constraints.tabs"].support == ConstraintSupport.HONORED

    def test_keepouts_honored(self):
        assert "constraints.keepouts" in PLANNER_CAPABILITIES
        assert PLANNER_CAPABILITIES["constraints.keepouts"].support == ConstraintSupport.HONORED

    def test_v_carve_not_implemented(self):
        assert "depth_profile.mode.v_carve" in PLANNER_CAPABILITIES
        cap = PLANNER_CAPABILITIES["depth_profile.mode.v_carve"]
        assert cap.support == ConstraintSupport.NOT_IMPLEMENTED


class TestAdapterKeepoutExtraction:
    def test_keepouts_extracted_to_planner_input(self):
        from adapters.removal_to_planner import removal_intents_to_planner_input

        keepout = KeepoutRegion(
            bounds=Bounds2D(x_min=40, x_max=60, y_min=40, y_max=60),
            reason="clamp",
        )
        intent = RemovalIntent(
            region_id="test",
            bounds=Bounds2D(x_min=0, x_max=100, y_min=0, y_max=100),
            depth_profile=DepthProfile.constant(z_top=0, z_bottom=-10),
            constraints=Constraints(keepouts=(keepout,)),
            hint_type="pocket",
            shape="Rect",
        )
        planner_input = removal_intents_to_planner_input([intent])

        assert len(planner_input.keepouts) == 1
        k = planner_input.keepouts[0]
        assert k.x_min == 40
        assert k.x_max == 60
        assert k.y_min == 40
        assert k.y_max == 60
        assert k.reason == "clamp"

    def test_multiple_keepouts_deduplicated(self):
        from adapters.removal_to_planner import removal_intents_to_planner_input

        keepout = KeepoutRegion(
            bounds=Bounds2D(x_min=40, x_max=60, y_min=40, y_max=60),
            reason="clamp",
        )
        intent1 = RemovalIntent(
            region_id="test1",
            bounds=Bounds2D(x_min=0, x_max=100, y_min=0, y_max=100),
            depth_profile=DepthProfile.constant(z_top=0, z_bottom=-10),
            constraints=Constraints(keepouts=(keepout,)),
            hint_type="pocket",
            shape="Rect",
        )
        intent2 = RemovalIntent(
            region_id="test2",
            bounds=Bounds2D(x_min=100, x_max=200, y_min=0, y_max=100),
            depth_profile=DepthProfile.constant(z_top=0, z_bottom=-10),
            constraints=Constraints(keepouts=(keepout,)),
            hint_type="pocket",
            shape="Rect",
        )
        planner_input = removal_intents_to_planner_input([intent1, intent2])

        assert len(planner_input.keepouts) == 1


class TestTypedPlannerInput:
    def test_planner_input_from_intents(self):
        from adapters.removal_to_planner import removal_intents_to_planner_input

        keepout = KeepoutRegion(
            bounds=Bounds2D(x_min=40, x_max=60, y_min=40, y_max=60),
            reason="clamp",
        )
        intent = RemovalIntent(
            region_id="test",
            bounds=Bounds2D(x_min=0, x_max=100, y_min=0, y_max=100),
            depth_profile=DepthProfile.constant(z_top=0, z_bottom=-10),
            constraints=Constraints(
                keepouts=(keepout,),
                tabs=TabConstraint(count=4, height_mm=3, width_mm=10),
            ),
            hint_type="profile",
            shape="Rect",
        )
        planner_input = removal_intents_to_planner_input([intent])

        assert len(planner_input.profiles) == 1
        assert len(planner_input.keepouts) == 1
        profile = planner_input.profiles[0]
        assert profile.tabs is not None
        assert profile.tabs.count == 4
        assert len(profile.keepouts) == 1
        assert profile.keepouts[0].reason == "clamp"

    def test_planner_input_roundtrip(self):
        from adapters.removal_to_planner import removal_intents_to_planner_input
        from cam.planner.planner_input import PlannerInput

        keepout = KeepoutRegion(
            bounds=Bounds2D(x_min=40, x_max=60, y_min=40, y_max=60),
            reason="clamp",
        )
        intent = RemovalIntent(
            region_id="test",
            bounds=Bounds2D(x_min=0, x_max=100, y_min=0, y_max=100),
            depth_profile=DepthProfile.constant(z_top=0, z_bottom=-10),
            constraints=Constraints(keepouts=(keepout,)),
            hint_type="pocket",
            shape="Rect",
        )
        planner_input = removal_intents_to_planner_input([intent])
        hints_dict = planner_input.to_hints_dict()
        roundtrip = PlannerInput.from_hints_dict(hints_dict)

        assert len(roundtrip.pockets) == 1
        assert len(roundtrip.keepouts) == 1
        assert roundtrip.keepouts[0].x_min == 40
        assert roundtrip.keepouts[0].reason == "clamp"

    def test_planner_input_preserves_tabs(self):
        from adapters.removal_to_planner import removal_intents_to_planner_input

        intent = RemovalIntent(
            region_id="test",
            bounds=Bounds2D(x_min=0, x_max=100, y_min=0, y_max=100),
            depth_profile=DepthProfile.constant(z_top=0, z_bottom=-10),
            constraints=Constraints(tabs=TabConstraint(count=4, height_mm=3, width_mm=10)),
            hint_type="profile",
            shape="Rect",
        )
        planner_input = removal_intents_to_planner_input([intent])

        assert len(planner_input.profiles) == 1
        profile = planner_input.profiles[0]
        assert profile.tabs is not None
        assert profile.tabs.count == 4
        assert profile.tabs.height_mm == 3.0
        assert profile.tabs.width_mm == 10.0


class TestOnionSkinPassOrdering:
    def _extract_comments(self, pml_str: str) -> list[str]:
        ast = parse_pml_yaml(pml_str)
        flat = resolve_layout(ast)
        result = run_pipeline(flat, generate_svg=False)
        from cam.moves import CommentMove

        comments = []
        for pr in result.passes:
            for m in pr.moves:
                if isinstance(m, CommentMove):
                    comments.append(m.text)
        return comments

    def test_single_part_rough_then_finish(self):
        pml = """
Sheet:
  width: 400mm
  height: 400mm
  thickness: 19mm

children:
  - Rect:
      id: part1
      w: 50mm
      h: 50mm
      x: 100mm
      y: 100mm
      children:
        - Profile:
            side: outside
            depth: through
            onion_skin_mm: 0.3
"""
        comments = self._extract_comments(pml)
        rough_idxs = [i for i, c in enumerate(comments) if "onion_skin_rough" in c]
        finish_idxs = [i for i, c in enumerate(comments) if "finish_profile_pass" in c]
        assert len(rough_idxs) >= 1
        assert len(finish_idxs) >= 1
        assert max(rough_idxs) < min(finish_idxs)

    def test_multiple_parts_all_rough_before_finish(self):
        pml = """
Sheet:
  width: 400mm
  height: 400mm
  thickness: 19mm

children:
  - Rect:
      id: part1
      w: 50mm
      h: 50mm
      x: 50mm
      y: 50mm
      children:
        - Profile:
            side: outside
            depth: through
            onion_skin_mm: 0.3
  - Rect:
      id: part2
      w: 50mm
      h: 50mm
      x: 150mm
      y: 50mm
      children:
        - Profile:
            side: outside
            depth: through
            onion_skin_mm: 0.3
  - Rect:
      id: part3
      w: 50mm
      h: 50mm
      x: 250mm
      y: 50mm
      children:
        - Profile:
            side: outside
            depth: through
            onion_skin_mm: 0.3
"""
        comments = self._extract_comments(pml)
        rough_idxs = [i for i, c in enumerate(comments) if "onion_skin_rough" in c]
        finish_idxs = [i for i, c in enumerate(comments) if "finish_profile_pass" in c]
        assert len(rough_idxs) == 3
        assert len(finish_idxs) == 3
        assert max(rough_idxs) < min(finish_idxs)

    def test_finish_order_matches_rough_order(self):
        pml = """
Sheet:
  width: 400mm
  height: 400mm
  thickness: 19mm

children:
  - Rect:
      id: part_a
      w: 40mm
      h: 40mm
      x: 50mm
      y: 50mm
      children:
        - Profile:
            side: outside
            depth: through
            onion_skin_mm: 0.3
  - Rect:
      id: part_b
      w: 60mm
      h: 60mm
      x: 150mm
      y: 50mm
      children:
        - Profile:
            side: outside
            depth: through
            onion_skin_mm: 0.3
"""
        comments = self._extract_comments(pml)
        rough_idxs = [i for i, c in enumerate(comments) if "onion_skin_rough" in c]
        finish_idxs = [i for i, c in enumerate(comments) if "finish_profile_pass" in c]
        assert len(rough_idxs) == 2
        assert len(finish_idxs) == 2
        assert max(rough_idxs) < min(finish_idxs)

    def test_no_onion_skin_unchanged(self):
        pml = """
Sheet:
  width: 400mm
  height: 400mm
  thickness: 19mm

children:
  - Rect:
      id: part1
      w: 50mm
      h: 50mm
      x: 100mm
      y: 100mm
      children:
        - Profile:
            side: outside
            depth: through
"""
        comments = self._extract_comments(pml)
        assert not any("onion_skin_rough" in c for c in comments)
        assert not any("finish_profile_pass" in c for c in comments)

    def test_mixed_onion_and_plain(self):
        pml = """
Sheet:
  width: 400mm
  height: 400mm
  thickness: 19mm

children:
  - Rect:
      id: onion_part
      w: 50mm
      h: 50mm
      x: 50mm
      y: 50mm
      children:
        - Profile:
            side: outside
            depth: through
            onion_skin_mm: 0.3
  - Rect:
      id: plain_part
      w: 50mm
      h: 50mm
      x: 200mm
      y: 50mm
      children:
        - Profile:
            side: outside
            depth: through
"""
        comments = self._extract_comments(pml)
        rough_idxs = [i for i, c in enumerate(comments) if "onion_skin_rough" in c]
        finish_idxs = [i for i, c in enumerate(comments) if "finish_profile_pass" in c]
        assert len(rough_idxs) == 1
        assert len(finish_idxs) == 1
        assert max(rough_idxs) < min(finish_idxs)

    def test_onion_skin_then_finish_backward_compat(self):
        from cam.model.machine import Machine as MachineModel
        from cam.model.material import Material as MaterialModel
        from cam.model.setup import Setup as SetupModel
        from cam.model.stock import Stock as StockModel
        from cam.model.tool import Tool as ToolModel
        from cam.moves import CommentMove
        from cam.path.strategies import onion_skin_then_finish
        from cam.primitives import rectangle

        tool = ToolModel(name="test", diameter=6.35, rpm=18000, feed_xy=1500, feed_z=500)
        stock = StockModel(width=200, height=200, thickness=19)
        material = MaterialModel(name="mdf")
        machine = MachineModel(name="test")
        setup = SetupModel(stock=stock, tool=tool, material=material, machine=machine, safe_z=5.0)
        shape = rectangle(50, 50)

        moves = onion_skin_then_finish(shape, setup, 19.0, skin_mm=0.3)
        comments = [m.text for m in moves if isinstance(m, CommentMove)]
        rough_idxs = [i for i, c in enumerate(comments) if "onion_skin_rough" in c]
        finish_idxs = [i for i, c in enumerate(comments) if "finish_profile_pass" in c]
        assert len(rough_idxs) >= 1
        assert len(finish_idxs) >= 1
        assert max(rough_idxs) < min(finish_idxs)


class TestConstraintCoverageEnforcement:
    def test_all_constraint_fields_documented(self):
        import dataclasses

        from ir.removal_intent import Constraints

        constraint_fields = {f.name for f in dataclasses.fields(Constraints)}
        documented = {
            "tabs",
            "onion_skin_mm",
            "keepouts",
            "islands",
            "edge_treatment",
            "tolerance_mm",
            "safe_z_mm",
        }
        assert constraint_fields == documented, (
            f"New constraint field(s) added to Constraints but not documented in "
            f"PLANNER_CAPABILITIES: {constraint_fields - documented}"
        )

    def test_all_constraint_fields_in_capabilities(self):
        constraint_keys_in_caps = [k for k in PLANNER_CAPABILITIES if k.startswith("constraints.")]
        expected = {
            "constraints.tabs",
            "constraints.onion_skin_mm",
            "constraints.keepouts",
            "constraints.islands",
            "constraints.edge_treatment",
            "constraints.tolerance_mm",
            "constraints.safe_z_mm",
        }
        actual = set(constraint_keys_in_caps)
        assert actual == expected, f"Constraint field(s) missing from PLANNER_CAPABILITIES: {expected - actual}"
