from pml.yaml_formatter import format_pml_yaml
from pml.yaml_parser import PMLParseError, parse_pml_yaml
from resolution.layout_resolver import resolve_layout


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
    assert panel.feature is not None
    assert panel.feature.type == "pocket"

    assert panel.geometry is not None
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
        assert pocket.geometry is not None
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

    assert panel.geometry is not None
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

    pocket1 = next(item for item in flat1.items if item.feature and item.feature.type == "pocket")
    pocket2 = next(item for item in flat2.items if item.feature and item.feature.type == "pocket")

    assert pocket1.geometry is not None
    assert pocket2.geometry is not None
    islands1 = pocket1.geometry.data.get("islands", [])
    islands2 = pocket2.geometry.data.get("islands", [])

    assert len(islands1) == len(islands2) == 1

    for island1, island2 in zip(islands1, islands2, strict=False):
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
    assert pocket.geometry is not None
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
    assert pocket.geometry is not None
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
        parse_pml_yaml(pml)
        raise AssertionError("Should have raised PMLParseError for nested keepout")
    except PMLParseError as e:
        assert "nested keepout" in str(e).lower()


def test_removal_intent_includes_islands():
    from adapters.ast_to_removal import item_to_removal_intent

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

    removal = item_to_removal_intent(pocket, sheet_thickness_mm=19.0)

    assert len(removal.constraints.islands) == 1

    island = removal.constraints.islands[0]
    assert abs(island.bounds.x_min - 50.0) < 0.01
    assert abs(island.bounds.x_max - 350.0) < 0.01
    assert abs(island.bounds.y_min - 50.0) < 0.01
    assert abs(island.bounds.y_max - 350.0) < 0.01


def test_pocket_planning_preserves_keepout_island():
    from shapely.geometry import Point, box

    from adapters.ast_to_removal import ast_to_removal_intents
    from adapters.removal_to_planner import removal_intents_to_planner_input
    from cam.config import Config
    from cam.model.machine import Machine
    from cam.model.stock import Stock
    from cam.moves import CutMove, RapidMove
    from cam.planner.passes import PassAccumulator
    from cam.planner.passes.pocket import plan_pocket_passes
    from cam.planner.passes.tools import normalize_tool_entries

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
                  distance: 60mm
                  children:
                    - Rect:
                        id: island
"""
    planner_input = removal_intents_to_planner_input(ast_to_removal_intents(resolve_layout(parse_pml_yaml(pml))))
    accumulator = PassAccumulator(
        machine=Machine(), stock=Stock(width=400, height=400, thickness=19), safe_z=5.0, prime_spindle=False
    )
    tool_db = normalize_tool_entries(
        [{"name": "12mm_flat", "diameter": 12.0, "kind": "flat", "rpm": 10000, "feed_xy": 800, "feed_z": 250}]
    )

    plan_pocket_passes(planner_input.pockets, accumulator=accumulator, tool_db=tool_db, config=Config())

    (record,) = accumulator.passes()
    island = box(60.0, 60.0, 340.0, 340.0)
    x = y = None
    z = 0.0
    cut_points = []
    for move in record.moves:
        if isinstance(move, (RapidMove, CutMove)):
            x = move.x if move.x is not None else x
            y = move.y if move.y is not None else y
            z = move.z if move.z is not None else z
            if isinstance(move, CutMove) and x is not None and y is not None and z < 0.0:
                cut_points.append(Point(x, y))
    assert cut_points
    assert min(island.distance(point) for point in cut_points) >= 6.0 - 1e-6
