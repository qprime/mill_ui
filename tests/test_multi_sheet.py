from __future__ import annotations

import pytest

from pml.yaml_parser import parse_pml_yaml
from resolution.layout_resolver import ResolutionAssertionError, resolve_layout, resolve_layout_multi

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
    def test_single_sheet_unchanged(self):
        comp_ast = parse_pml_yaml(SMALL_BOX_PML)
        results = resolve_layout_multi(comp_ast)
        assert len(results) == 1
        single = resolve_layout(comp_ast)
        assert len(results[0].items) == len(single.items)

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
