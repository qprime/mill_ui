from pml.yaml_formatter import format_pml_yaml
from pml.yaml_parser import PMLParseError as ParseError
from pml.yaml_parser import parse_pml_yaml
from resolution.layout_resolver import resolve_layout


def test_polyline_inside_rect():
    pml = """
Sheet:
  width: 400mm
  height: 300mm
  thickness: 19mm
  margin: 0mm

children:
  - Rect:
      id: canvas
      children:
        - Polyline:
            id: path1
            points: [[0.00, 0.00], [1.00, 1.00]]
            children:
              - Engrave:
                  depth: 1mm
"""

    ast = parse_pml_yaml(pml)
    flat = resolve_layout(ast)

    items = flat.items
    assert len(items) == 2

    polyline_item = next(item for item in items if item.type == "Polyline")
    assert polyline_item.geometry is not None
    assert polyline_item.placement is not None
    points = polyline_item.geometry.data["points"]
    cx, cy = polyline_item.placement.center_xy_mm

    assert len(points) == 2
    assert abs(cx - 200.0) < 0.01
    assert abs(cy - 150.0) < 0.01
    assert abs(points[0][0] + 200.0) < 0.01
    assert abs(points[0][1] + 150.0) < 0.01
    assert abs(points[1][0] - 200.0) < 0.01
    assert abs(points[1][1] - 150.0) < 0.01


def test_polyline_inside_rounded_rect():
    pml = """
Sheet:
  width: 500mm
  height: 500mm
  thickness: 19mm
  margin: 0mm

children:
  - RoundedRect:
      id: panel
      radius: 20mm
      children:
        - Polyline:
            id: diagonal
            points: [[0.10, 0.10], [0.90, 0.90]]
            children:
              - Engrave:
                  depth: 1mm
"""

    ast = parse_pml_yaml(pml)
    flat = resolve_layout(ast)

    items = flat.items
    polyline_item = next(item for item in items if item.type == "Polyline")
    assert polyline_item.geometry is not None
    assert polyline_item.placement is not None
    points = polyline_item.geometry.data["points"]
    cx, cy = polyline_item.placement.center_xy_mm

    assert abs(cx - 250.0) < 0.01
    assert abs(cy - 250.0) < 0.01
    assert abs(points[0][0] + 200.0) < 0.01
    assert abs(points[0][1] + 200.0) < 0.01
    assert abs(points[1][0] - 200.0) < 0.01
    assert abs(points[1][1] - 200.0) < 0.01


def test_polyline_inside_circle_fit():
    pml = """
Sheet:
  width: 400mm
  height: 400mm
  thickness: 19mm
  margin: 0mm

children:
  - Circle:
      id: boundary
      fit: true
      children:
        - Polyline:
            id: cross
            points: [[0.25, 0.50], [0.75, 0.50], [0.50, 0.50], [0.50, 0.25], [0.50, 0.75]]
            children:
              - Engrave:
                  depth: 1mm
"""

    ast = parse_pml_yaml(pml)
    flat = resolve_layout(ast)

    polyline_item = next(item for item in flat.items if item.type == "Polyline")
    assert polyline_item.geometry is not None
    assert polyline_item.placement is not None
    points = polyline_item.geometry.data["points"]
    cx, cy = polyline_item.placement.center_xy_mm

    assert len(points) == 5
    assert abs(cx - 200.0) < 0.01
    assert abs(cy - 200.0) < 0.01


def test_polyline_with_10_points():
    pml = """
Sheet:
  width: 600mm
  height: 400mm
  thickness: 19mm
  margin: 0mm

children:
  - Polyline:
      id: zigzag
      points: [[0.0, 0.0], [0.1, 0.9], [0.2, 0.1], [0.3, 0.8], [0.4, 0.2], [0.5, 0.7], [0.6, 0.3], [0.7, 0.6], [0.8, 0.4], [0.9, 0.5]]
      children:
        - Engrave:
            depth: 1mm
"""

    ast = parse_pml_yaml(pml)
    flat = resolve_layout(ast)

    polyline_item = flat.items[0]
    assert polyline_item.geometry is not None
    assert polyline_item.placement is not None
    points = polyline_item.geometry.data["points"]
    cx, cy = polyline_item.placement.center_xy_mm

    assert len(points) == 10

    assert abs(cx - 270.0) < 0.01
    assert abs(cy - 180.0) < 0.01


def test_polyline_error_out_of_range_x_negative():
    pml = """
Sheet:
  width: 400mm
  height: 400mm
  thickness: 19mm
  margin: 0mm

children:
  - Polyline:
      id: bad
      points: [[-0.1, 0.5], [1.0, 0.5]]
      children:
        - Engrave:
            depth: 1mm
"""

    try:
        ast = parse_pml_yaml(pml)

        resolve_layout(ast)
        raise AssertionError("Should have raised ValueError")
    except ValueError as e:
        assert "out of range" in str(e).lower()


