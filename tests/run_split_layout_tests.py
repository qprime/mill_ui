
import sys
import traceback


def test_basic_split_2x2():
    print("Running test_basic_split_2x2...")

    from pml.yaml_parser import parse_pml_yaml
    from resolution.layout_resolver import resolve_layout

    pml = """
Sheet:
  width: 600mm
  height: 600mm
  thickness: 19mm
  margin: 0mm

children:
  - Rect:
      id: outer
      feature:
        type: profile
        side: outside
        depth: through
      children:
        - Frame:
            width: 50mm
            children:
              - Split:
                  cols: 2
                  rows: 2
                  rail: 50mm
                  mullion: 40mm
                  children:
                    - Cell:
                        children:
                          - Rect:
                              id: pane
                              feature:
                                type: pocket
                                depth: 6mm
"""

    ast = parse_pml_yaml(pml)
    assert ast.sheet.width_mm == 600
    assert ast.sheet.height_mm == 600

    flat = resolve_layout(ast)

    profile_items = [item for item in flat.items if item.feature and item.feature.type == "profile"]
    pocket_items = [item for item in flat.items if item.feature and item.feature.type == "pocket"]

    assert len(profile_items) == 1, f"Expected 1 profile (outer), got {len(profile_items)}"
    assert len(pocket_items) == 4, f"Expected 4 pockets (2x2 panes), got {len(pocket_items)}"

    first_pocket = pocket_items[0]
    assert abs(first_pocket.geometry.data["w_mm"] - 230.0) < 0.01
    assert abs(first_pocket.geometry.data["h_mm"] - 225.0) < 0.01

    print("  ✓ PASS")
    return True


def test_split_zero_rails_behaves_like_grid():
    print("Running test_split_zero_rails_behaves_like_grid...")

    from pml.yaml_parser import parse_pml_yaml
    from resolution.layout_resolver import resolve_layout

    pml_split = """
Sheet:
  width: 400mm
  height: 400mm
  thickness: 19mm
  margin: 0mm

children:
  - Split:
      cols: 2
      rows: 2
      rail: 0mm
      mullion: 0mm
      children:
        - Cell:
            children:
              - Rect:
                  id: cell_rect
                  children:
                    - Pocket:
                        depth: 5mm
"""

    pml_grid = """
Sheet:
  width: 400mm
  height: 400mm
  thickness: 19mm
  margin: 0mm

children:
  - Grid:
      cols: 2
      rows: 2
      gap: 0mm
      children:
        - Cell:
            children:
              - Rect:
                  id: cell_rect
                  children:
                    - Pocket:
                        depth: 5mm
"""

    split_ast = parse_pml_yaml(pml_split)
    grid_ast = parse_pml_yaml(pml_grid)

    split_flat = resolve_layout(split_ast)
    grid_flat = resolve_layout(grid_ast)

    assert len(split_flat.items) == len(grid_flat.items)

    split_pockets = [item for item in split_flat.items if item.feature and item.feature.type == "pocket"]
    grid_pockets = [item for item in grid_flat.items if item.feature and item.feature.type == "pocket"]

    assert len(split_pockets) == len(grid_pockets) == 4

    for sp, gp in zip(split_pockets, grid_pockets):
        assert abs(sp.geometry.data["w_mm"] - gp.geometry.data["w_mm"]) < 0.01
        assert abs(sp.geometry.data["h_mm"] - gp.geometry.data["h_mm"]) < 0.01

    print("  ✓ PASS")
    return True


def test_split_pane_size_calculation():
    print("Running test_split_pane_size_calculation...")

    from pml.yaml_parser import parse_pml_yaml
    from resolution.layout_resolver import resolve_layout

    pml = """
Sheet:
  width: 1000mm
  height: 800mm
  thickness: 19mm
  margin: 0mm

children:
  - Split:
      cols: 3
      rows: 4
      rail: 30mm
      mullion: 20mm
      children:
        - Cell:
            children:
              - Rect:
                  id: pane
                  feature:
                    type: pocket
                    depth: 5mm
"""

    ast = parse_pml_yaml(pml)
    flat = resolve_layout(ast)

    pockets = [item for item in flat.items if item.feature and item.feature.type == "pocket"]
    assert len(pockets) == 12, f"Expected 12 pockets (3x4 panes), got {len(pockets)}"

    first_pocket = pockets[0]
    assert abs(first_pocket.geometry.data["w_mm"] - 320.0) < 0.01
    assert abs(first_pocket.geometry.data["h_mm"] - 177.5) < 0.01

    print("  ✓ PASS")
    return True


def test_split_inside_inset():
    print("Running test_split_inside_inset...")

    from pml.yaml_parser import parse_pml_yaml
    from resolution.layout_resolver import resolve_layout

    pml = """
Sheet:
  width: 500mm
  height: 500mm
  thickness: 19mm
  margin: 0mm

children:
  - Inset:
      distance: 50mm
      children:
        - Split:
            cols: 2
            rows: 2
            rail: 40mm
            mullion: 30mm
            children:
              - Cell:
                  children:
                    - Rect:
                        id: pane
                        children:
                          - Pocket:
                              depth: 5mm
"""

    ast = parse_pml_yaml(pml)
    flat = resolve_layout(ast)

    pockets = [item for item in flat.items if item.feature and item.feature.type == "pocket"]
    assert len(pockets) == 4

    first_pocket = pockets[0]
    assert abs(first_pocket.geometry.data["w_mm"] - 185.0) < 0.01
    assert abs(first_pocket.geometry.data["h_mm"] - 180.0) < 0.01

    print("  ✓ PASS")
    return True


