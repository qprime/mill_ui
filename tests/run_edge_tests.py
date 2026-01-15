
import sys
import traceback


def test_edge_allowance():
    print("Running test_edge_allowance...")

    from pml.compositional_parser import parse_compositional_pml
    from resolution.layout_resolver import resolve_layout
    from adapters.hints_to_removal import item_to_removal_intent

    pml = """sheet 400.00mm 400.00mm 19.00mm

rect panel profile through outside
    edge allowance 0.50mm 0.10mm
"""

    ast = parse_compositional_pml(pml)
    flat = resolve_layout(ast)

    profile_items = [item for item in flat.items if item.feature and item.feature.type == "profile"]
    assert len(profile_items) == 1
    profile = profile_items[0]


    assert "edge_treatment" in profile.geometry.data
    edge = profile.geometry.data["edge_treatment"]
    assert edge["type"] == "allowance"
    assert abs(edge["rough_allowance_mm"] - 0.5) < 0.01
    assert abs(edge["finish_allowance_mm"] - 0.1) < 0.01


    removal = item_to_removal_intent(profile)
    assert removal.constraints.edge_treatment is not None
    assert removal.constraints.edge_treatment.type == "allowance"

    print("  ✓ PASS")
    return True


def test_fillet():
    print("Running test_fillet...")

    from pml.compositional_parser import parse_compositional_pml
    from resolution.layout_resolver import resolve_layout
    from adapters.hints_to_removal import item_to_removal_intent

    pml = """sheet 400.00mm 400.00mm 19.00mm

rect panel profile through outside
    edge fillet 3.00mm
"""

    ast = parse_compositional_pml(pml)
    flat = resolve_layout(ast)

    profile_items = [item for item in flat.items if item.feature and item.feature.type == "profile"]
    removal = item_to_removal_intent(profile_items[0])

    assert removal.constraints.edge_treatment is not None
    assert removal.constraints.edge_treatment.type == "fillet"
    assert abs(removal.constraints.edge_treatment.radius_mm - 3.0) < 0.01

    print("  ✓ PASS")
    return True


def test_roundtrip():
    print("Running test_roundtrip...")

    from pml.compositional_parser import parse_compositional_pml
    from pml.compositional_formatter import format_compositional_pml
    from resolution.layout_resolver import resolve_layout

    original_pml = """sheet 400.00mm 400.00mm 19.00mm

rect panel profile through outside
    edge allowance 0.50mm 0.10mm
"""

    ast1 = parse_compositional_pml(original_pml)
    formatted_pml = format_compositional_pml(ast1)
    ast2 = parse_compositional_pml(formatted_pml)

    flat1 = resolve_layout(ast1)
    flat2 = resolve_layout(ast2)

    profile1 = [item for item in flat1.items if item.feature and item.feature.type == "profile"][0]
    profile2 = [item for item in flat2.items if item.feature and item.feature.type == "profile"][0]

    edge1 = profile1.geometry.data.get("edge_treatment")
    edge2 = profile2.geometry.data.get("edge_treatment")

    assert edge1 is not None and edge2 is not None
    assert edge1["type"] == edge2["type"]

    print("  ✓ PASS")
    return True


def test_chamfer():
    print("Running test_chamfer...")

    from pml.compositional_parser import parse_compositional_pml
    from resolution.layout_resolver import resolve_layout
    from adapters.hints_to_removal import item_to_removal_intent

    pml = """sheet 400.00mm 400.00mm 19.00mm

rect panel profile through outside
    edge chamfer 2.50mm
"""

    ast = parse_compositional_pml(pml)
    flat = resolve_layout(ast)

    profile_items = [item for item in flat.items if item.feature and item.feature.type == "profile"]
    removal = item_to_removal_intent(profile_items[0])

    assert removal.constraints.edge_treatment is not None
    assert removal.constraints.edge_treatment.type == "chamfer"
    assert abs(removal.constraints.edge_treatment.distance_mm - 2.5) < 0.01

    print("  ✓ PASS")
    return True


