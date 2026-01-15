
from pml.compositional_parser import parse_compositional_pml, ParseError
from pml.compositional_formatter import format_compositional_pml
from resolution.layout_resolver import resolve_layout
from layout_ast.compositional import Keepout
from layout_ast.layout import Feature


def test_simple_pocket_with_island():
    pml = """sheet 400.00mm 400.00mm 19.00mm

rect panel pocket 6.00mm
    keepout
        inset 50.00mm
            rect island
"""

    ast = parse_compositional_pml(pml)
    flat = resolve_layout(ast)


    items = flat.items
    assert len(items) == 1


    panel = items[0]
    assert panel.feature.type == "pocket"


    assert "islands" in panel.geometry.data
    islands = panel.geometry.data["islands"]
    assert len(islands) == 1


    island = islands[0]
    assert abs(island["x_min"] - 50.0) < 0.01
    assert abs(island["x_max"] - 350.0) < 0.01
    assert abs(island["y_min"] - 50.0) < 0.01
    assert abs(island["y_max"] - 350.0) < 0.01


def test_keepout_inside_grid():
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


    pocket_items = [item for item in flat.items if item.feature and item.feature.type == "pocket"]
    assert len(pocket_items) == 4


    for pocket in pocket_items:
        assert "islands" in pocket.geometry.data
        assert len(pocket.geometry.data["islands"]) == 1


def test_multiple_keepouts_in_region():
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


    panel_items = [item for item in flat.items if item.feature and item.feature.type == "pocket"]
    assert len(panel_items) == 1

    panel = panel_items[0]


    assert "islands" in panel.geometry.data
    islands = panel.geometry.data["islands"]
    assert len(islands) == 2


def test_keepout_roundtrip():
    original_pml = """sheet 400.00mm 400.00mm 19.00mm

rect panel pocket 6.00mm
    keepout
        inset 50.00mm
            rect island
"""


    ast1 = parse_compositional_pml(original_pml)
    formatted_pml = format_compositional_pml(ast1)
    ast2 = parse_compositional_pml(formatted_pml)


    flat1 = resolve_layout(ast1)
    flat2 = resolve_layout(ast2)


    pocket1 = [item for item in flat1.items if item.feature and item.feature.type == "pocket"][0]
    pocket2 = [item for item in flat2.items if item.feature and item.feature.type == "pocket"][0]

    islands1 = pocket1.geometry.data.get("islands", [])
    islands2 = pocket2.geometry.data.get("islands", [])

    assert len(islands1) == len(islands2) == 1


    for island1, island2 in zip(islands1, islands2):
        assert abs(island1["x_min"] - island2["x_min"]) < 0.01
        assert abs(island1["x_max"] - island2["x_max"]) < 0.01
        assert abs(island1["y_min"] - island2["y_min"]) < 0.01
        assert abs(island1["y_max"] - island2["y_max"]) < 0.01


def test_keepout_with_circle():
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


    island = islands[0]
    assert abs(island["x_min"] - 150.0) < 0.01
    assert abs(island["x_max"] - 250.0) < 0.01
    assert abs(island["y_min"] - 150.0) < 0.01
    assert abs(island["y_max"] - 250.0) < 0.01


def test_keepout_with_rounded_rect():
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


    island = islands[0]
    assert abs(island["x_min"] - 50.0) < 0.01
    assert abs(island["x_max"] - 450.0) < 0.01
    assert abs(island["y_min"] - 50.0) < 0.01
    assert abs(island["y_max"] - 350.0) < 0.01


def test_nested_keepout_error():
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
    from adapters.hints_to_removal import item_to_removal_intent

    pml = """sheet 400.00mm 400.00mm 19.00mm

rect panel pocket 6.00mm
    keepout
        inset 50.00mm
            rect island
"""

    ast = parse_compositional_pml(pml)
    flat = resolve_layout(ast)


    pocket_items = [item for item in flat.items if item.feature and item.feature.type == "pocket"]
    assert len(pocket_items) == 1
    pocket = pocket_items[0]


    removal = item_to_removal_intent(pocket, region_id_prefix="test_pocket")


    assert len(removal.constraints.islands) == 1


    island = removal.constraints.islands[0]
    assert abs(island.bounds.x_min - 50.0) < 0.01
    assert abs(island.bounds.x_max - 350.0) < 0.01
    assert abs(island.bounds.y_min - 50.0) < 0.01
    assert abs(island.bounds.y_max - 350.0) < 0.01