def test_split_roundtrip_preserves_rail_mullion():
    print("Running test_split_roundtrip_preserves_rail_mullion...")

    from pml.yaml_parser import parse_pml_yaml
    from pml.yaml_formatter import format_pml_yaml
    from resolution.layout_resolver import resolve_layout

    original_pml = """
Sheet:
  width: 600mm
  height: 400mm
  thickness: 19mm
  margin: 0mm

children:
  - Split:
      cols: 2
      rows: 3
      rail: 45mm
      mullion: 35mm
      children:
        - Cell:
            children:
              - Rect:
                  id: cell_rect
                  children:
                    - Pocket:
                        depth: 6mm
"""

    ast1 = parse_pml_yaml(original_pml)
    formatted_pml = format_pml_yaml(ast1)
    ast2 = parse_pml_yaml(formatted_pml)

    flat1 = resolve_layout(ast1)
    flat2 = resolve_layout(ast2)

    assert len(flat1.items) == len(flat2.items)

    pockets1 = [item for item in flat1.items if item.feature and item.feature.type == "pocket"]
    pockets2 = [item for item in flat2.items if item.feature and item.feature.type == "pocket"]

    assert len(pockets1) == len(pockets2) == 6

    for p1, p2 in zip(pockets1, pockets2):
        assert abs(p1.geometry.data["w_mm"] - p2.geometry.data["w_mm"]) < 0.01
        assert abs(p1.geometry.data["h_mm"] - p2.geometry.data["h_mm"]) < 0.01

    print("  ✓ PASS")
    return True


def test_french_door_acceptance():
    print("Running test_french_door_acceptance...")

    from pml.yaml_parser import parse_pml_yaml
    from resolution.layout_resolver import resolve_layout

    pml = """
Sheet:
  width: 800mm
  height: 1200mm
  thickness: 19mm
  margin: 0mm

children:
  - Rect:
      id: door_outer
      feature:
        type: profile
        side: outside
        depth: through
      children:
        - Frame:
            width: 60mm
            children:
              - Split:
                  cols: 2
                  rows: 2
                  rail: 50mm
                  mullion: 40mm
                  children:
                    - Cell:
                        children:
                          - Rect:
                              id: glass_pane
                              feature:
                                type: pocket
                                depth: 8mm
"""

    ast = parse_pml_yaml(pml)
    flat = resolve_layout(ast)

    profile_items = [item for item in flat.items if item.feature and item.feature.type == "profile"]
    pocket_items = [item for item in flat.items if item.feature and item.feature.type == "pocket"]

    assert len(profile_items) == 1, f"Expected 1 profile, got {len(profile_items)}"
    assert len(pocket_items) == 4

    first_pane = pocket_items[0]
    assert abs(first_pane.geometry.data["w_mm"] - 320.0) < 0.01
    assert abs(first_pane.geometry.data["h_mm"] - 515.0) < 0.01

    print("  ✓ PASS")
    return True


def test_split_single_row():
    print("Running test_split_single_row...")

    from pml.yaml_parser import parse_pml_yaml
    from resolution.layout_resolver import resolve_layout

    pml = """
Sheet:
  width: 600mm
  height: 200mm
  thickness: 19mm
  margin: 0mm

children:
  - Split:
      cols: 3
      rows: 1
      rail: 0mm
      mullion: 30mm
      children:
        - Cell:
            children:
              - Rect:
                  id: pane
                  feature:
                    type: pocket
                    depth: 5mm
"""

    ast = parse_pml_yaml(pml)
    flat = resolve_layout(ast)

    pockets = [item for item in flat.items if item.feature and item.feature.type == "pocket"]
    assert len(pockets) == 3

    first_pocket = pockets[0]
    assert abs(first_pocket.geometry.data["w_mm"] - 180.0) < 0.01
    assert abs(first_pocket.geometry.data["h_mm"] - 200.0) < 0.01

    print("  ✓ PASS")
    return True


def test_split_single_column():
    print("Running test_split_single_column...")

    from pml.yaml_parser import parse_pml_yaml
    from resolution.layout_resolver import resolve_layout

    pml = """
Sheet:
  width: 200mm
  height: 600mm
  thickness: 19mm
  margin: 0mm

children:
  - Split:
      cols: 1
      rows: 3
      rail: 40mm
      mullion: 0mm
      children:
        - Cell:
            children:
              - Rect:
                  id: pane
                  feature:
                    type: pocket
                    depth: 5mm
"""

    ast = parse_pml_yaml(pml)
    flat = resolve_layout(ast)

    pockets = [item for item in flat.items if item.feature and item.feature.type == "pocket"]
    assert len(pockets) == 3

    first_pocket = pockets[0]
    assert abs(first_pocket.geometry.data["w_mm"] - 200.0) < 0.01
    assert abs(first_pocket.geometry.data["h_mm"] - 173.33) < 0.01

    print("  ✓ PASS")
    return True


if __name__ == "__main__":
    tests = [
        test_basic_split_2x2,
        test_split_zero_rails_behaves_like_grid,
        test_split_pane_size_calculation,
        test_split_inside_inset,
        test_split_roundtrip_preserves_rail_mullion,
        test_french_door_acceptance,
        test_split_single_row,
        test_split_single_column,
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
    print(f"\n{passed}/{total} Split layout tests passed")

    sys.exit(0 if all(results) else 1)
