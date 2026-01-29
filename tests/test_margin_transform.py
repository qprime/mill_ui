
from __future__ import annotations

import pytest

from pml.yaml_parser import parse_pml_yaml
from resolution.layout_resolver import resolve_layout
from cam.pipeline import run_pipeline
from cam.post.gcode import _apply_margin_offset
from validation.removal_checks import check_working_area_bounds
from adapters.ast_to_removal import ast_to_removal_intents


class TestSheetWorkingArea:

    def test_sheet_working_dimensions(self):
        pml = """
Sheet:
  width: 1200mm
  height: 800mm
  thickness: 19mm
  margin: 10mm
children: []
"""
        ast = parse_pml_yaml(pml)
        assert ast.sheet.width_mm == 1200.0
        assert ast.sheet.height_mm == 800.0
        assert ast.sheet.margin_mm == 10.0
        assert ast.sheet.working_width_mm == 1180.0
        assert ast.sheet.working_height_mm == 780.0

    def test_physical_width_alias(self):
        pml = """
Sheet:
  physical_width: 1200mm
  physical_height: 800mm
  thickness: 19mm
  margin: 10mm
children: []
"""
        ast = parse_pml_yaml(pml)
        assert ast.sheet.width_mm == 1200.0
        assert ast.sheet.height_mm == 800.0
        assert ast.sheet.physical_width_mm == 1200.0
        assert ast.sheet.physical_height_mm == 800.0

    def test_zero_margin_working_equals_physical(self):
        pml = """
Sheet:
  width: 1200mm
  height: 800mm
  thickness: 19mm
  margin: 0mm
children: []
"""
        ast = parse_pml_yaml(pml)
        assert ast.sheet.working_width_mm == ast.sheet.width_mm
        assert ast.sheet.working_height_mm == ast.sheet.height_mm


class TestMarginTransformGcode:

    def test_margin_offset_applied_to_moves(self):
        moves = [
            {"kind": "rapid", "x": 100.0, "y": 200.0, "z": 5.0},
            {"kind": "linear", "x": 150.0, "y": 250.0, "z": -5.0},
        ]
        margin = 10.0
        offset_moves = _apply_margin_offset(moves, margin)

        assert offset_moves[0]["x"] == 110.0
        assert offset_moves[0]["y"] == 210.0
        assert offset_moves[0]["z"] == 5.0

        assert offset_moves[1]["x"] == 160.0
        assert offset_moves[1]["y"] == 260.0
        assert offset_moves[1]["z"] == -5.0

    def test_zero_margin_no_offset(self):
        moves = [{"kind": "rapid", "x": 100.0, "y": 200.0, "z": 5.0}]
        offset_moves = _apply_margin_offset(moves, 0.0)
        assert offset_moves[0]["x"] == 100.0
        assert offset_moves[0]["y"] == 200.0

    def test_none_coordinates_preserved(self):
        moves = [{"kind": "set_rpm", "rpm": 10000}]
        offset_moves = _apply_margin_offset(moves, 10.0)
        assert "x" not in offset_moves[0]
        assert "y" not in offset_moves[0]


class TestResolverWorkingArea:

    def test_resolver_uses_working_area(self):
        pml = """
Sheet:
  width: 1200mm
  height: 800mm
  thickness: 19mm
  margin: 10mm
children:
  - Rect:
      id: full_area
      children:
        - Profile:
            side: outside
            depth: through
"""
        ast = parse_pml_yaml(pml)
        layout_ast = resolve_layout(ast)

        rect_item = None
        for item in layout_ast.items:
            if item.kind == "shape" and item.type == "Rect":
                rect_item = item
                break

        assert rect_item is not None
        cx, cy = rect_item.placement.center_xy_mm
        assert cx == 590.0
        assert cy == 390.0

        w = rect_item.geometry.data["w_mm"]
        h = rect_item.geometry.data["h_mm"]
        assert w == 1180.0
        assert h == 780.0


