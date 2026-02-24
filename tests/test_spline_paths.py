from adapters.hints_to_removal import simple_item_to_removal_intent
from pml.yaml_formatter import format_pml_yaml
from pml.yaml_parser import parse_pml_yaml
from resolution.layout_resolver import resolve_layout


def test_spline_parsing_and_roundtrip():
    original_pml = """
Sheet:
  width: 400mm
  height: 400mm
  thickness: 19mm
  margin: 0mm

children:
  - Spline:
      id: wave
      points: [[0.0, 0.5], [0.25, 0.6], [0.5, 0.4], [0.75, 0.6], [1.0, 0.5]]
      children:
        - Engrave:
            depth: 0.8mm
"""

    ast1 = parse_pml_yaml(original_pml)
    assert ast1.root is not None

    formatted_pml = format_pml_yaml(ast1)

    ast2 = parse_pml_yaml(formatted_pml)

    spline1 = ast1.root.children[0]
    spline2 = ast2.root.children[0]

    assert len(spline1.points) == len(spline2.points)
    for (x1, y1), (x2, y2) in zip(spline1.points, spline2.points, strict=False):
        assert abs(x1 - x2) < 0.01
        assert abs(y1 - y2) < 0.01

    assert spline1.feature.type == spline2.feature.type == "engrave"
    assert abs(spline1.feature.depth_mm - spline2.feature.depth_mm) < 0.01


def test_spline_lowering_deterministic():
    pml = """
Sheet:
  width: 400mm
  height: 400mm
  thickness: 19mm
  margin: 0mm

children:
  - Spline:
      id: curve
      points: [[0.0, 0.0], [0.5, 0.5], [1.0, 1.0]]
      tolerance: 0.1mm
      children:
        - Engrave:
            depth: 1mm
"""

    ast = parse_pml_yaml(pml)
    flat = resolve_layout(ast)

    spline_items = [item for item in flat.items if item.shape_id == "curve"]
    assert len(spline_items) == 1
    spline_item = spline_items[0]

    assert spline_item.type == "Polyline"
    assert "points" in spline_item.geometry.data

    points = spline_item.geometry.data["points"]
    cx, cy = spline_item.placement.center_xy_mm
    assert len(points) > 3

    assert spline_item.geometry.data.get("spline_source") is True
    assert abs(spline_item.geometry.data.get("spline_tolerance_mm", 0) - 0.1) < 0.01

    first_abs = (points[0][0] + cx, points[0][1] + cy)
    last_abs = (points[-1][0] + cx, points[-1][1] + cy)

    assert abs(first_abs[0] - 0.0) < 1.0
    assert abs(first_abs[1] - 0.0) < 1.0
    assert abs(last_abs[0] - 400.0) < 1.0
    assert abs(last_abs[1] - 400.0) < 1.0


def test_spline_engrave_removal_intent():
    pml = """
Sheet:
  width: 400mm
  height: 400mm
  thickness: 19mm
  margin: 0mm

children:
  - Spline:
      id: decorative
      points: [[0.1, 0.1], [0.3, 0.2], [0.5, 0.5], [0.7, 0.8], [0.9, 0.9]]
      children:
        - Engrave:
            depth: 0.8mm
"""

    ast = parse_pml_yaml(pml)
    flat = resolve_layout(ast)

    spline_items = [item for item in flat.items if item.shape_id == "decorative"]
    assert len(spline_items) == 1
    spline_item = spline_items[0]

    removal = simple_item_to_removal_intent(spline_item, region_id_prefix="test_spline")

    assert removal.region_id == "test_spline_decorative"
    assert removal.depth_profile.z_top == 0.0
    assert abs(removal.depth_profile.z_bottom - (-0.8)) < 0.01

    assert removal.bounds.x_min >= 0.0
    assert removal.bounds.x_max <= 400.0
    assert removal.bounds.y_min >= 0.0
    assert removal.bounds.y_max <= 400.0

    assert removal.feature_type == "engrave"


def test_tool_diameter_does_not_invalidate():
    pml = """
Sheet:
  width: 400mm
  height: 400mm
  thickness: 19mm
  margin: 0mm

children:
  - Spline:
      id: wave
      points: [[0.0, 0.5], [0.25, 0.6], [0.5, 0.4], [0.75, 0.6], [1.0, 0.5]]
      children:
        - Engrave:
            depth: 0.5mm
"""

    ast1 = parse_pml_yaml(pml)
    flat1 = resolve_layout(ast1)
    spline1 = next(item for item in flat1.items if item.shape_id == "wave")

    ast2 = parse_pml_yaml(pml)
    flat2 = resolve_layout(ast2)
    spline2 = next(item for item in flat2.items if item.shape_id == "wave")

    points1 = spline1.geometry.data["points"]
    points2 = spline2.geometry.data["points"]

    assert len(points1) == len(points2)
    for (x1, y1), (x2, y2) in zip(points1, points2, strict=False):
        assert abs(x1 - x2) < 0.01
        assert abs(y1 - y2) < 0.01


def test_tolerance_affects_resolution():
    pml_coarse = """
Sheet:
  width: 400mm
  height: 400mm
  thickness: 19mm
  margin: 0mm

children:
  - Spline:
      id: curve
      points: [[0.0, 0.0], [0.5, 0.5], [1.0, 1.0]]
      tolerance: 1mm
      children:
        - Engrave:
            depth: 1mm
"""

    pml_fine = """
Sheet:
  width: 400mm
  height: 400mm
  thickness: 19mm
  margin: 0mm

children:
  - Spline:
      id: curve
      points: [[0.0, 0.0], [0.5, 0.5], [1.0, 1.0]]
      tolerance: 0.01mm
      children:
        - Engrave:
            depth: 1mm
"""

    ast_coarse = parse_pml_yaml(pml_coarse)
    flat_coarse = resolve_layout(ast_coarse)
    points_coarse = next(item for item in flat_coarse.items if item.shape_id == "curve").geometry.data["points"]

    ast_fine = parse_pml_yaml(pml_fine)
    flat_fine = resolve_layout(ast_fine)
    points_fine = next(item for item in flat_fine.items if item.shape_id == "curve").geometry.data["points"]

    assert len(points_fine) > len(points_coarse)
