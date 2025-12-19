"""Tests for Split layout manager (Stage 15).

Acceptance tests:
- French-door pocket example: frame → split(2×2, rail/mullion) → cell pocket
- 4-pane panel with 50mm rails (horizontal) and 40mm mullions (vertical)
- Zero rail/mullion behaves like grid (no material reserved)
- Split inside inset region calculates pane sizes correctly
- Round-trip: PML → AST → PML preserves rail/mullion dimensions
"""

from pml.compositional_parser import parse_compositional_pml
from pml.compositional_formatter import format_compositional_pml
from resolution.layout_resolver import resolve_layout


def test_basic_split_2x2():
    """Test basic 2×2 split with rail/mullion bars."""
    pml = """sheet 600.00mm 600.00mm 19.00mm

rect outer profile through outside
    frame 50.00mm
        split 2 2 rail 50.00mm mullion 40.00mm
            cell
                rect pane pocket 6.00mm
"""

    ast = parse_compositional_pml(pml)
    assert ast.sheet.width_mm == 600
    assert ast.sheet.height_mm == 600

    # Resolve to flat AST
    flat = resolve_layout(ast)

    # Should have:
    # - 2 profiles (outer rect + frame)
    # - 4 pockets (one per pane in split)
    profile_items = [item for item in flat.items if item.feature and item.feature.type == "profile"]
    pocket_items = [item for item in flat.items if item.feature and item.feature.type == "pocket"]

    assert len(profile_items) == 2, f"Expected 2 profiles, got {len(profile_items)}"
    assert len(pocket_items) == 4, f"Expected 4 pockets (2×2 panes), got {len(pocket_items)}"

    # Calculate expected pane sizes
    # Frame inner region: 600 - 2*50 = 500mm × 500mm
    # Split with 2 rows, 2 cols, rail=50mm, mullion=40mm
    # Pane width: (500 - 1*40) / 2 = 460 / 2 = 230mm
    # Pane height: (500 - 1*50) / 2 = 450 / 2 = 225mm

    first_pocket = pocket_items[0]
    assert abs(first_pocket.geometry.data["w_mm"] - 230.0) < 0.01
    assert abs(first_pocket.geometry.data["h_mm"] - 225.0) < 0.01


def test_split_zero_rails_behaves_like_grid():
    """Test that split with zero rail/mullion behaves like grid."""
    pml_split = """sheet 400.00mm 400.00mm 19.00mm

split 2 2 rail 0.00mm mullion 0.00mm
    cell
        rect pocket 5.00mm
"""

    pml_grid = """sheet 400.00mm 400.00mm 19.00mm

grid 2 2 gap 0.00mm
    cell
        rect pocket 5.00mm
"""

    # Parse and resolve both
    split_ast = parse_compositional_pml(pml_split)
    grid_ast = parse_compositional_pml(pml_grid)

    split_flat = resolve_layout(split_ast)
    grid_flat = resolve_layout(grid_ast)

    # Both should produce same number of items
    assert len(split_flat.items) == len(grid_flat.items)

    # Compare pocket sizes (should be identical)
    split_pockets = [item for item in split_flat.items if item.feature and item.feature.type == "pocket"]
    grid_pockets = [item for item in grid_flat.items if item.feature and item.feature.type == "pocket"]

    assert len(split_pockets) == len(grid_pockets) == 4

    for sp, gp in zip(split_pockets, grid_pockets):
        assert abs(sp.geometry.data["w_mm"] - gp.geometry.data["w_mm"]) < 0.01
        assert abs(sp.geometry.data["h_mm"] - gp.geometry.data["h_mm"]) < 0.01


def test_split_pane_size_calculation():
    """Test correct pane size calculation with various rail/mullion values."""
    pml = """sheet 1000.00mm 800.00mm 19.00mm

split 3 4 rail 30.00mm mullion 20.00mm
    cell
        rect pane pocket 5.00mm
"""

    ast = parse_compositional_pml(pml)
    flat = resolve_layout(ast)

    # Expected pane sizes:
    # Region: 1000mm × 800mm
    # 3 rows, 4 cols, rail=30mm, mullion=20mm
    # Pane width: (1000 - (4-1)*20) / 4 = (1000 - 60) / 4 = 940 / 4 = 235mm
    # Pane height: (800 - (3-1)*30) / 3 = (800 - 60) / 3 = 740 / 3 ≈ 246.67mm

    pockets = [item for item in flat.items if item.feature and item.feature.type == "pocket"]
    assert len(pockets) == 12, f"Expected 12 pockets (3×4 panes), got {len(pockets)}"

    # Check first pane size
    first_pocket = pockets[0]
    assert abs(first_pocket.geometry.data["w_mm"] - 235.0) < 0.01
    assert abs(first_pocket.geometry.data["h_mm"] - 246.67) < 0.01


