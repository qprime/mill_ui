from __future__ import annotations

import pytest

from adapters.ast_to_removal import ast_to_removal_intents
from pml.yaml_parser import parse_pml_yaml
from resolution.layout_resolver import ResolutionAssertionError, resolve_layout, resolve_layout_multi
from validation.removal_checks import check_working_area_bounds

SMALL_BOX_PML = """\
Sheet:
  width: 800mm
  height: 600mm
  thickness: 6mm
  margin: 10mm
  material: mdf
children:
- Assembly:
    type: box
    width: 200mm
    depth: 150mm
    height: 100mm
    thickness: 6mm
    joinery: finger
    finger_width: 12mm
    clearance: 0.15mm
    bottom: captured
    top: none
    show_labels: true
"""

LARGE_BOX_PML = """\
Sheet:
  width: 500mm
  height: 500mm
  thickness: 6mm
  margin: 10mm
  material: mdf
children:
- Assembly:
    type: box
    width: 400mm
    depth: 300mm
    height: 200mm
    thickness: 6mm
    joinery: finger
    finger_width: 12mm
    clearance: 0.15mm
    bottom: captured
    top: none
    show_labels: true
"""

MIXED_CONTENT_OVERFLOW_PML = """\
Sheet:
  width: 500mm
  height: 500mm
  thickness: 6mm
  margin: 10mm
  material: mdf
children:
- Rect:
    feature: {type: pocket, depth: 3mm}
- Assembly:
    type: box
    width: 400mm
    depth: 300mm
    height: 200mm
    thickness: 6mm
    joinery: finger
    finger_width: 12mm
    clearance: 0.15mm
    bottom: captured
    top: none
"""