def test_multi_tool_scenario():
    print("Running test_multi_tool_scenario...")

    from pml.compositional_parser import parse_compositional_pml
    from resolution.layout_resolver import resolve_layout
    from adapters.hints_to_removal import item_to_removal_intent

    pml = """sheet 400.00mm 400.00mm 19.00mm

rect panel profile through outside
    edge allowance 0.50mm 0.10mm
"""

    ast = parse_compositional_pml(pml)
    flat = resolve_layout(ast)

    profile_items = [item for item in flat.items if item.feature and item.feature.type == "profile"]
    base_removal = item_to_removal_intent(profile_items[0])


    assert base_removal.constraints.edge_treatment is not None
    assert base_removal.constraints.edge_treatment.type == "allowance"

    rough_allowance = base_removal.constraints.edge_treatment.rough_allowance_mm
    finish_allowance = base_removal.constraints.edge_treatment.finish_allowance_mm

    assert abs(rough_allowance - 0.5) < 0.01
    assert abs(finish_allowance - 0.1) < 0.01


    rough_side_offset = rough_allowance
    assert rough_side_offset > 0


    finish_side_offset = finish_allowance
    assert finish_side_offset < rough_side_offset


    assert rough_allowance > finish_allowance

    print("  ✓ PASS")
    return True


def test_kerf_compatibility():
    print("Running test_kerf_compatibility...")

    from pml.compositional_parser import parse_compositional_pml
    from resolution.layout_resolver import resolve_layout
    from adapters.hints_to_removal import item_to_removal_intent
    from ir.removal_intent import Allowance

    pml = """sheet 400.00mm 400.00mm 19.00mm

rect panel profile through outside
    edge allowance 0.50mm 0.10mm
"""

    ast = parse_compositional_pml(pml)
    flat = resolve_layout(ast)

    profile_items = [item for item in flat.items if item.feature and item.feature.type == "profile"]
    base_removal = item_to_removal_intent(profile_items[0])


    assert base_removal.constraints.edge_treatment is not None
    edge_rough = base_removal.constraints.edge_treatment.rough_allowance_mm
    edge_finish = base_removal.constraints.edge_treatment.finish_allowance_mm


    tool_kerf_mm = 3.175
    kerf_offset = tool_kerf_mm / 2.0


    from ir.removal_intent import RemovalIntent, Constraints, EdgeTreatment

    combined_removal = RemovalIntent(
        region_id=base_removal.region_id,
        bounds=base_removal.bounds,
        z_top=base_removal.z_top,
        z_bottom=base_removal.z_bottom,
        allowance=Allowance(outside=0.0, kerf_compensation=kerf_offset),
        constraints=Constraints(
            edge_treatment=EdgeTreatment(
                type="allowance",
                rough_allowance_mm=edge_rough,
                finish_allowance_mm=edge_finish
            )
        ),
        metadata=base_removal.metadata
    )


    assert combined_removal.allowance.kerf_compensation == kerf_offset
    assert combined_removal.constraints.edge_treatment.rough_allowance_mm == edge_rough
    assert combined_removal.constraints.edge_treatment.finish_allowance_mm == edge_finish


    total_rough_offset = kerf_offset + edge_rough
    total_finish_offset = kerf_offset + edge_finish

    assert total_rough_offset > kerf_offset
    assert total_finish_offset > kerf_offset
    assert total_rough_offset > total_finish_offset

    print("  ✓ PASS")
    return True


if __name__ == "__main__":
    tests = [
        test_edge_allowance,
        test_fillet,
        test_roundtrip,
        test_chamfer,
        test_multi_tool_scenario,
        test_kerf_compatibility,
    ]

    results = []
    for test in tests:
        try:
            results.append(test())
        except Exception as e:
            print(f"  ✗ FAIL: {e}")
            traceback.print_exc()
            results.append(False)

    passed = sum(1 for r in results if r)
    total = len(results)
    print(f"\n{passed}/{total} Edge Intent tests passed")

    sys.exit(0 if all(results) else 1)
