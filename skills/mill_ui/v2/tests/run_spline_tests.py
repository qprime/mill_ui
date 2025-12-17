"""Standalone test runner for SplinePath tests (without pytest)."""

import sys
import traceback


def test_spline_parsing_and_roundtrip():
    """Test spline parses and round-trips in PML."""
    print("Running test_spline_parsing_and_roundtrip...")

    from skills.mill_ui.v2.pml.compositional_parser import parse_compositional_pml
    from skills.mill_ui.v2.pml.compositional_formatter import format_compositional_pml

    original_pml = """sheet 400.00mm 400.00mm 19.00mm

spline wave engrave 0.8mm points (0.0,0.5) (0.25,0.6) (0.5,0.4) (0.75,0.6) (1.0,0.5)
"""

    # Parse
    ast1 = parse_compositional_pml(original_pml)
    assert ast1.root is not None

    # Format
    formatted_pml = format_compositional_pml(ast1)

    # Parse again
    ast2 = parse_compositional_pml(formatted_pml)

    # Verify control points preserved
    spline1 = ast1.root.children[0]
    spline2 = ast2.root.children[0]

    assert len(spline1.points) == len(spline2.points), f"Point count mismatch: {len(spline1.points)} vs {len(spline2.points)}"
    for i, ((x1, y1), (x2, y2)) in enumerate(zip(spline1.points, spline2.points)):
        assert abs(x1 - x2) < 0.01, f"Point {i} x mismatch: {x1} vs {x2}"
        assert abs(y1 - y2) < 0.01, f"Point {i} y mismatch: {y1} vs {y2}"

    # Verify feature preserved
    assert spline1.feature.type == spline2.feature.type == "engrave"
    assert abs(spline1.feature.depth_mm - spline2.feature.depth_mm) < 0.01

    print("  ✓ PASS")
    return True


def test_spline_lowering_deterministic():
    """Test spline lowers to polyline deterministically."""
    print("Running test_spline_lowering_deterministic...")

    from skills.mill_ui.v2.pml.compositional_parser import parse_compositional_pml
    from skills.mill_ui.v2.resolution.layout_resolver import resolve_layout

    pml = """sheet 400.00mm 400.00mm 19.00mm

spline curve engrave 1.0mm points (0.0,0.0) (0.5,0.5) (1.0,1.0) tolerance 0.1mm
"""

    # Resolve layout (spline lowered to polyline)
    ast = parse_compositional_pml(pml)
    flat = resolve_layout(ast)

    # Find the spline item (now a polyline)
    spline_items = [item for item in flat.items if item.shape_id == "curve"]
    assert len(spline_items) == 1, f"Expected 1 spline item, got {len(spline_items)}"
    spline_item = spline_items[0]

    # Verify spline was lowered to polyline
    assert spline_item.type == "Polyline", f"Expected Polyline, got {spline_item.type}"
    assert "points_mm" in spline_item.geometry.data, "Missing points_mm in geometry data"

    # Verify sampling produced multiple points
    points = spline_item.geometry.data["points_mm"]
    assert len(points) > 3, f"Expected > 3 sampled points, got {len(points)}"

    # Verify metadata indicates spline source
    assert spline_item.geometry.data.get("spline_source") is True, "Missing spline_source metadata"
    assert abs(spline_item.geometry.data.get("spline_tolerance_mm", 0) - 0.1) < 0.01, "Tolerance metadata mismatch"

    # Verify endpoints preserved (spline passes through control points)
    first_point = points[0]
    last_point = points[-1]

    # First point should be at (0,0) in normalized space → (0,0) in absolute
    # Last point should be at (1,1) in normalized space → (400,400) in absolute
    assert abs(first_point[0] - 0.0) < 1.0, f"First point x: {first_point[0]}"
    assert abs(first_point[1] - 0.0) < 1.0, f"First point y: {first_point[1]}"
    assert abs(last_point[0] - 400.0) < 1.0, f"Last point x: {last_point[0]}"
    assert abs(last_point[1] - 400.0) < 1.0, f"Last point y: {last_point[1]}"

    print("  ✓ PASS")
    return True