class TestResolveLayoutMulti:
    def test_carcass_partitions_are_rejected_instead_of_omitted(self):
        pml = """Sheet:
  width: 1220mm
  height: 1220mm
  thickness: 18mm
children:
- Assembly:
    type: carcass
    width: 500mm
    depth: 300mm
    height: 600mm
    thickness: 18mm
    vertical_partitions: 2
    fixed_shelves: 3
"""
        with pytest.raises(ResolutionAssertionError, match="vertical_partitions is not implemented; got 2"):
            resolve_layout_multi(parse_pml_yaml(pml))

    @pytest.mark.parametrize(
        "assembly",
        [
            """type: carcass
    width: 500mm
    depth: 300mm
    height: 600mm
    thickness: 18mm
    fixed_shelves: 2
    shelf_joinery: dado
    back: none""",
            """type: cubby
    width: 900mm
    depth: 300mm
    height: 600mm
    thickness: 18mm
    grid: [3, 2]
    perimeter_joinery: finger
    internal_joinery: half_lap
    back: captured""",
        ],
        ids=["single_sheet_shelves", "multiple_sheet_dividers"],
    )
    def test_packed_profiles_stay_on_sheet_with_clearance(self, assembly):
        pml = f"""Sheet:
  physical_width: 1220mm
  physical_height: 1220mm
  thickness: 18mm
  margin: 10mm
children:
- Assembly:
    {assembly}
"""
        results = resolve_layout_multi(parse_pml_yaml(pml))

        assert results
        for ast in results:
            profiles = [intent for intent in ast_to_removal_intents(ast) if intent.hint_type == "profile"]
            assert profiles
            bounds_result = check_working_area_bounds(
                profiles, ast.sheet.working_width_mm, ast.sheet.working_height_mm, tool_radius_mm=3.175
            )
            assert not bounds_result.errors
            for index, a in enumerate(profiles):
                for b in profiles[index + 1 :]:
                    assert (
                        a.bounds.x_max <= b.bounds.x_min
                        or b.bounds.x_max <= a.bounds.x_min
                        or a.bounds.y_max <= b.bounds.y_min
                        or b.bounds.y_max <= a.bounds.y_min
                    )

    def test_single_sheet_unchanged(self):
        comp_ast = parse_pml_yaml(SMALL_BOX_PML)
        results = resolve_layout_multi(comp_ast)
        assert len(results) == 1
        single = resolve_layout(comp_ast)
        assert len(results[0].items) == len(single.items)

    def test_multiple_assemblies_on_one_sheet_are_preserved(self):
        from dataclasses import replace

        from layout_ast.compositional import Panel

        ast = parse_pml_yaml(SMALL_BOX_PML)
        assert ast.root is not None
        node = ast.root.children[0]
        single = resolve_layout_multi(ast)[0]
        double = resolve_layout_multi(replace(ast, root=Panel(children=(node, node))))[0]

        assert len(double.items) == 2 * len(single.items)

    def test_multi_sheet_produces_multiple_asts(self):
        comp_ast = parse_pml_yaml(LARGE_BOX_PML)
        results = resolve_layout_multi(comp_ast)
        assert len(results) > 1

    def test_each_ast_has_correct_sheet(self):
        comp_ast = parse_pml_yaml(LARGE_BOX_PML)
        results = resolve_layout_multi(comp_ast)
        for ast in results:
            assert ast.sheet.width_mm == 500
            assert ast.sheet.height_mm == 500

    def test_all_panels_accounted_for(self):
        comp_ast = parse_pml_yaml(LARGE_BOX_PML)
        results = resolve_layout_multi(comp_ast)

        from resolution.layout_resolver import (
            LayoutResolver,
            _find_assembly_node,
        )

        node = _find_assembly_node(comp_ast.root)
        assert node is not None
        resolver = LayoutResolver(comp_ast)
        panel_specs = resolver._build_assembly(node).resolve()

        profile_items = sum(
            1 for ast in results for item in ast.items if item.feature and item.feature.type == "profile"
        )
        assert profile_items == len(panel_specs)

    def test_labels_preserved(self):
        comp_ast = parse_pml_yaml(LARGE_BOX_PML)
        results = resolve_layout_multi(comp_ast)
        labels = [item.label for ast in results for item in ast.items if item.label is not None]
        assert len(labels) > 0

    def test_non_assembly_pml_unchanged(self):
        pml = """\
Sheet:
  width: 400mm
  height: 400mm
  thickness: 6mm
  margin: 10mm
  material: mdf
children:
- Rect:
    feature: {type: pocket, depth: 3mm}
"""
        comp_ast = parse_pml_yaml(pml)
        results = resolve_layout_multi(comp_ast)
        assert len(results) == 1

    def test_resolve_layout_raises_on_multi_sheet(self):
        comp_ast = parse_pml_yaml(LARGE_BOX_PML)
        with pytest.raises(ResolutionAssertionError, match="Use resolve_layout_multi"):
            resolve_layout(comp_ast)

    def test_resolve_layout_delegates_single_sheet(self):
        comp_ast = parse_pml_yaml(SMALL_BOX_PML)
        single = resolve_layout(comp_ast)
        multi = resolve_layout_multi(comp_ast)
        assert len(multi) == 1
        assert len(single.items) == len(multi[0].items)

    def test_mixed_content_single_sheet_ok(self):
        pml = """\
Sheet:
  width: 800mm
  height: 600mm
  thickness: 6mm
  margin: 10mm
  material: mdf
children:
- Rect:
    feature: {type: pocket, depth: 3mm}
- Assembly:
    type: box
    width: 200mm
    depth: 150mm
    height: 100mm
    thickness: 6mm
    joinery: finger
    finger_width: 12mm
    clearance: 0.15mm
    bottom: captured
    top: none
"""
        comp_ast = parse_pml_yaml(pml)
        results = resolve_layout_multi(comp_ast)
        assert len(results) == 1
        has_pocket = any(item.feature and item.feature.type == "pocket" for item in results[0].items)
        has_profile = any(item.feature and item.feature.type == "profile" for item in results[0].items)
        assert has_pocket
        assert has_profile

    def test_mixed_content_multi_sheet_error(self):
        comp_ast = parse_pml_yaml(MIXED_CONTENT_OVERFLOW_PML)
        with pytest.raises(ResolutionAssertionError, match="non-assembly items"):
            resolve_layout_multi(comp_ast)

    def test_shape_ids_per_sheet_isolated(self):
        comp_ast = parse_pml_yaml(LARGE_BOX_PML)
        results = resolve_layout_multi(comp_ast)
        assert len(results) > 1
        for ast in results:
            ids = [item.shape_id for item in ast.items if item.shape_id]
            assert len(ids) == len(set(ids)), "Shape IDs should be unique within a sheet"
