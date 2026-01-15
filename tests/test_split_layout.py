
from pml.compositional_parser import parse_compositional_pml
from pml.compositional_formatter import format_compositional_pml
from resolution.layout_resolver import resolve_layout


def test_basic_split_2x2():
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


    flat = resolve_layout(ast)


    profile_items = [item for item in flat.items if item.feature and item.feature.type == "profile"]
    pocket_items = [item for item in flat.items if item.feature and item.feature.type == "pocket"]

    assert len(profile_items) == 2, f"Expected 2 profiles, got {len(profile_items)}"
    assert len(pocket_items) == 4, f"Expected 4 pockets (2×2 panes), got {len(pocket_items)}"


    first_pocket = pocket_items[0]
    assert abs(first_pocket.geometry.data["w_mm"] - 230.0) < 0.01
    assert abs(first_pocket.geometry.data["h_mm"] - 225.0) < 0.01


def test_split_zero_rails_behaves_like_grid():
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


    split_ast = parse_compositional_pml(pml_split)
    grid_ast = parse_compositional_pml(pml_grid)

    split_flat = resolve_layout(split_ast)
    grid_flat = resolve_layout(grid_ast)


    assert len(split_flat.items) == len(grid_flat.items)


    split_pockets = [item for item in split_flat.items if item.feature and item.feature.type == "pocket"]
    grid_pockets = [item for item in grid_flat.items if item.feature and item.feature.type == "pocket"]

    assert len(split_pockets) == len(grid_pockets) == 4

    for sp, gp in zip(split_pockets, grid_pockets):
        assert abs(sp.geometry.data["w_mm"] - gp.geometry.data["w_mm"]) < 0.01
        assert abs(sp.geometry.data["h_mm"] - gp.geometry.data["h_mm"]) < 0.01


def test_split_pane_size_calculation():
    pml = """sheet 1000.00mm 800.00mm 19.00mm

split 3 4 rail 30.00mm mullion 20.00mm
    cell
        rect pane pocket 5.00mm
"""

    ast = parse_compositional_pml(pml)
    flat = resolve_layout(ast)


    pockets = [item for item in flat.items if item.feature and item.feature.type == "pocket"]
    assert len(pockets) == 12, f"Expected 12 pockets (3×4 panes), got {len(pockets)}"


    first_pocket = pockets[0]
    assert abs(first_pocket.geometry.data["w_mm"] - 235.0) < 0.01
    assert abs(first_pocket.geometry.data["h_mm"] - 246.67) < 0.01


def test_split_inside_inset():
    pml = """sheet 500.00mm 500.00mm 19.00mm

inset 50.00mm
    split 2 2 rail 40.00mm mullion 30.00mm
        cell
            rect pane pocket 5.00mm
"""

    ast = parse_compositional_pml(pml)
    flat = resolve_layout(ast)


    pockets = [item for item in flat.items if item.feature and item.feature.type == "pocket"]
    assert len(pockets) == 4

    first_pocket = pockets[0]
    assert abs(first_pocket.geometry.data["w_mm"] - 185.0) < 0.01
    assert abs(first_pocket.geometry.data["h_mm"] - 180.0) < 0.01


def test_split_roundtrip_preserves_rail_mullion():
    original_pml = """sheet 600.00mm 400.00mm 19.00mm

split 2 3 rail 45.00mm mullion 35.00mm
    cell
        rect pocket 6.00mm
"""


    ast1 = parse_compositional_pml(original_pml)
    formatted_pml = format_compositional_pml(ast1)
    ast2 = parse_compositional_pml(formatted_pml)


    flat1 = resolve_layout(ast1)
    flat2 = resolve_layout(ast2)

    assert len(flat1.items) == len(flat2.items)


    pockets1 = [item for item in flat1.items if item.feature and item.feature.type == "pocket"]
    pockets2 = [item for item in flat2.items if item.feature and item.feature.type == "pocket"]

    assert len(pockets1) == len(pockets2) == 6

    for p1, p2 in zip(pockets1, pockets2):
        assert abs(p1.geometry.data["w_mm"] - p2.geometry.data["w_mm"]) < 0.01
        assert abs(p1.geometry.data["h_mm"] - p2.geometry.data["h_mm"]) < 0.01


def test_french_door_acceptance():
    pml = """sheet 800.00mm 1200.00mm 19.00mm

rect door_outer profile through outside
    frame 60.00mm
        split 2 2 rail 50.00mm mullion 40.00mm
            cell
                rect glass_pane pocket 8.00mm
"""

    ast = parse_compositional_pml(pml)
    flat = resolve_layout(ast)


    profile_items = [item for item in flat.items if item.feature and item.feature.type == "profile"]
    pocket_items = [item for item in flat.items if item.feature and item.feature.type == "pocket"]

    assert len(profile_items) == 2
    assert len(pocket_items) == 4


    first_pane = pocket_items[0]
    assert abs(first_pane.geometry.data["w_mm"] - 320.0) < 0.01
    assert abs(first_pane.geometry.data["h_mm"] - 515.0) < 0.01


def test_split_single_row():
    pml = """sheet 600.00mm 200.00mm 19.00mm

split 1 3 rail 0.00mm mullion 30.00mm
    cell
        rect pane pocket 5.00mm
"""

    ast = parse_compositional_pml(pml)
    flat = resolve_layout(ast)


    pockets = [item for item in flat.items if item.feature and item.feature.type == "pocket"]
    assert len(pockets) == 3

    first_pocket = pockets[0]
    assert abs(first_pocket.geometry.data["w_mm"] - 180.0) < 0.01
    assert abs(first_pocket.geometry.data["h_mm"] - 200.0) < 0.01


def test_split_single_column():
    pml = """sheet 200.00mm 600.00mm 19.00mm

split 3 1 rail 40.00mm mullion 0.00mm
    cell
        rect pane pocket 5.00mm
"""

    ast = parse_compositional_pml(pml)
    flat = resolve_layout(ast)


    pockets = [item for item in flat.items if item.feature and item.feature.type == "pocket"]
    assert len(pockets) == 3

    first_pocket = pockets[0]
    assert abs(first_pocket.geometry.data["w_mm"] - 200.0) < 0.01
    assert abs(first_pocket.geometry.data["h_mm"] - 173.33) < 0.01