def test_polyline_error_out_of_range_x_over_one():
    pml = """
Sheet:
  width: 400mm
  height: 400mm
  thickness: 19mm
  margin: 0mm

children:
  - Polyline:
      id: bad
      points: [[0.5, 0.5], [1.1, 0.5]]
      children:
        - Engrave:
            depth: 1mm
"""

    try:
        ast = parse_pml_yaml(pml)
        resolve_layout(ast)
        raise AssertionError("Should have raised ValueError")
    except ValueError as e:
        assert "out of range" in str(e).lower()


def test_polyline_error_out_of_range_y_negative():
    pml = """
Sheet:
  width: 400mm
  height: 400mm
  thickness: 19mm
  margin: 0mm

children:
  - Polyline:
      id: bad
      points: [[0.5, -0.1], [0.5, 1.0]]
      children:
        - Engrave:
            depth: 1mm
"""

    try:
        ast = parse_pml_yaml(pml)
        resolve_layout(ast)
        raise AssertionError("Should have raised ValueError")
    except ValueError as e:
        assert "out of range" in str(e).lower()


def test_polyline_error_out_of_range_y_over_one():
    pml = """
Sheet:
  width: 400mm
  height: 400mm
  thickness: 19mm
  margin: 0mm

children:
  - Polyline:
      id: bad
      points: [[0.5, 0.5], [0.5, 1.1]]
      children:
        - Engrave:
            depth: 1mm
"""

    try:
        ast = parse_pml_yaml(pml)
        resolve_layout(ast)
        raise AssertionError("Should have raised ValueError")
    except ValueError as e:
        assert "out of range" in str(e).lower()


def test_polyline_error_single_point():
    pml = """
Sheet:
  width: 400mm
  height: 400mm
  thickness: 19mm
  margin: 0mm

children:
  - Polyline:
      id: bad
      points: [[0.5, 0.5]]
      children:
        - Engrave:
            depth: 1mm
"""

    try:
        ast = parse_pml_yaml(pml)
        resolve_layout(ast)
        raise AssertionError("Should have raised ValueError or ParseError")
    except (ValueError, ParseError) as e:
        assert "2 points" in str(e).lower() or "at least 2" in str(e).lower()


def test_polyline_roundtrip_preserves_coordinates():
    original_pml = """
Sheet:
  width: 500mm
  height: 400mm
  thickness: 19mm
  margin: 0mm

children:
  - Polyline:
      id: path1
      points: [[0.10, 0.20], [0.50, 0.50], [0.90, 0.80]]
      children:
        - Engrave:
            depth: 1mm
"""

    ast1 = parse_pml_yaml(original_pml)
    formatted_pml = format_pml_yaml(ast1)
    ast2 = parse_pml_yaml(formatted_pml)

    flat1 = resolve_layout(ast1)
    flat2 = resolve_layout(ast2)

    assert flat1.items[0].geometry is not None
    assert flat2.items[0].geometry is not None
    assert flat1.items[0].placement is not None
    assert flat2.items[0].placement is not None
    points1 = flat1.items[0].geometry.data["points"]
    points2 = flat2.items[0].geometry.data["points"]
    cx1, cy1 = flat1.items[0].placement.center_xy_mm
    cx2, cy2 = flat2.items[0].placement.center_xy_mm

    assert len(points1) == len(points2) == 3

    for (x1, y1), (x2, y2) in zip(points1, points2, strict=False):
        assert abs((x1 + cx1) - (x2 + cx2)) < 0.01
        assert abs((y1 + cy1) - (y2 + cy2)) < 0.01


def test_polyline_in_inset_region():
    pml = """
Sheet:
  width: 600mm
  height: 400mm
  thickness: 19mm
  margin: 0mm

children:
  - Inset:
      distance: 50mm
      children:
        - Polyline:
            id: path1
            points: [[0.00, 0.00], [1.00, 1.00]]
            children:
              - Engrave:
                  depth: 1mm
"""

    ast = parse_pml_yaml(pml)
    flat = resolve_layout(ast)

    polyline_item = flat.items[0]
    assert polyline_item.geometry is not None
    assert polyline_item.placement is not None
    points = polyline_item.geometry.data["points"]
    cx, cy = polyline_item.placement.center_xy_mm

    assert abs(cx - 300.0) < 0.01
    assert abs(cy - 200.0) < 0.01
    assert abs(points[0][0] + cx - 50.0) < 0.01
    assert abs(points[0][1] + cy - 50.0) < 0.01
    assert abs(points[1][0] + cx - 550.0) < 0.01
    assert abs(points[1][1] + cy - 350.0) < 0.01
