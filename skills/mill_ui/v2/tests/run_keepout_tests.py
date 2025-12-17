"""Standalone test runner for Keepout/Island tests (without pytest)."""

import sys
import traceback


def test_simple_pocket_with_island():
    """Test basic pocket with keepout island (faux raised panel)."""
    print("Running test_simple_pocket_with_island...")

    from skills.mill_ui.v2.pml.compositional_parser import parse_compositional_pml
    from skills.mill_ui.v2.resolution.layout_resolver import resolve_layout

    pml = """sheet 400.00mm 400.00mm 19.00mm

rect panel pocket 6.00mm
    keepout
        inset 50.00mm
            rect island
"""

    ast = parse_compositional_pml(pml)
    flat = resolve_layout(ast)

    # Should have one rect with pocket feature
    # (keepout children are not emitted as separate items - they define island bounds)
    items = flat.items
    assert len(items) == 1, f"Expected 1 item (panel), got {len(items)}"

    # The item should be the panel with pocket feature
    panel = items[0]
    assert panel.feature.type == "pocket"

    # Panel should have island information in geometry
    assert "islands" in panel.geometry.data, "Expected islands in geometry data"
    islands = panel.geometry.data["islands"]
    assert len(islands) == 1, f"Expected 1 island, got {len(islands)}"

    # Island should be inset by 50mm from 400×400mm panel
    # So island bounds: 50 to 350 in both X and Y
    island = islands[0]
    assert abs(island["x_min"] - 50.0) < 0.01
    assert abs(island["x_max"] - 350.0) < 0.01
    assert abs(island["y_min"] - 50.0) < 0.01
    assert abs(island["y_max"] - 350.0) < 0.01

    print("  ✓ PASS")
    return True


def test_keepout_inside_grid():
    """Test keepout inside grid cell."""
    print("Running test_keepout_inside_grid...")

    from skills.mill_ui.v2.pml.compositional_parser import parse_compositional_pml
    from skills.mill_ui.v2.resolution.layout_resolver import resolve_layout

    pml = """sheet 600.00mm 400.00mm 19.00mm

grid 2 2 gap 10.00mm
    cell
        rect pocket 5.00mm
            keepout
                inset 20.00mm
                    rect
"""

    ast = parse_compositional_pml(pml)
    flat = resolve_layout(ast)

    # Should have 4 pocket rects (2×2 grid)
    pocket_items = [item for item in flat.items if item.feature and item.feature.type == "pocket"]
    assert len(pocket_items) == 4, f"Expected 4 pocket items, got {len(pocket_items)}"

    # Each pocket should have an island
    for pocket in pocket_items:
        assert "islands" in pocket.geometry.data
        assert len(pocket.geometry.data["islands"]) == 1

    print("  ✓ PASS")
    return True


def test_multiple_keepouts():
    """Test multiple keepouts in single region."""
    print("Running test_multiple_keepouts...")

    from skills.mill_ui.v2.pml.compositional_parser import parse_compositional_pml
    from skills.mill_ui.v2.resolution.layout_resolver import resolve_layout

    pml = """sheet 500.00mm 500.00mm 19.00mm

rect panel pocket 6.00mm
    keepout
        inset 50.00mm
            inset 50.00mm
                rect island1
    keepout
        inset 200.00mm
            circle fit
"""

    ast = parse_compositional_pml(pml)
    flat = resolve_layout(ast)

    # Find the panel
    panel_items = [item for item in flat.items if item.feature and item.feature.type == "pocket"]
    assert len(panel_items) == 1

    panel = panel_items[0]

    # Panel should have 2 islands
    assert "islands" in panel.geometry.data
    islands = panel.geometry.data["islands"]
    assert len(islands) == 2, f"Expected 2 islands, got {len(islands)}"

    print("  ✓ PASS")
    return True


def test_keepout_roundtrip():
    """Test PML → AST → PML preserves keepout structure."""
    print("Running test_keepout_roundtrip...")

    from skills.mill_ui.v2.pml.compositional_parser import parse_compositional_pml
    from skills.mill_ui.v2.pml.compositional_formatter import format_compositional_pml
    from skills.mill_ui.v2.resolution.layout_resolver import resolve_layout

    original_pml = """sheet 400.00mm 400.00mm 19.00mm

rect panel pocket 6.00mm
    keepout
        inset 50.00mm
            rect island
"""

    # Parse → Format → Parse
    ast1 = parse_compositional_pml(original_pml)
    formatted_pml = format_compositional_pml(ast1)
    ast2 = parse_compositional_pml(formatted_pml)

    # Resolve both and compare
    flat1 = resolve_layout(ast1)
    flat2 = resolve_layout(ast2)

    # Both should have same island configuration
    pocket1 = [item for item in flat1.items if item.feature and item.feature.type == "pocket"][0]
    pocket2 = [item for item in flat2.items if item.feature and item.feature.type == "pocket"][0]

    islands1 = pocket1.geometry.data.get("islands", [])
    islands2 = pocket2.geometry.data.get("islands", [])

    assert len(islands1) == len(islands2) == 1

    # Compare island bounds
    for island1, island2 in zip(islands1, islands2):
        assert abs(island1["x_min"] - island2["x_min"]) < 0.01
        assert abs(island1["x_max"] - island2["x_max"]) < 0.01
        assert abs(island1["y_min"] - island2["y_min"]) < 0.01
        assert abs(island1["y_max"] - island2["y_max"]) < 0.01

    print("  ✓ PASS")
    return True


def test_keepout_with_circle():
    """Test keepout with circular island."""
    print("Running test_keepout_with_circle...")

    from skills.mill_ui.v2.pml.compositional_parser import parse_compositional_pml
    from skills.mill_ui.v2.resolution.layout_resolver import resolve_layout

    pml = """sheet 400.00mm 400.00mm 19.00mm

rect panel pocket 6.00mm
    keepout
        circle diameter 100.00mm
"""

    ast = parse_compositional_pml(pml)
    flat = resolve_layout(ast)

    pocket_items = [item for item in flat.items if item.feature and item.feature.type == "pocket"]
    assert len(pocket_items) == 1

    pocket = pocket_items[0]
    assert "islands" in pocket.geometry.data
    islands = pocket.geometry.data["islands"]
    assert len(islands) == 1

    # Circle with diameter 100mm centered at (200,200)
    # Bounding box: (150, 250) in both dimensions
    island = islands[0]
    assert abs(island["x_min"] - 150.0) < 0.01
    assert abs(island["x_max"] - 250.0) < 0.01
    assert abs(island["y_min"] - 150.0) < 0.01
    assert abs(island["y_max"] - 250.0) < 0.01

    print("  ✓ PASS")
    return True


if __name__ == "__main__":
    tests = [
        test_simple_pocket_with_island,
        test_keepout_inside_grid,
        test_multiple_keepouts,
        test_keepout_roundtrip,
        test_keepout_with_circle,
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
    print(f"\n{passed}/{total} Keepout/Island tests passed")

    sys.exit(0 if all(results) else 1)
