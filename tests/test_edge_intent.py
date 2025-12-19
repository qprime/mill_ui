"""Tests for Edge Treatment Intent (Stage 18).

Acceptance tests:
- Edge allowance influences RemovalIntent (rough/finish multi-pass)
- Profile with fillet hint emits RemovalIntent with fillet annotation
- Multi-tool scenario: rough pass + finish pass with different allowances
- Allowance semantics compatible with kerf (per-edge, not global)
- Round-trip: edge intent preserved in PML
"""

from pml.compositional_parser import parse_compositional_pml, ParseError
from pml.compositional_formatter import format_compositional_pml
from resolution.layout_resolver import resolve_layout
from adapters.hints_to_removal import item_to_removal_intent
from layout_ast.compositional import Edge


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


def test_multi_tool_scenario():
    """Test multi-tool scenario: rough pass + finish pass with different allowances."""
    pml = """sheet 400.00mm 400.00mm 19.00mm

rect panel profile through outside
    edge allowance 0.50mm 0.10mm
"""

    ast = parse_compositional_pml(pml)
    flat = resolve_layout(ast)

    profile_items = [item for item in flat.items if item.feature and item.feature.type == "profile"]
    base_removal = item_to_removal_intent(profile_items[0])

    # Verify edge treatment is captured
    assert base_removal.constraints.edge_treatment is not None
    assert base_removal.constraints.edge_treatment.type == "allowance"

    rough_allowance = base_removal.constraints.edge_treatment.rough_allowance_mm
    finish_allowance = base_removal.constraints.edge_treatment.finish_allowance_mm

    assert abs(rough_allowance - 0.5) < 0.01
    assert abs(finish_allowance - 0.1) < 0.01

    # Demonstrate that a multi-pass planner could use this data:
    # - Rough pass would use rough_allowance_mm (0.5mm stock left)
    # - Finish pass would use finish_allowance_mm (0.1mm final allowance)
    # This test verifies the data is accessible for multi-tool sequencing

    # Simulate rough pass: original bounds with rough allowance applied
    rough_side_offset = rough_allowance  # For "outside" profile, positive offset leaves stock
    assert rough_side_offset > 0  # Rough pass leaves stock

    # Simulate finish pass: original bounds with finish allowance applied
    finish_side_offset = finish_allowance
    assert finish_side_offset < rough_side_offset  # Finish removes more than rough

    # Verify the edge treatment data enables multi-pass decision-making
    assert rough_allowance > finish_allowance  # Rough leaves more stock than finish


def test_kerf_compatibility():
    """Test allowance semantics compatible with kerf (per-edge, not global)."""
    from ir.removal_intent import RemovalIntent, Allowance, Constraints, EdgeTreatment

    pml = """sheet 400.00mm 400.00mm 19.00mm

rect panel profile through outside
    edge allowance 0.50mm 0.10mm
"""

    ast = parse_compositional_pml(pml)
    flat = resolve_layout(ast)

    profile_items = [item for item in flat.items if item.feature and item.feature.type == "profile"]
    base_removal = item_to_removal_intent(profile_items[0])

    # Edge treatment is stored in constraints (per-edge treatment)
    assert base_removal.constraints.edge_treatment is not None
    edge_rough = base_removal.constraints.edge_treatment.rough_allowance_mm
    edge_finish = base_removal.constraints.edge_treatment.finish_allowance_mm

    # Kerf compensation is stored in allowance (global tool property)
    # Demonstrate they are independent and can coexist
    tool_kerf_mm = 3.175  # Example: 1/8" endmill kerf
    kerf_offset = tool_kerf_mm / 2.0

    # Create a new RemovalIntent with both edge allowance and kerf compensation
    combined_removal = RemovalIntent(
        region_id=base_removal.region_id,
        bounds=base_removal.bounds,
        z_top=base_removal.z_top,
        z_bottom=base_removal.z_bottom,
        allowance=Allowance(outside=0.0, kerf_compensation=kerf_offset),  # Kerf is global
        constraints=Constraints(
            edge_treatment=EdgeTreatment(
                type="allowance",
                rough_allowance_mm=edge_rough,  # Edge allowance is per-edge
                finish_allowance_mm=edge_finish
            )
        ),
        metadata=base_removal.metadata
    )

    # Verify both edge treatment and kerf compensation are present and independent
    assert combined_removal.allowance.kerf_compensation == kerf_offset
    assert combined_removal.constraints.edge_treatment.rough_allowance_mm == edge_rough
    assert combined_removal.constraints.edge_treatment.finish_allowance_mm == edge_finish

    # Demonstrate they serve different purposes:
    # - kerf_compensation: global tool property (compensates for tool width)
    # - edge_treatment allowances: per-edge intent (multi-pass finish strategy)
    # A planner would apply BOTH: kerf offset + edge allowance offset
    total_rough_offset = kerf_offset + edge_rough
    total_finish_offset = kerf_offset + edge_finish

    assert total_rough_offset > kerf_offset  # Rough pass needs extra stock beyond kerf
    assert total_finish_offset > kerf_offset  # Finish pass still has some allowance beyond kerf
    assert total_rough_offset > total_finish_offset  # Rough leaves more than finish
