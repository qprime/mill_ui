"""Unit tests for PML roundtrip: PML → AST → JSON → AST semantic equivalence.

Stage 11 acceptance tests.
"""

from __future__ import annotations

import json
import pytest

from pml import parse_pml, format_pml, PMLParseError


def test_pml_parse_minimal_layout():
    """Test parsing minimal valid PML layout."""
    pml = """
sheet 450mm 650mm 19mm

rect outer at 225mm,325mm size 400mm,600mm profile through outside
"""

    ast = parse_pml(pml)

    assert ast.sheet.width_mm == 450.0
    assert ast.sheet.height_mm == 650.0
    assert ast.sheet.thickness_mm == 19.0
    assert len(ast.items) == 1

    item = ast.items[0]
    assert item.kind == "shape"
    assert item.type == "Rect"
    assert item.shape_id == "outer"
    assert item.geometry.data["w_mm"] == 400.0
    assert item.geometry.data["h_mm"] == 600.0
    assert item.placement.center_xy_mm == (225.0, 325.0)
    assert item.feature.type == "profile"
    assert item.feature.depth == "through"
    assert item.feature.side == "outside"


def test_pml_parse_with_metadata():
    """Test parsing PML with project and kerf metadata."""
    pml = """
project test_panel
kerf 0.15mm

sheet 300mm 400mm 19mm

rect panel at 150mm,200mm size 200mm,300mm pocket 5mm
"""

    ast = parse_pml(pml)

    assert ast.project == "test_panel"
    assert ast.kerf_width_mm == 0.15
    assert ast.sheet.width_mm == 300.0


def test_pml_parse_multiple_shapes():
    """Test parsing PML with multiple shapes."""
    pml = """
sheet 450mm 650mm 19mm

rect door:outer at 225mm,325mm size 400mm,600mm profile through outside
rect door:panel at 225mm,325mm size 300mm,500mm pocket 6mm
circle door:anchor:1 at 95mm,545mm diameter 10mm hole 8mm
circle door:anchor:2 at 355mm,545mm diameter 10mm hole 8mm
"""

    ast = parse_pml(pml)

    assert len(ast.items) == 4

    # Verify outer profile
    outer = ast.items[0]
    assert outer.shape_id == "door:outer"
    assert outer.type == "Rect"
    assert outer.feature.type == "profile"

    # Verify panel pocket
    panel = ast.items[1]
    assert panel.shape_id == "door:panel"
    assert panel.type == "Rect"
    assert panel.feature.type == "pocket"
    assert panel.feature.depth_mm == 6.0

    # Verify anchor holes
    anchor1 = ast.items[2]
    assert anchor1.shape_id == "door:anchor:1"
    assert anchor1.type == "Circle"
    assert anchor1.feature.type == "hole"
    assert anchor1.feature.depth_mm == 8.0


def test_pml_parse_circle_diameter_vs_radius():
    """Test parsing circles with both diameter and radius syntax."""
    pml = """
sheet 200mm 200mm 19mm

circle hole1 at 50mm,50mm diameter 20mm hole through
circle hole2 at 150mm,150mm radius 8mm hole 12mm
"""

    ast = parse_pml(pml)

    assert len(ast.items) == 2

    # Diameter syntax
    hole1 = ast.items[0]
    assert "diameter_mm" in hole1.geometry.data
    assert hole1.geometry.data["diameter_mm"] == 20.0

    # Radius syntax
    hole2 = ast.items[1]
    assert "radius_mm" in hole2.geometry.data
    assert hole2.geometry.data["radius_mm"] == 8.0


def test_pml_parse_roundedrect():
    """Test parsing RoundedRect shape."""
    pml = """
sheet 300mm 300mm 19mm

roundedrect panel at 150mm,150mm size 200mm,150mm radius 10mm pocket 5mm
"""

    ast = parse_pml(pml)

    assert len(ast.items) == 1

    item = ast.items[0]
    assert item.type == "RoundedRect"
    assert item.geometry.data["w_mm"] == 200.0
    assert item.geometry.data["h_mm"] == 150.0
    assert item.geometry.data["corner_radius_mm"] == 10.0
    assert item.feature.type == "pocket"


def test_pml_parse_comments_and_blank_lines():
    """Test that comments and blank lines are ignored."""
    pml = """
# This is a comment
sheet 300mm 400mm 19mm

# Another comment

rect panel at 150mm,200mm size 200mm,300mm profile through inside

# Final comment
"""

    ast = parse_pml(pml)

    assert len(ast.items) == 1
    assert ast.sheet.width_mm == 300.0


def test_pml_parse_error_missing_sheet():
    """Test error when sheet declaration is missing."""
    pml = """
rect panel at 150mm,200mm size 200mm,300mm profile through inside
"""

    with pytest.raises(PMLParseError, match="Missing required 'sheet' declaration"):
        parse_pml(pml)


def test_pml_parse_error_invalid_sheet_syntax():
    """Test error on invalid sheet syntax."""
    pml = "sheet 300 400 19"  # Missing 'mm' suffix

    with pytest.raises(PMLParseError, match="Invalid sheet syntax"):
        parse_pml(pml)


def test_pml_parse_error_invalid_feature():
    """Test error on invalid feature type."""
    pml = """
sheet 300mm 400mm 19mm
rect panel at 150mm,200mm size 200mm,300mm invalid_feature 5mm
"""

    with pytest.raises(PMLParseError, match="Unknown feature type"):
        parse_pml(pml)


