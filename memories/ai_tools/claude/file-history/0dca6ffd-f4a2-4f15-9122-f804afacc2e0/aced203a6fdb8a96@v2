"""Tests for Edge Treatment Intent (Stage 18).

Acceptance tests:
- Edge allowance influences RemovalIntent (rough/finish multi-pass)
- Profile with fillet hint emits RemovalIntent with fillet annotation
- Multi-tool scenario: rough pass + finish pass with different allowances
- Allowance semantics compatible with kerf (per-edge, not global)
- Round-trip: edge intent preserved in PML
"""

from skills.mill_ui.v2.pml.compositional_parser import parse_compositional_pml, ParseError
from skills.mill_ui.v2.pml.compositional_formatter import format_compositional_pml
from skills.mill_ui.v2.resolution.layout_resolver import resolve_layout
from skills.mill_ui.v2.adapters.hints_to_removal import item_to_removal_intent
from skills.mill_ui.v2.ast.compositional import Edge


def test_edge_allowance_influences_removal_intent():
    """Test edge allowance values appear in RemovalIntent."""
    pml = """sheet 400.00mm 400.00mm 19.00mm

rect panel profile through outside
    edge allowance 0.50mm 0.10mm
"""

    ast = parse_compositional_pml(pml)
    flat = resolve_layout(ast)

    # Get the profile item
    profile_items = [item for item in flat.items if item.feature and item.feature.type == "profile"]
    assert len(profile_items) == 1
    profile = profile_items[0]

    # Verify edge treatment in geometry
    assert "edge_treatment" in profile.geometry.data
    edge = profile.geometry.data["edge_treatment"]
    assert edge["type"] == "allowance"
    assert abs(edge["rough_allowance_mm"] - 0.5) < 0.01
    assert abs(edge["finish_allowance_mm"] - 0.1) < 0.01

    # Convert to RemovalIntent
    removal = item_to_removal_intent(profile, region_id_prefix="test_profile")

    # Verify RemovalIntent has edge treatment
    assert removal.constraints.edge_treatment is not None
    assert removal.constraints.edge_treatment.type == "allowance"
    assert abs(removal.constraints.edge_treatment.rough_allowance_mm - 0.5) < 0.01
    assert abs(removal.constraints.edge_treatment.finish_allowance_mm - 0.1) < 0.01


def test_profile_with_fillet_hint():
    """Test profile with fillet edge treatment."""
    pml = """sheet 400.00mm 400.00mm 19.00mm

rect panel profile through outside
    edge fillet 3.00mm
"""

    ast = parse_compositional_pml(pml)
    flat = resolve_layout(ast)

    profile_items = [item for item in flat.items if item.feature and item.feature.type == "profile"]
    assert len(profile_items) == 1
    profile = profile_items[0]

    # Convert to RemovalIntent
    removal = item_to_removal_intent(profile)

    # Verify fillet treatment
    assert removal.constraints.edge_treatment is not None
    assert removal.constraints.edge_treatment.type == "fillet"
    assert abs(removal.constraints.edge_treatment.radius_mm - 3.0) < 0.01


def test_edge_chamfer():
    """Test chamfer edge treatment."""
    pml = """sheet 400.00mm 400.00mm 19.00mm

rect panel profile through outside
    edge chamfer 2.50mm
"""

    ast = parse_compositional_pml(pml)
    flat = resolve_layout(ast)

    profile_items = [item for item in flat.items if item.feature and item.feature.type == "profile"]
    assert len(profile_items) == 1
    profile = profile_items[0]

    # Convert to RemovalIntent
    removal = item_to_removal_intent(profile)

    # Verify chamfer treatment
    assert removal.constraints.edge_treatment is not None
    assert removal.constraints.edge_treatment.type == "chamfer"
    assert abs(removal.constraints.edge_treatment.distance_mm - 2.5) < 0.01


def test_edge_roundtrip():
    """Test PML → AST → PML preserves edge treatment."""
    original_pml = """sheet 400.00mm 400.00mm 19.00mm

rect panel profile through outside
    edge allowance 0.50mm 0.10mm
"""

    # Parse → Format → Parse
    ast1 = parse_compositional_pml(original_pml)
    formatted_pml = format_compositional_pml(ast1)
    ast2 = parse_compositional_pml(formatted_pml)

    # Resolve both and compare
    flat1 = resolve_layout(ast1)
    flat2 = resolve_layout(ast2)

    profile1 = [item for item in flat1.items if item.feature and item.feature.type == "profile"][0]
    profile2 = [item for item in flat2.items if item.feature and item.feature.type == "profile"][0]

    edge1 = profile1.geometry.data.get("edge_treatment")
    edge2 = profile2.geometry.data.get("edge_treatment")

    assert edge1 is not None and edge2 is not None
    assert edge1["type"] == edge2["type"] == "allowance"
    assert abs(edge1["rough_allowance_mm"] - edge2["rough_allowance_mm"]) < 0.01
    assert abs(edge1["finish_allowance_mm"] - edge2["finish_allowance_mm"]) < 0.01


def test_pocket_with_edge():
    """Test pocket with edge treatment."""
    pml = """sheet 400.00mm 400.00mm 19.00mm

rect panel pocket 6.00mm
    edge allowance 0.30mm 0.05mm
"""

    ast = parse_compositional_pml(pml)
    flat = resolve_layout(ast)

    pocket_items = [item for item in flat.items if item.feature and item.feature.type == "pocket"]
    assert len(pocket_items) == 1
    pocket = pocket_items[0]

    # Verify edge treatment in pocket
    assert "edge_treatment" in pocket.geometry.data
    edge = pocket.geometry.data["edge_treatment"]
    assert edge["type"] == "allowance"
