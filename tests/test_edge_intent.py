from adapters.hints_to_removal import simple_item_to_removal_intent
from ir.removal_intent import DepthProfile
from pml.yaml_formatter import format_pml_yaml
from pml.yaml_parser import parse_pml_yaml
from resolution.layout_resolver import resolve_layout


def test_edge_allowance_influences_removal_intent():
    pml = """
Sheet:
  width: 400mm
  height: 400mm
  thickness: 19mm

children:
  - Rect:
      id: panel
      children:
        - Profile:
            side: outside
            depth: through
        - Edge:
            treatment: allowance
            rough_allowance: 0.5mm
            finish_allowance: 0.1mm
"""

    ast = parse_pml_yaml(pml)
    flat = resolve_layout(ast)

    profile_items = [item for item in flat.items if item.feature and item.feature.type == "profile"]
    assert len(profile_items) == 1
    profile = profile_items[0]

    assert profile.geometry is not None
    assert "edge_treatment" in profile.geometry.data
    edge = profile.geometry.data["edge_treatment"]
    assert edge["type"] == "allowance"
    assert abs(edge["rough_allowance_mm"] - 0.5) < 0.01
    assert abs(edge["finish_allowance_mm"] - 0.1) < 0.01

    removal = simple_item_to_removal_intent(profile, region_id_prefix="test_profile")

    assert removal.constraints.edge_treatment is not None
    assert removal.constraints.edge_treatment.type == "allowance"
    assert removal.constraints.edge_treatment.rough_allowance_mm is not None
    assert removal.constraints.edge_treatment.finish_allowance_mm is not None
    assert abs(removal.constraints.edge_treatment.rough_allowance_mm - 0.5) < 0.01
    assert abs(removal.constraints.edge_treatment.finish_allowance_mm - 0.1) < 0.01


def test_profile_with_fillet_hint():
    pml = """
Sheet:
  width: 400mm
  height: 400mm
  thickness: 19mm

children:
  - Rect:
      id: panel
      children:
        - Profile:
            side: outside
            depth: through
        - Edge:
            treatment: fillet
            radius: 3mm
"""

    ast = parse_pml_yaml(pml)
    flat = resolve_layout(ast)

    profile_items = [item for item in flat.items if item.feature and item.feature.type == "profile"]
    assert len(profile_items) == 1
    profile = profile_items[0]

    removal = simple_item_to_removal_intent(profile)

    assert removal.constraints.edge_treatment is not None
    assert removal.constraints.edge_treatment.type == "fillet"
    assert removal.constraints.edge_treatment.radius_mm is not None
    assert abs(removal.constraints.edge_treatment.radius_mm - 3.0) < 0.01


def test_edge_chamfer():
    pml = """
Sheet:
  width: 400mm
  height: 400mm
  thickness: 19mm

children:
  - Rect:
      id: panel
      children:
        - Profile:
            side: outside
            depth: through
        - Edge:
            treatment: chamfer
            distance: 2.5mm
"""

    ast = parse_pml_yaml(pml)
    flat = resolve_layout(ast)

    profile_items = [item for item in flat.items if item.feature and item.feature.type == "profile"]
    assert len(profile_items) == 1
    profile = profile_items[0]

    removal = simple_item_to_removal_intent(profile)

    assert removal.constraints.edge_treatment is not None
    assert removal.constraints.edge_treatment.type == "chamfer"
    assert removal.constraints.edge_treatment.distance_mm is not None
    assert abs(removal.constraints.edge_treatment.distance_mm - 2.5) < 0.01


def test_edge_roundtrip():
    original_pml = """
Sheet:
  width: 400mm
  height: 400mm
  thickness: 19mm

children:
  - Rect:
      id: panel
      children:
        - Profile:
            side: outside
            depth: through
        - Edge:
            treatment: allowance
            rough_allowance: 0.5mm
            finish_allowance: 0.1mm
"""

    ast1 = parse_pml_yaml(original_pml)
    formatted_pml = format_pml_yaml(ast1)
    ast2 = parse_pml_yaml(formatted_pml)

    flat1 = resolve_layout(ast1)
    flat2 = resolve_layout(ast2)

    profile1 = next(item for item in flat1.items if item.feature and item.feature.type == "profile")
    profile2 = next(item for item in flat2.items if item.feature and item.feature.type == "profile")

    assert profile1.geometry is not None
    assert profile2.geometry is not None
    edge1 = profile1.geometry.data.get("edge_treatment")
    edge2 = profile2.geometry.data.get("edge_treatment")

    assert edge1 is not None and edge2 is not None
    assert edge1["type"] == edge2["type"] == "allowance"
    assert abs(edge1["rough_allowance_mm"] - edge2["rough_allowance_mm"]) < 0.01
    assert abs(edge1["finish_allowance_mm"] - edge2["finish_allowance_mm"]) < 0.01