def test_split_inside_inset():
    """Test split inside inset region calculates correctly."""
    pml = """sheet 500.00mm 500.00mm 19.00mm

inset 50.00mm
    split 2 2 rail 40.00mm mullion 30.00mm
        cell
            rect pane pocket 5.00mm
"""

    ast = parse_compositional_pml(pml)
    flat = resolve_layout(ast)

    # Expected pane sizes:
    # Inset region: 500 - 2*50 = 400mm × 400mm
    # Split: 2 rows, 2 cols, rail=40mm, mullion=30mm
    # Pane width: (400 - (2-1)*30) / 2 = (400 - 30) / 2 = 370 / 2 = 185mm
    # Pane height: (400 - (2-1)*40) / 2 = (400 - 40) / 2 = 360 / 2 = 180mm

    pockets = [item for item in flat.items if item.feature and item.feature.type == "pocket"]
    assert len(pockets) == 4

    first_pocket = pockets[0]
    assert abs(first_pocket.geometry.data["w_mm"] - 185.0) < 0.01
    assert abs(first_pocket.geometry.data["h_mm"] - 180.0) < 0.01


def test_split_roundtrip_preserves_rail_mullion():
    """Test PML → AST → PML preserves rail/mullion values."""
    original_pml = """sheet 600.00mm 400.00mm 19.00mm

split 2 3 rail 45.00mm mullion 35.00mm
    cell
        rect pocket 6.00mm
"""

    # Parse → Format → Parse
    ast1 = parse_compositional_pml(original_pml)
    formatted_pml = format_compositional_pml(ast1)
    ast2 = parse_compositional_pml(formatted_pml)

    # Resolve both and compare
    flat1 = resolve_layout(ast1)
    flat2 = resolve_layout(ast2)

    assert len(flat1.items) == len(flat2.items)

    # Compare pocket geometries
    pockets1 = [item for item in flat1.items if item.feature and item.feature.type == "pocket"]
    pockets2 = [item for item in flat2.items if item.feature and item.feature.type == "pocket"]

    assert len(pockets1) == len(pockets2) == 6  # 2×3 panes

    for p1, p2 in zip(pockets1, pockets2):
        assert abs(p1.geometry.data["w_mm"] - p2.geometry.data["w_mm"]) < 0.01
        assert abs(p1.geometry.data["h_mm"] - p2.geometry.data["h_mm"]) < 0.01


def test_french_door_acceptance():
    """Stage 15 acceptance test: French-door pocket example with split."""
    pml = """sheet 800.00mm 1200.00mm 19.00mm

rect door_outer profile through outside
    frame 60.00mm
        split 2 2 rail 50.00mm mullion 40.00mm
            cell
                rect glass_pane pocket 8.00mm
"""

    ast = parse_compositional_pml(pml)
    flat = resolve_layout(ast)

    # Should have:
    # - 2 profiles (outer + frame)
    # - 4 pockets (2×2 glass panes)
    profile_items = [item for item in flat.items if item.feature and item.feature.type == "profile"]
    pocket_items = [item for item in flat.items if item.feature and item.feature.type == "pocket"]

    assert len(profile_items) == 2
    assert len(pocket_items) == 4

    # Verify pane geometry
    # Frame inner: 800 - 2*60 = 680mm × 1200 - 2*60 = 1080mm
    # Pane width: (680 - 1*40) / 2 = 640 / 2 = 320mm
    # Pane height: (1080 - 1*50) / 2 = 1030 / 2 = 515mm

    first_pane = pocket_items[0]
    assert abs(first_pane.geometry.data["w_mm"] - 320.0) < 0.01
    assert abs(first_pane.geometry.data["h_mm"] - 515.0) < 0.01


def test_split_single_row():
    """Test split with single row (only mullions, no rails)."""
    pml = """sheet 600.00mm 200.00mm 19.00mm

split 1 3 rail 0.00mm mullion 30.00mm
    cell
        rect pane pocket 5.00mm
"""

    ast = parse_compositional_pml(pml)
    flat = resolve_layout(ast)

    # 1 row, 3 cols, mullion=30mm
    # Pane width: (600 - 2*30) / 3 = 540 / 3 = 180mm
    # Pane height: 200mm (full height, no rails)

    pockets = [item for item in flat.items if item.feature and item.feature.type == "pocket"]
    assert len(pockets) == 3

    first_pocket = pockets[0]
    assert abs(first_pocket.geometry.data["w_mm"] - 180.0) < 0.01
    assert abs(first_pocket.geometry.data["h_mm"] - 200.0) < 0.01


def test_split_single_column():
    """Test split with single column (only rails, no mullions)."""
    pml = """sheet 200.00mm 600.00mm 19.00mm

split 3 1 rail 40.00mm mullion 0.00mm
    cell
        rect pane pocket 5.00mm
"""

    ast = parse_compositional_pml(pml)
    flat = resolve_layout(ast)

    # 3 rows, 1 col, rail=40mm
    # Pane width: 200mm (full width, no mullions)
    # Pane height: (600 - 2*40) / 3 = 520 / 3 ≈ 173.33mm

    pockets = [item for item in flat.items if item.feature and item.feature.type == "pocket"]
    assert len(pockets) == 3

    first_pocket = pockets[0]
    assert abs(first_pocket.geometry.data["w_mm"] - 200.0) < 0.01
    assert abs(first_pocket.geometry.data["h_mm"] - 173.33) < 0.01
