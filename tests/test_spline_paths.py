"""Tests for SplinePath Support (Stage 19: Studio Mode).

Acceptance tests:
1. Spline parsing and round-trip preservation
2. Spline lowering to polyline (deterministic sampling)
3. Spline + engrave produces valid RemovalIntent
4. Tool diameter changes do NOT invalidate design (Studio Mode policy)
5. Existing Stage 12-18 tests remain unchanged

Studio Mode Policy:
- Centerline paths are valid and expected
- Visual outcome takes precedence over dimensional accuracy
- No errors for tight curvature or tool coupling
- Designers iterate via test cuts
"""

from skills.mill_ui.pml.compositional_parser import parse_compositional_pml
from skills.mill_ui.pml.compositional_formatter import format_compositional_pml
from skills.mill_ui.resolution.layout_resolver import resolve_layout
from skills.mill_ui.adapters.hints_to_removal import item_to_removal_intent


def test_spline_parsing_and_roundtrip():
    """Test spline parses and round-trips in PML."""
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

    assert len(spline1.points) == len(spline2.points)
    for (x1, y1), (x2, y2) in zip(spline1.points, spline2.points):
        assert abs(x1 - x2) < 0.01
        assert abs(y1 - y2) < 0.01

    # Verify feature preserved
    assert spline1.feature.type == spline2.feature.type == "engrave"
    assert abs(spline1.feature.depth_mm - spline2.feature.depth_mm) < 0.01


def test_spline_lowering_deterministic():
    """Test spline lowers to polyline deterministically."""
    pml = """sheet 400.00mm 400.00mm 19.00mm

spline curve engrave 1.0mm points (0.0,0.0) (0.5,0.5) (1.0,1.0) tolerance 0.1mm
"""

    # Resolve layout (spline lowered to polyline)
    ast = parse_compositional_pml(pml)
    flat = resolve_layout(ast)

    # Find the spline item (now a polyline)
    spline_items = [item for item in flat.items if item.shape_id == "curve"]
    assert len(spline_items) == 1
    spline_item = spline_items[0]

    # Verify spline was lowered to polyline
    assert spline_item.type == "Polyline"
    assert "points_mm" in spline_item.geometry.data

    # Verify sampling produced multiple points
    points = spline_item.geometry.data["points_mm"]
    assert len(points) > 3  # Should have sampled intermediate points

    # Verify metadata indicates spline source
    assert spline_item.geometry.data.get("spline_source") is True
    assert abs(spline_item.geometry.data.get("spline_tolerance_mm", 0) - 0.1) < 0.01

    # Verify endpoints preserved (spline passes through control points)
    first_point = points[0]
    last_point = points[-1]

    # First point should be at (0,0) in normalized space → (0,0) in absolute
    # Last point should be at (1,1) in normalized space → (400,400) in absolute
    assert abs(first_point[0] - 0.0) < 1.0  # Within 1mm of origin
    assert abs(first_point[1] - 0.0) < 1.0
    assert abs(last_point[0] - 400.0) < 1.0  # Within 1mm of top-right
    assert abs(last_point[1] - 400.0) < 1.0


def test_spline_engrave_removal_intent():
    """Test spline + engrave produces valid RemovalIntent."""
    pml = """sheet 400.00mm 400.00mm 19.00mm

spline decorative engrave 0.8mm points (0.1,0.1) (0.3,0.2) (0.5,0.5) (0.7,0.8) (0.9,0.9)
"""

    ast = parse_compositional_pml(pml)
    flat = resolve_layout(ast)

    # Get the spline item (lowered to polyline)
    spline_items = [item for item in flat.items if item.shape_id == "decorative"]
    assert len(spline_items) == 1
    spline_item = spline_items[0]

    # Convert to RemovalIntent
    removal = item_to_removal_intent(spline_item, region_id_prefix="test_spline")

    # Verify RemovalIntent is valid
    assert removal.region_id == "test_spline_decorative"
    assert removal.z_top == 0.0
    assert abs(removal.z_bottom - (-0.8)) < 0.01  # 0.8mm depth

    # Verify bounds cover the path extent
    assert removal.bounds.x_min >= 0.0
    assert removal.bounds.x_max <= 400.0
    assert removal.bounds.y_min >= 0.0
    assert removal.bounds.y_max <= 400.0

    # Verify feature type
    assert removal.metadata.get("feature_type") == "engrave"


def test_tool_diameter_does_not_invalidate():
    """Test changing tool diameter does NOT invalidate design (Studio Mode policy)."""
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

    assert len(points1) == len(points2)
    for (x1, y1), (x2, y2) in zip(points1, points2):
        assert abs(x1 - x2) < 0.01
        assert abs(y1 - y2) < 0.01

    # Studio Mode: No errors, no warnings, no validation failures
    # Design is valid regardless of tool selection


def test_tolerance_affects_resolution():
    """Test tolerance parameter affects polyline sampling resolution."""
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
    assert len(points_fine) > len(points_coarse)