def test_pocket_with_edge():
    pml = """
Sheet:
  width: 400mm
  height: 400mm
  thickness: 19mm

children:
  - Rect:
      id: panel
      children:
        - Pocket:
            depth: 6mm
        - Edge:
            treatment: allowance
            rough_allowance: 0.3mm
            finish_allowance: 0.05mm
"""

    ast = parse_pml_yaml(pml)
    flat = resolve_layout(ast)

    pocket_items = [item for item in flat.items if item.feature and item.feature.type == "pocket"]
    assert len(pocket_items) == 1
    pocket = pocket_items[0]

    assert pocket.geometry is not None
    assert "edge_treatment" in pocket.geometry.data
    edge = pocket.geometry.data["edge_treatment"]
    assert edge["type"] == "allowance"


def test_multi_tool_scenario():
    pml = """
Sheet:
  width: 400mm
  height: 400mm
  thickness: 19mm

children:
  - Rect:
      id: panel
      children:
        - Profile:
            side: outside
            depth: through
        - Edge:
            treatment: allowance
            rough_allowance: 0.5mm
            finish_allowance: 0.1mm
"""

    ast = parse_pml_yaml(pml)
    flat = resolve_layout(ast)

    profile_items = [item for item in flat.items if item.feature and item.feature.type == "profile"]
    base_removal = simple_item_to_removal_intent(profile_items[0])

    assert base_removal.constraints.edge_treatment is not None
    assert base_removal.constraints.edge_treatment.type == "allowance"

    assert base_removal.constraints.edge_treatment.rough_allowance_mm is not None
    assert base_removal.constraints.edge_treatment.finish_allowance_mm is not None
    rough_allowance = base_removal.constraints.edge_treatment.rough_allowance_mm
    finish_allowance = base_removal.constraints.edge_treatment.finish_allowance_mm

    assert abs(rough_allowance - 0.5) < 0.01
    assert abs(finish_allowance - 0.1) < 0.01

    rough_side_offset = rough_allowance
    assert rough_side_offset > 0

    finish_side_offset = finish_allowance
    assert finish_side_offset < rough_side_offset

    assert rough_allowance > finish_allowance


def test_kerf_compatibility():
    from ir.removal_intent import Allowance, Constraints, EdgeTreatment, RemovalIntent

    pml = """
Sheet:
  width: 400mm
  height: 400mm
  thickness: 19mm

children:
  - Rect:
      id: panel
      children:
        - Profile:
            side: outside
            depth: through
        - Edge:
            treatment: allowance
            rough_allowance: 0.5mm
            finish_allowance: 0.1mm
"""

    ast = parse_pml_yaml(pml)
    flat = resolve_layout(ast)

    profile_items = [item for item in flat.items if item.feature and item.feature.type == "profile"]
    base_removal = simple_item_to_removal_intent(profile_items[0])

    assert base_removal.constraints.edge_treatment is not None
    assert base_removal.constraints.edge_treatment.rough_allowance_mm is not None
    assert base_removal.constraints.edge_treatment.finish_allowance_mm is not None
    edge_rough = base_removal.constraints.edge_treatment.rough_allowance_mm
    edge_finish = base_removal.constraints.edge_treatment.finish_allowance_mm

    tool_kerf_mm = 3.175
    kerf_offset = tool_kerf_mm / 2.0

    combined_removal = RemovalIntent(
        region_id=base_removal.region_id,
        bounds=base_removal.bounds,
        depth_profile=DepthProfile.constant(
            z_top=base_removal.depth_profile.z_top, z_bottom=base_removal.depth_profile.z_bottom
        ),
        allowance=Allowance(outside=0.0, kerf_compensation=kerf_offset),
        constraints=Constraints(
            edge_treatment=EdgeTreatment(
                type="allowance", rough_allowance_mm=edge_rough, finish_allowance_mm=edge_finish
            )
        ),
    )

    assert combined_removal.allowance.kerf_compensation == kerf_offset
    assert combined_removal.constraints.edge_treatment is not None
    assert combined_removal.constraints.edge_treatment.rough_allowance_mm == edge_rough
    assert combined_removal.constraints.edge_treatment.finish_allowance_mm == edge_finish

    assert combined_removal.constraints.edge_treatment.rough_allowance_mm is not None
    assert combined_removal.constraints.edge_treatment.finish_allowance_mm is not None
    total_rough_offset = kerf_offset + combined_removal.constraints.edge_treatment.rough_allowance_mm
    total_finish_offset = kerf_offset + combined_removal.constraints.edge_treatment.finish_allowance_mm

    assert total_rough_offset > kerf_offset
    assert total_finish_offset > kerf_offset
    assert total_rough_offset > total_finish_offset