def test_pml_parse_error_invalid_profile_side():
    """Test error on invalid profile side."""
    pml = """
sheet 300mm 400mm 19mm
rect panel at 150mm,200mm size 200mm,300mm profile through bad_side
"""

    with pytest.raises(PMLParseError, match="Invalid profile side"):
        parse_pml(pml)


def test_pml_format_minimal_layout():
    """Test formatting minimal LayoutAST to PML."""
    from layout_ast.layout import LayoutAST, Sheet, Item, Geometry, Placement, Feature

    ast = LayoutAST(
        sheet=Sheet(width_mm=450.0, height_mm=650.0, thickness_mm=19.0),
        items=(
            Item(
                kind="shape",
                type="Rect",
                geometry=Geometry(data={"w_mm": 400.0, "h_mm": 600.0}),
                placement=Placement(center_xy_mm=(225.0, 325.0)),
                feature=Feature(type="profile", depth="through", side="outside"),
                shape_id="outer",
            ),
        ),
    )

    pml = format_pml(ast)

    assert "sheet 450.00mm 650.00mm 19.00mm" in pml
    assert "rect outer at 225.00mm,325.00mm size 400.00mm,600.00mm profile through outside" in pml


def test_pml_format_with_metadata():
    """Test formatting LayoutAST with project and kerf metadata."""
    from layout_ast.layout import LayoutAST, Sheet, Item, Geometry, Placement, Feature

    ast = LayoutAST(
        sheet=Sheet(width_mm=300.0, height_mm=400.0, thickness_mm=19.0),
        items=(
            Item(
                kind="shape",
                type="Rect",
                geometry=Geometry(data={"w_mm": 200.0, "h_mm": 300.0}),
                placement=Placement(center_xy_mm=(150.0, 200.0)),
                feature=Feature(type="pocket", depth="5.0", depth_mm=5.0),
                shape_id="panel",
            ),
        ),
        project="test_panel",
        kerf_width_mm=0.15,
    )

    pml = format_pml(ast)

    assert "project test_panel" in pml
    assert "kerf 0.15mm" in pml


def test_pml_roundtrip_semantic_equivalence():
    """Test PML → AST → PML preserves semantics (not formatting)."""
    original_pml = """
# Comment (will be lost)
project shaker_door

sheet 450mm 650mm 19mm

rect door:outer at 225mm,325mm size 400mm,600mm profile through outside
rect door:panel at 225mm,325mm size 300mm,500mm pocket 6mm
"""

    # Parse original
    ast1 = parse_pml(original_pml)

    # Format to canonical PML
    canonical_pml = format_pml(ast1)

    # Parse canonical
    ast2 = parse_pml(canonical_pml)

    # Verify semantic equivalence (not formatting equivalence)
    assert ast1.sheet.width_mm == ast2.sheet.width_mm
    assert ast1.sheet.height_mm == ast2.sheet.height_mm
    assert ast1.sheet.thickness_mm == ast2.sheet.thickness_mm
    assert ast1.project == ast2.project
    assert len(ast1.items) == len(ast2.items)

    for item1, item2 in zip(ast1.items, ast2.items):
        assert item1.kind == item2.kind
        assert item1.type == item2.type
        assert item1.shape_id == item2.shape_id
        assert item1.placement.center_xy_mm == item2.placement.center_xy_mm
        assert item1.feature.type == item2.feature.type
        assert item1.feature.depth == item2.feature.depth


def test_pml_to_json_to_ast_semantic_equivalence():
    """Test PML → AST → JSON → AST preserves semantics."""
    pml = """
project test_panel
kerf 0.15mm

sheet 450mm 650mm 19mm

rect door:outer at 225mm,325mm size 400mm,600mm profile through outside
rect door:panel at 225mm,325mm size 300mm,500mm pocket 6mm
circle door:anchor:1 at 95mm,545mm diameter 10mm hole 8mm
"""

    # PML → AST
    ast1 = parse_pml(pml)

    # AST → JSON
    json_str = ast1.to_json()
    json_dict = json.loads(json_str)

    # Verify JSON structure
    assert "sheet" in json_dict
    assert "items" in json_dict
    assert json_dict["sheet"]["thickness_mm"] == 19.0
    assert len(json_dict["items"]) == 3
    assert json_dict.get("project") == "test_panel"
    assert json_dict.get("kerf_width_mm") == 0.15

    # Verify semantic preservation
    assert ast1.sheet.thickness_mm == 19.0
    assert len(ast1.items) == 3
    assert ast1.project == "test_panel"
    assert ast1.kerf_width_mm == 0.15


def test_pml_canonical_formatting():
    """Test that PML formatter produces canonical formatting."""
    pml_input = """
sheet 450.123mm 650.456mm 19.789mm
rect test at 100.1mm,200.2mm size 50.5mm,60.6mm pocket 5.123mm
"""

    ast = parse_pml(pml_input)
    canonical_pml = format_pml(ast)

    # Verify 2 decimal place precision
    assert "450.12mm" in canonical_pml
    assert "650.46mm" in canonical_pml
    assert "19.79mm" in canonical_pml
    assert "100.10mm" in canonical_pml
    assert "200.20mm" in canonical_pml
    assert "5.12mm" in canonical_pml
