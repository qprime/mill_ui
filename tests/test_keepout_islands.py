
from pml.yaml_parser import parse_pml_yaml, PMLParseError
from pml.yaml_formatter import format_pml_yaml
from resolution.layout_resolver import resolve_layout
from layout_ast.compositional import Keepout
from layout_ast.layout import Feature


def test_simple_pocket_with_island():
    pml = """
Sheet:
  width: 400mm
  height: 400mm
  thickness: 19mm

children:
  - Rect:
      id: panel
      feature:
        type: pocket
        depth: 6mm
      children:
        - Keepout:
            children:
              - Inset:
                  distance: 50mm
                  children:
                    - Rect:
                        id: island
"""

    ast = parse_pml_yaml(pml)
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
    pml = """
Sheet:
  width: 600mm
  height: 400mm
  thickness: 19mm

children:
  - Grid:
      rows: 2
      cols: 2
      gap: 10mm
      children:
        - Cell:
            children:
              - Rect:
                  feature:
                    type: pocket
                    depth: 5mm
                  children:
                    - Keepout:
                        children:
                          - Inset:
                              distance: 20mm
                              children:
                                - Rect: {}
"""

    ast = parse_pml_yaml(pml)
    flat = resolve_layout(ast)


    pocket_items = [item for item in flat.items if item.feature and item.feature.type == "pocket"]
    assert len(pocket_items) == 4


    for pocket in pocket_items:
        assert "islands" in pocket.geometry.data
        assert len(pocket.geometry.data["islands"]) == 1


def test_multiple_keepouts_in_region():
    pml = """
Sheet:
  width: 500mm
  height: 500mm
  thickness: 19mm

children:
  - Rect:
      id: panel
      feature:
        type: pocket
        depth: 6mm
      children:
        - Keepout:
            children:
              - Inset:
                  distance: 50mm
                  children:
                    - Inset:
                        distance: 50mm
                        children:
                          - Rect:
                              id: island1
        - Keepout:
            children:
              - Inset:
                  distance: 200mm
                  children:
                    - Circle:
                        fit: true
"""

    ast = parse_pml_yaml(pml)
    flat = resolve_layout(ast)


    panel_items = [item for item in flat.items if item.feature and item.feature.type == "pocket"]
    assert len(panel_items) == 1

    panel = panel_items[0]


    assert "islands" in panel.geometry.data
    islands = panel.geometry.data["islands"]
    assert len(islands) == 2


def test_keepout_roundtrip():
    original_pml = """
Sheet:
  width: 400mm
  height: 400mm
  thickness: 19mm

children:
  - Rect:
      id: panel
      feature:
        type: pocket
        depth: 6mm
      children:
        - Keepout:
            children:
              - Inset:
                  distance: 50mm
                  children:
                    - Rect:
                        id: island
"""


    ast1 = parse_pml_yaml(original_pml)
    formatted_pml = format_pml_yaml(ast1)
    ast2 = parse_pml_yaml(formatted_pml)


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
    pml = """
Sheet:
  width: 400mm
  height: 400mm
  thickness: 19mm

children:
  - Rect:
      id: panel
      feature:
        type: pocket
        depth: 6mm
      children:
        - Keepout:
            children:
              - Circle:
                  diameter: 100mm
"""

    ast = parse_pml_yaml(pml)
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
    pml = """
Sheet:
  width: 500mm
  height: 400mm
  thickness: 19mm

children:
  - Rect:
      id: panel
      feature:
        type: pocket
        depth: 6mm
      children:
        - Keepout:
            children:
              - Inset:
                  distance: 50mm
                  children:
                    - RoundedRect:
                        radius: 10mm
"""

    ast = parse_pml_yaml(pml)
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
    pml = """
Sheet:
  width: 400mm
  height: 400mm
  thickness: 19mm

children:
  - Rect:
      id: panel
      feature:
        type: pocket
        depth: 6mm
      children:
        - Keepout:
            children:
              - Inset:
                  distance: 50mm
                  children:
                    - Rect:
                        id: outer_island
                        children:
                          - Keepout:
                              children:
                                - Rect:
                                    id: nested_island
"""

    try:
        ast = parse_pml_yaml(pml)
        assert False, "Should have raised PMLParseError for nested keepout"
    except PMLParseError as e:
        assert "nested keepout" in str(e).lower()


def test_removal_intent_includes_islands():
    from adapters.hints_to_removal import item_to_removal_intent

    pml = """
Sheet:
  width: 400mm
  height: 400mm
  thickness: 19mm

children:
  - Rect:
      id: panel
      feature:
        type: pocket
        depth: 6mm
      children:
        - Keepout:
            children:
              - Inset:
                  distance: 50mm
                  children:
                    - Rect:
                        id: island
"""

    ast = parse_pml_yaml(pml)
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
