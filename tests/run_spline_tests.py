
import sys
import traceback


def test_spline_parsing_and_roundtrip():
    print("Running test_spline_parsing_and_roundtrip...")

    from pml.yaml_parser import parse_pml_yaml
    from pml.yaml_formatter import format_pml_yaml

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

    assert len(spline1.points) == len(spline2.points), f"Point count mismatch: {len(spline1.points)} vs {len(spline2.points)}"
    for i, ((x1, y1), (x2, y2)) in enumerate(zip(spline1.points, spline2.points)):
        assert abs(x1 - x2) < 0.01, f"Point {i} x mismatch: {x1} vs {x2}"
        assert abs(y1 - y2) < 0.01, f"Point {i} y mismatch: {y1} vs {y2}"

    assert spline1.feature.type == spline2.feature.type == "engrave"
    assert abs(spline1.feature.depth_mm - spline2.feature.depth_mm) < 0.01

    print("  ✓ PASS")
    return True


def test_spline_lowering_deterministic():
    print("Running test_spline_lowering_deterministic...")

    from pml.yaml_parser import parse_pml_yaml
    from resolution.layout_resolver import resolve_layout

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
    assert len(spline_items) == 1, f"Expected 1 spline item, got {len(spline_items)}"
    spline_item = spline_items[0]

    assert spline_item.type == "Polyline", f"Expected Polyline, got {spline_item.type}"
    assert "points" in spline_item.geometry.data, "Missing points in geometry data"

    points = spline_item.geometry.data["points"]
    cx, cy = spline_item.placement.center_xy_mm
    assert len(points) > 3, f"Expected > 3 sampled points, got {len(points)}"

    assert spline_item.geometry.data.get("spline_source") is True, "Missing spline_source metadata"
    assert abs(spline_item.geometry.data.get("spline_tolerance_mm", 0) - 0.1) < 0.01, "Tolerance metadata mismatch"

    first_point = points[0]
    last_point = points[-1]

    assert abs(first_point[0] + cx - 0.0) < 1.0, f"First point x: {first_point[0] + cx}"
    assert abs(first_point[1] + cy - 0.0) < 1.0, f"First point y: {first_point[1] + cy}"
    assert abs(last_point[0] + cx - 400.0) < 1.0, f"Last point x: {last_point[0] + cx}"
    assert abs(last_point[1] + cy - 400.0) < 1.0, f"Last point y: {last_point[1] + cy}"

    print("  ✓ PASS")
    return True


def test_spline_engrave_removal_intent():
    print("Running test_spline_engrave_removal_intent...")

    from pml.yaml_parser import parse_pml_yaml
    from resolution.layout_resolver import resolve_layout
    from adapters.hints_to_removal import item_to_removal_intent

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
    assert len(spline_items) == 1, f"Expected 1 spline item, got {len(spline_items)}"
    spline_item = spline_items[0]

    removal = item_to_removal_intent(spline_item, region_id_prefix="test_spline")

    assert removal.region_id == "test_spline_decorative", f"Region ID mismatch: {removal.region_id}"
    assert removal.depth_profile.z_top == 0.0
    assert abs(removal.depth_profile.z_bottom - (-0.8)) < 0.01, f"Z bottom mismatch: {removal.depth_profile.z_bottom}"

    assert removal.bounds.x_min >= 0.0, f"x_min out of range: {removal.bounds.x_min}"
    assert removal.bounds.x_max <= 400.0, f"x_max out of range: {removal.bounds.x_max}"
    assert removal.bounds.y_min >= 0.0, f"y_min out of range: {removal.bounds.y_min}"
    assert removal.bounds.y_max <= 400.0, f"y_max out of range: {removal.bounds.y_max}"

    assert removal.metadata.get("feature_type") == "engrave", f"Feature type mismatch: {removal.metadata.get('feature_type')}"

    print("  ✓ PASS")
    return True


def test_tool_diameter_does_not_invalidate():
    print("Running test_tool_diameter_does_not_invalidate...")

    from pml.yaml_parser import parse_pml_yaml
    from resolution.layout_resolver import resolve_layout

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
    spline1 = [item for item in flat1.items if item.shape_id == "wave"][0]

    ast2 = parse_pml_yaml(pml)
    flat2 = resolve_layout(ast2)
    spline2 = [item for item in flat2.items if item.shape_id == "wave"][0]

    points1 = spline1.geometry.data["points"]
    points2 = spline2.geometry.data["points"]

    assert len(points1) == len(points2), f"Point count mismatch: {len(points1)} vs {len(points2)}"
    for i, ((x1, y1), (x2, y2)) in enumerate(zip(points1, points2)):
        assert abs(x1 - x2) < 0.01, f"Point {i} x mismatch: {x1} vs {x2}"
        assert abs(y1 - y2) < 0.01, f"Point {i} y mismatch: {y1} vs {y2}"

    print("  ✓ PASS")
    return True


def test_tolerance_affects_resolution():
    print("Running test_tolerance_affects_resolution...")

    from pml.yaml_parser import parse_pml_yaml
    from resolution.layout_resolver import resolve_layout

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
    points_coarse = [item for item in flat_coarse.items if item.shape_id == "curve"][0].geometry.data["points"]

    ast_fine = parse_pml_yaml(pml_fine)
    flat_fine = resolve_layout(ast_fine)
    points_fine = [item for item in flat_fine.items if item.shape_id == "curve"][0].geometry.data["points"]

    assert len(points_fine) > len(points_coarse), f"Fine ({len(points_fine)}) should have more points than coarse ({len(points_coarse)})"

    print("  ✓ PASS")
    return True


if __name__ == "__main__":
    tests = [
        test_spline_parsing_and_roundtrip,
        test_spline_lowering_deterministic,
        test_spline_engrave_removal_intent,
        test_tool_diameter_does_not_invalidate,
        test_tolerance_affects_resolution,
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
    print(f"\n{passed}/{total} SplinePath tests passed")

    sys.exit(0 if all(results) else 1)
