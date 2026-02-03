from __future__ import annotations

import pytest

from pml.yaml_parser import parse_pml_yaml
from resolution.layout_resolver import resolve_layout
from cam.pipeline import run_pipeline
from cam.planner.capabilities import (
    ConstraintSupport,
    PLANNER_CAPABILITIES,
    audit_constraints,
)
from adapters.ast_to_removal import ast_to_removal_intents
from ir.removal_intent import (
    RemovalIntent,
    Bounds2D,
    DepthProfile,
    Constraints,
    KeepoutRegion,
    TabConstraint,
    Allowance,
)
from validation.toolpath_checks import (
    verify_toolpath_avoids_keepouts,
    verify_passes_avoid_keepouts,
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
            {"x": 10, "y": 10, "z": -5},
            {"x": 20, "y": 20, "z": -5},
        ]
        result = verify_toolpath_avoids_keepouts(moves, [])
        assert not result.has_violations()

    def test_move_outside_keepout_passes(self):
        moves = [
            {"x": 10, "y": 10, "z": -5},
            {"x": 20, "y": 20, "z": -5},
        ]
        keepouts = [
            {"x_min": 50, "x_max": 60, "y_min": 50, "y_max": 60, "reason": "clamp"},
        ]
        result = verify_toolpath_avoids_keepouts(moves, keepouts)
        assert not result.has_violations()

    def test_move_inside_keepout_fails(self):
        moves = [
            {"x": 10, "y": 10, "z": -5},
            {"x": 55, "y": 55, "z": -5},
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
            {"x": 45, "y": 55, "z": -5},
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
            {"x": 55, "y": 55, "z": -5},
        ]
        keepouts = [
            {"x_min": 10, "x_max": 20, "y_min": 10, "y_max": 20, "reason": "clamp1"},
            {"x_min": 50, "x_max": 60, "y_min": 50, "y_max": 60, "reason": "clamp2"},
        ]
        result = verify_toolpath_avoids_keepouts(moves, keepouts)
        assert result.has_violations()
        assert result.keepout_violations[0].keepout_reason == "clamp2"

    def test_moves_without_xy_ignored(self):
        moves = [
            {"kind": "set_rpm", "rpm": 10000},
            {"z": 5},
            {"x": 55, "y": 55, "z": -5},
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

    def test_keepouts_extracted_to_hints(self):
        from adapters.removal_to_planner import removal_intents_to_hints

        keepout = KeepoutRegion(
            bounds=Bounds2D(x_min=40, x_max=60, y_min=40, y_max=60),
            reason="clamp",
        )
        intent = RemovalIntent(
            region_id="test",
            bounds=Bounds2D(x_min=0, x_max=100, y_min=0, y_max=100),
            depth_profile=DepthProfile.constant(z_top=0, z_bottom=-10),
            constraints=Constraints(keepouts=(keepout,)),
            metadata={"hint_type": "pocket", "shape": "Rect"},
        )
        hints = removal_intents_to_hints([intent])

        assert "keepouts" in hints
        assert len(hints["keepouts"]) == 1
        k = hints["keepouts"][0]
        assert k["x_min"] == 40
        assert k["x_max"] == 60
        assert k["y_min"] == 40
        assert k["y_max"] == 60
        assert k["reason"] == "clamp"

    def test_multiple_keepouts_deduplicated(self):
        from adapters.removal_to_planner import removal_intents_to_hints

        keepout = KeepoutRegion(
            bounds=Bounds2D(x_min=40, x_max=60, y_min=40, y_max=60),
            reason="clamp",
        )
        intent1 = RemovalIntent(
            region_id="test1",
            bounds=Bounds2D(x_min=0, x_max=100, y_min=0, y_max=100),
            depth_profile=DepthProfile.constant(z_top=0, z_bottom=-10),
            constraints=Constraints(keepouts=(keepout,)),
            metadata={"hint_type": "pocket", "shape": "Rect"},
        )
        intent2 = RemovalIntent(
            region_id="test2",
            bounds=Bounds2D(x_min=100, x_max=200, y_min=0, y_max=100),
            depth_profile=DepthProfile.constant(z_top=0, z_bottom=-10),
            constraints=Constraints(keepouts=(keepout,)),
            metadata={"hint_type": "pocket", "shape": "Rect"},
        )
        hints = removal_intents_to_hints([intent1, intent2])

        assert "keepouts" in hints
        assert len(hints["keepouts"]) == 1


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
            metadata={"hint_type": "profile", "shape": "Rect"},
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
            metadata={"hint_type": "pocket", "shape": "Rect"},
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
            metadata={"hint_type": "profile", "shape": "Rect"},
        )
        planner_input = removal_intents_to_planner_input([intent])

        assert len(planner_input.profiles) == 1
        profile = planner_input.profiles[0]
        assert profile.tabs is not None
        assert profile.tabs.count == 4
        assert profile.tabs.height_mm == 3.0
        assert profile.tabs.width_mm == 10.0


class TestConstraintCoverageEnforcement:

    def test_all_constraint_fields_documented(self):
        from ir.removal_intent import Constraints
        import dataclasses

        constraint_fields = {f.name for f in dataclasses.fields(Constraints)}
        documented = {
            "tabs",
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
        constraint_keys_in_caps = [
            k for k in PLANNER_CAPABILITIES.keys()
            if k.startswith("constraints.")
        ]
        expected = {
            "constraints.tabs",
            "constraints.keepouts",
            "constraints.islands",
            "constraints.edge_treatment",
            "constraints.tolerance_mm",
            "constraints.safe_z_mm",
        }
        actual = set(constraint_keys_in_caps)
        assert actual == expected, (
            f"Constraint field(s) missing from PLANNER_CAPABILITIES: {expected - actual}"
        )
