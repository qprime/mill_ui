"""Tests for Keepout/Island semantics (Stage 17).

Acceptance tests:
- Frame field pocket with preserved panel island (faux raised panel base case)
- Keepout inside grid cell (each cell can have keepout)
- Multiple keepouts in single region
- RemovalIntent includes island geometry
- Round-trip: keepout boundaries preserved
"""

from skills.mill_ui.pml.compositional_parser import parse_compositional_pml, ParseError
from skills.mill_ui.pml.compositional_formatter import format_compositional_pml
from skills.mill_ui.resolution.layout_resolver import resolve_layout
from skills.mill_ui.layout_ast.compositional import Keepout
from skills.mill_ui.layout_ast.layout import Feature


def test_simple_pocket_with_island():
    """Test basic pocket with keepout island (faux raised panel)."""
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
    assert len(items) == 1  # Only the panel

    # The item should be the panel with pocket feature
    panel = items[0]
    assert panel.feature.type == "pocket"

    # Panel should have island information in geometry
    assert "islands" in panel.geometry.data
    islands = panel.geometry.data["islands"]
    assert len(islands) == 1

    # Island should be inset by 50mm from 400×400mm panel
    # So island bounds: 50 to 350 in both X and Y
    island = islands[0]
    assert abs(island["x_min"] - 50.0) < 0.01
    assert abs(island["x_max"] - 350.0) < 0.01
    assert abs(island["y_min"] - 50.0) < 0.01
    assert abs(island["y_max"] - 350.0) < 0.01


def test_keepout_inside_grid():
    """Test keepout inside grid cell."""
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
    assert len(pocket_items) == 4

    # Each pocket should have an island
    for pocket in pocket_items:
        assert "islands" in pocket.geometry.data
        assert len(pocket.geometry.data["islands"]) == 1


def test_multiple_keepouts_in_region():
    """Test multiple keepouts in single region."""
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
    assert len(islands) == 2


def test_keepout_roundtrip():
    """Test PML → AST → PML preserves keepout structure."""
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


def test_keepout_with_circle():
    """Test keepout with circular island."""
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


def test_keepout_with_rounded_rect():
    """Test keepout with rounded rectangle island."""
    pml = """sheet 500.00mm 400.00mm 19.00mm

rect panel pocket 6.00mm
    keepout
        inset 50.00mm
            rounded_rect radius 10.00mm
"""

    ast = parse_compositional_pml(pml)
    flat = resolve_layout(ast)

    pocket_items = [item for item in flat.items if item.feature and item.feature.type == "pocket"]
    assert len(pocket_items) == 1

    pocket = pocket_items[0]
    assert "islands" in pocket.geometry.data
    islands = pocket.geometry.data["islands"]
    assert len(islands) == 1

    # Rounded rect inset by 50mm from 500×400mm sheet
    # Island bounds: (50, 450) × (50, 350)
    island = islands[0]
    assert abs(island["x_min"] - 50.0) < 0.01
    assert abs(island["x_max"] - 450.0) < 0.01
    assert abs(island["y_min"] - 50.0) < 0.01
    assert abs(island["y_max"] - 350.0) < 0.01


def test_nested_keepout_error():
    """Test that nested keepouts are rejected with clear error."""
    pml = """sheet 400.00mm 400.00mm 19.00mm

rect panel pocket 6.00mm
    keepout
        inset 50.00mm
            rect outer_island
                keepout
                    rect nested_island
"""

    try:
        ast = parse_compositional_pml(pml)
        assert False, "Should have raised ParseError for nested keepout"
    except ParseError as e:
        assert "nested keepout" in str(e).lower()


def test_removal_intent_includes_islands():
    """Test RemovalIntent includes island geometry from keepouts."""
    from skills.mill_ui.adapters.hints_to_removal import item_to_removal_intent

    pml = """sheet 400.00mm 400.00mm 19.00mm

rect panel pocket 6.00mm
    keepout
        inset 50.00mm
            rect island
"""

    ast = parse_compositional_pml(pml)
    flat = resolve_layout(ast)

    # Get the pocket item
    pocket_items = [item for item in flat.items if item.feature and item.feature.type == "pocket"]
    assert len(pocket_items) == 1
    pocket = pocket_items[0]

    # Convert to RemovalIntent
    removal = item_to_removal_intent(pocket, region_id_prefix="test_pocket")

    # Verify RemovalIntent has islands
    assert len(removal.constraints.islands) == 1

    # Verify island bounds match expected values (inset by 50mm from 400×400mm)
    island = removal.constraints.islands[0]
    assert abs(island.bounds.x_min - 50.0) < 0.01
    assert abs(island.bounds.x_max - 350.0) < 0.01
    assert abs(island.bounds.y_min - 50.0) < 0.01
    assert abs(island.bounds.y_max - 350.0) < 0.01