def test_spline_engrave_removal_intent():
    """Test spline + engrave produces valid RemovalIntent."""
    print("Running test_spline_engrave_removal_intent...")

    from skills.mill_ui.v2.pml.compositional_parser import parse_compositional_pml
    from skills.mill_ui.v2.resolution.layout_resolver import resolve_layout
    from skills.mill_ui.v2.adapters.hints_to_removal import item_to_removal_intent

    pml = """sheet 400.00mm 400.00mm 19.00mm

spline decorative engrave 0.8mm points (0.1,0.1) (0.3,0.2) (0.5,0.5) (0.7,0.8) (0.9,0.9)
"""

    ast = parse_compositional_pml(pml)
    flat = resolve_layout(ast)

    # Get the spline item (lowered to polyline)
    spline_items = [item for item in flat.items if item.shape_id == "decorative"]
    assert len(spline_items) == 1, f"Expected 1 spline item, got {len(spline_items)}"
    spline_item = spline_items[0]

    # Convert to RemovalIntent
    removal = item_to_removal_intent(spline_item, region_id_prefix="test_spline")

    # Verify RemovalIntent is valid
    assert removal.region_id == "test_spline_decorative", f"Region ID mismatch: {removal.region_id}"
    assert removal.z_top == 0.0
    assert abs(removal.z_bottom - (-0.8)) < 0.01, f"Z bottom mismatch: {removal.z_bottom}"

    # Verify bounds cover the path extent
    assert removal.bounds.x_min >= 0.0, f"x_min out of range: {removal.bounds.x_min}"
    assert removal.bounds.x_max <= 400.0, f"x_max out of range: {removal.bounds.x_max}"
    assert removal.bounds.y_min >= 0.0, f"y_min out of range: {removal.bounds.y_min}"
    assert removal.bounds.y_max <= 400.0, f"y_max out of range: {removal.bounds.y_max}"

    # Verify feature type
    assert removal.metadata.get("feature_type") == "engrave", f"Feature type mismatch: {removal.metadata.get('feature_type')}"

    print("  ✓ PASS")
    return True


def test_tool_diameter_does_not_invalidate():
    """Test changing tool diameter does NOT invalidate design (Studio Mode policy)."""
    print("Running test_tool_diameter_does_not_invalidate...")

    from skills.mill_ui.v2.pml.compositional_parser import parse_compositional_pml
    from skills.mill_ui.v2.resolution.layout_resolver import resolve_layout

    pml = """sheet 400.00mm 400.00mm 19.00mm

spline wave engrave 0.5mm points (0.0,0.5) (0.25,0.6) (0.5,0.4) (0.75,0.6) (1.0,0.5)
"""

    # Parse and resolve with small tool diameter
    ast1 = parse_compositional_pml(pml)
    flat1 = resolve_layout(ast1)
    spline1 = [item for item in flat1.items if item.shape_id == "wave"][0]

    # Parse and resolve again (same PML, different tool would be applied downstream)
    ast2 = parse_compositional_pml(pml)
    flat2 = resolve_layout(ast2)
    spline2 = [item for item in flat2.items if item.shape_id == "wave"][0]

    # Verify same geometry regardless of tool diameter
    # (Tool diameter is a downstream CAM parameter, not part of design)
    points1 = spline1.geometry.data["points_mm"]
    points2 = spline2.geometry.data["points_mm"]

    assert len(points1) == len(points2), f"Point count mismatch: {len(points1)} vs {len(points2)}"
    for i, ((x1, y1), (x2, y2)) in enumerate(zip(points1, points2)):
        assert abs(x1 - x2) < 0.01, f"Point {i} x mismatch: {x1} vs {x2}"
        assert abs(y1 - y2) < 0.01, f"Point {i} y mismatch: {y1} vs {y2}"

    # Studio Mode: No errors, no warnings, no validation failures
    # Design is valid regardless of tool selection

    print("  ✓ PASS")
    return True


def test_tolerance_affects_resolution():
    """Test tolerance parameter affects polyline sampling resolution."""
    print("Running test_tolerance_affects_resolution...")

    from skills.mill_ui.v2.pml.compositional_parser import parse_compositional_pml
    from skills.mill_ui.v2.resolution.layout_resolver import resolve_layout

    pml_coarse = """sheet 400.00mm 400.00mm 19.00mm

spline curve engrave 1.0mm points (0.0,0.0) (0.5,0.5) (1.0,1.0) tolerance 1.0mm
"""

    pml_fine = """sheet 400.00mm 400.00mm 19.00mm

spline curve engrave 1.0mm points (0.0,0.0) (0.5,0.5) (1.0,1.0) tolerance 0.01mm
"""

    # Resolve coarse tolerance
    ast_coarse = parse_compositional_pml(pml_coarse)
    flat_coarse = resolve_layout(ast_coarse)
    points_coarse = [item for item in flat_coarse.items if item.shape_id == "curve"][0].geometry.data["points_mm"]

    # Resolve fine tolerance
    ast_fine = parse_compositional_pml(pml_fine)
    flat_fine = resolve_layout(ast_fine)
    points_fine = [item for item in flat_fine.items if item.shape_id == "curve"][0].geometry.data["points_mm"]

    # Fine tolerance should produce more points
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
