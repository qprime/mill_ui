"""Standalone test runner for Edge Intent tests (without pytest)."""

import sys
import traceback


def test_edge_allowance():
    """Test edge allowance influences RemovalIntent."""
    print("Running test_edge_allowance...")

    from skills.mill_ui.v2.pml.compositional_parser import parse_compositional_pml
    from skills.mill_ui.v2.resolution.layout_resolver import resolve_layout
    from skills.mill_ui.v2.adapters.hints_to_removal import item_to_removal_intent

    pml = """sheet 400.00mm 400.00mm 19.00mm

rect panel profile through outside
    edge allowance 0.50mm 0.10mm
"""

    ast = parse_compositional_pml(pml)
    flat = resolve_layout(ast)

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
    removal = item_to_removal_intent(profile)
    assert removal.constraints.edge_treatment is not None
    assert removal.constraints.edge_treatment.type == "allowance"

    print("  ✓ PASS")
    return True


def test_fillet():
    """Test fillet edge treatment."""
    print("Running test_fillet...")

    from skills.mill_ui.v2.pml.compositional_parser import parse_compositional_pml
    from skills.mill_ui.v2.resolution.layout_resolver import resolve_layout
    from skills.mill_ui.v2.adapters.hints_to_removal import item_to_removal_intent

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
    """Test PML round-trip preserves edge."""
    print("Running test_roundtrip...")

    from skills.mill_ui.v2.pml.compositional_parser import parse_compositional_pml
    from skills.mill_ui.v2.pml.compositional_formatter import format_compositional_pml
    from skills.mill_ui.v2.resolution.layout_resolver import resolve_layout

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


if __name__ == "__main__":
    tests = [
        test_edge_allowance,
        test_fillet,
        test_roundtrip,
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