class TestWorkingAreaValidation:

    def test_valid_coordinates_pass(self):
        pml = """
Sheet:
  width: 500mm
  height: 400mm
  thickness: 19mm
  margin: 10mm
children:
  - Rect:
      id: part
      feature:
        type: profile
        depth: through
        side: outside
      at:
        x: 240mm
        y: 190mm
        width: 200mm
        height: 150mm
"""
        ast = parse_pml_yaml(pml)
        layout_ast = resolve_layout(ast)
        intents = ast_to_removal_intents(layout_ast)

        result = check_working_area_bounds(
            intents,
            working_width_mm=ast.sheet.working_width_mm,
            working_height_mm=ast.sheet.working_height_mm,
            tool_radius_mm=3.0,
        )
        assert not result.has_issues()

    def test_coordinates_exceeding_working_area_detected(self):
        pml = """
Sheet:
  width: 500mm
  height: 400mm
  thickness: 19mm
  margin: 10mm
children:
  - Rect:
      id: part
      feature:
        type: profile
        depth: through
        side: outside
      at:
        x: 470mm
        y: 190mm
        width: 100mm
        height: 100mm
"""
        ast = parse_pml_yaml(pml)
        layout_ast = resolve_layout(ast)
        intents = ast_to_removal_intents(layout_ast)

        result = check_working_area_bounds(
            intents,
            working_width_mm=ast.sheet.working_width_mm,
            working_height_mm=ast.sheet.working_height_mm,
            tool_radius_mm=3.0,
        )
        assert result.has_issues()
        assert any("right" in e.message for e in result.errors)

    def test_outside_profile_cutting_edge_encroachment_detected(self):
        pml = """
Sheet:
  width: 500mm
  height: 400mm
  thickness: 19mm
  margin: 10mm
children:
  - Rect:
      id: part
      feature:
        type: profile
        depth: through
        side: outside
      at:
        x: 103.175mm
        y: 78.175mm
        width: 200mm
        height: 150mm
"""
        ast = parse_pml_yaml(pml)
        layout_ast = resolve_layout(ast)
        intents = ast_to_removal_intents(layout_ast)

        result = check_working_area_bounds(
            intents,
            working_width_mm=ast.sheet.working_width_mm,
            working_height_mm=ast.sheet.working_height_mm,
            tool_radius_mm=3.175,
        )
        assert result.has_issues()
        assert any("left" in e.message or "bottom" in e.message for e in result.errors)

    def test_outside_profile_with_full_tool_diameter_clearance_passes(self):
        pml = """
Sheet:
  width: 500mm
  height: 400mm
  thickness: 19mm
  margin: 10mm
children:
  - Rect:
      id: part
      feature:
        type: profile
        depth: through
        side: outside
      at:
        x: 106.5mm
        y: 81.5mm
        width: 200mm
        height: 150mm
"""
        ast = parse_pml_yaml(pml)
        layout_ast = resolve_layout(ast)
        intents = ast_to_removal_intents(layout_ast)

        result = check_working_area_bounds(
            intents,
            working_width_mm=ast.sheet.working_width_mm,
            working_height_mm=ast.sheet.working_height_mm,
            tool_radius_mm=3.175,
        )
        assert not result.has_issues()


class TestPipelineMarginIntegration:

    def test_pipeline_applies_margin_to_gcode(self):
        pml = """
Sheet:
  width: 450mm
  height: 650mm
  thickness: 19mm
  margin: 10mm
children:
  - Rect:
      id: part
      feature:
        type: profile
        depth: through
        side: outside
      at:
        x: 215mm
        y: 315mm
        width: 200mm
        height: 150mm
"""
        ast = parse_pml_yaml(pml)
        layout_ast = resolve_layout(ast)

        result = run_pipeline(layout_ast, kerf_mm=3.175, generate_svg=False)

        assert result.gcode
        for name, gcode in result.gcode.items():
            if "profile" in name:
                lines_with_coords = [
                    l for l in gcode.split('\n')
                    if ('X' in l or 'Y' in l) and ('G0' in l or 'G1' in l)
                ]
                assert lines_with_coords
                first_line = lines_with_coords[0]
                x_val = float(first_line.split('X')[1].split()[0].rstrip('YZ'))
                y_val = float(first_line.split('Y')[1].split()[0].rstrip('XZ'))
                assert x_val >= 10.0
                assert y_val >= 10.0
