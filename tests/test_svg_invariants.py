from __future__ import annotations

from cam.pipeline import run_pipeline
from pml import parse_pml
from validation.core import Verdict
from validation.invariants.svg_invariants import (
    SVG_INVARIANT_IDS,
    check_svg_invariants,
)

PANEL_PML = """Sheet:
  width: 260mm
  height: 180mm
  thickness: 19mm
  material: mdf
children:
- Rect:
    id: panel
    feature:
      type: profile
      depth: through
      side: outside
    at:
      x: 130mm
      y: 90mm
      width: 200mm
      height: 140mm
- Rect:
    id: panel_recess
    feature:
      type: pocket
      depth: 4mm
    at:
      x: 130mm
      y: 90mm
      width: 110mm
      height: 70mm
- Circle:
    id: panel_hole
    diameter: 6mm
    feature:
      type: hole
      depth: 12mm
    at:
      x: 45mm
      y: 40mm
"""


def _make_pipeline_svg() -> str:
    result = run_pipeline(parse_pml(PANEL_PML))
    assert result.svg is not None
    return result.svg


def test_pipeline_svg_passes_every_invariant():
    results = check_svg_invariants(_make_pipeline_svg())

    assert set(SVG_INVARIANT_IDS) <= {r.id for r in results}
    assert [(r.id, r.failures) for r in results if r.status == Verdict.FAIL] == []


def test_invalid_xml():
    """Test that invalid XML fails SVG_VALID_XML invariant."""
    invalid_svg = "<svg><unclosed"

    results = check_svg_invariants(invalid_svg)

    assert len(results) == 1
    assert results[0].id == "SVG_VALID_XML"
    assert results[0].status == Verdict.FAIL
    assert "parse error" in str(results[0].failures).lower()


def test_empty_content():
    """Test that empty content fails SVG_VALID_XML."""
    results = check_svg_invariants("")

    assert len(results) >= 1
    assert results[0].id == "SVG_VALID_XML"
    assert results[0].status == Verdict.FAIL


def test_missing_viewbox():
    """Test that SVG without viewBox fails SVG_HAS_VIEWBOX."""
    svg = """<?xml version="1.0"?>
    <svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="100mm">
        <rect x="0" y="0" width="100" height="100"/>
    </svg>
    """

    results = check_svg_invariants(svg)

    viewbox_result = next(r for r in results if r.id == "SVG_HAS_VIEWBOX")
    assert viewbox_result.status == Verdict.FAIL
    assert "viewBox" in str(viewbox_result.failures)


def test_valid_viewbox():
    """Test that SVG with viewBox passes SVG_HAS_VIEWBOX."""
    svg = """<?xml version="1.0"?>
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100mm" height="100mm">
        <rect x="0" y="0" width="100" height="100"/>
    </svg>
    """

    results = check_svg_invariants(svg)

    viewbox_result = next(r for r in results if r.id == "SVG_HAS_VIEWBOX")
    assert viewbox_result.status == Verdict.PASS


def test_comma_separated_viewbox():
    """Test that SVG with comma-separated viewBox passes (valid SVG syntax)."""
    svg = """<?xml version="1.0"?>
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0,0,100,100" width="100mm" height="100mm">
        <rect x="0" y="0" width="100" height="100"/>
    </svg>
    """

    results = check_svg_invariants(svg)

    viewbox_result = next(r for r in results if r.id == "SVG_HAS_VIEWBOX")
    assert viewbox_result.status == Verdict.PASS
    assert viewbox_result.details.get("viewbox") == [0, 0, 100, 100]


def test_zero_dimensions():
    """Test that SVG with zero dimensions fails SVG_POSITIVE_DIMENSIONS."""
    svg = """<?xml version="1.0"?>
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="0mm" height="100mm">
        <rect x="0" y="0" width="100" height="100"/>
    </svg>
    """

    results = check_svg_invariants(svg)

    dim_result = next(r for r in results if r.id == "SVG_POSITIVE_DIMENSIONS")
    assert dim_result.status == Verdict.FAIL
    assert "not positive" in str(dim_result.failures).lower()


def test_invalid_path_d():
    """Test that paths with invalid d attribute fail SVG_PATHS_VALID."""
    svg = """<?xml version="1.0"?>
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100mm" height="100mm">
        <g id="PROFILE_CUTS">
            <path d="X 0 0 L 100 100"/>
        </g>
    </svg>
    """

    results = check_svg_invariants(svg)

    path_result = next(r for r in results if r.id == "SVG_PATHS_VALID")
    assert path_result.status == Verdict.FAIL
    assert "doesn't start with M" in str(path_result.failures)


def test_empty_path_d():
    """Test that paths with empty d attribute fail SVG_PATHS_VALID."""
    svg = """<?xml version="1.0"?>
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100mm" height="100mm">
        <g id="PROFILE_CUTS">
            <path d=""/>
        </g>
    </svg>
    """

    results = check_svg_invariants(svg)

    path_result = next(r for r in results if r.id == "SVG_PATHS_VALID")
    assert path_result.status == Verdict.FAIL
    assert "empty" in str(path_result.failures).lower()


def test_valid_paths():
    """Test that valid paths pass SVG_PATHS_VALID."""
    svg = """<?xml version="1.0"?>
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100mm" height="100mm">
        <g id="PROFILE_CUTS">
            <path d="M 0 0 L 100 0 L 100 100 L 0 100 Z"/>
        </g>
    </svg>
    """

    results = check_svg_invariants(svg)

    path_result = next(r for r in results if r.id == "SVG_PATHS_VALID")
    assert path_result.status == Verdict.PASS


def test_unclosed_profile():
    """Test that unclosed profile paths fail SVG_CLOSED_PROFILES."""
    svg = """<?xml version="1.0"?>
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100mm" height="100mm">
        <g id="PROFILE_CUTS">
            <path d="M 0 0 L 100 0 L 100 100 L 0 100"/>
        </g>
    </svg>
    """

    results = check_svg_invariants(svg)

    profile_result = next(r for r in results if r.id == "SVG_CLOSED_PROFILES")
    assert profile_result.status == Verdict.FAIL
    assert "not closed" in str(profile_result.failures).lower()


def test_closed_profile_path():
    """Test that closed profile paths pass SVG_CLOSED_PROFILES."""
    svg = """<?xml version="1.0"?>
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100mm" height="100mm">
        <g id="PROFILE_CUTS">
            <path d="M 0 0 L 100 0 L 100 100 L 0 100 Z"/>
        </g>
    </svg>
    """

    results = check_svg_invariants(svg)

    profile_result = next(r for r in results if r.id == "SVG_CLOSED_PROFILES")
    assert profile_result.status == Verdict.PASS


def test_profile_rect_inherently_closed():
    """Test that rect elements in profile layer count as closed."""
    svg = """<?xml version="1.0"?>
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100mm" height="100mm">
        <g id="PROFILE_CUTS">
            <rect x="10" y="10" width="80" height="80"/>
        </g>
    </svg>
    """

    results = check_svg_invariants(svg)

    profile_result = next(r for r in results if r.id == "SVG_CLOSED_PROFILES")
    assert profile_result.status == Verdict.PASS
    assert profile_result.checked == 1
    assert profile_result.passed == 1


def test_profile_polygon_inherently_closed():
    """Test that polygon elements in profile layer count as closed."""
    svg = """<?xml version="1.0"?>
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100mm" height="100mm">
        <g id="PROFILE_CUTS">
            <polygon points="10,10 90,10 90,90 10,90"/>
        </g>
    </svg>
    """

    results = check_svg_invariants(svg)

    profile_result = next(r for r in results if r.id == "SVG_CLOSED_PROFILES")
    assert profile_result.status == Verdict.PASS
    assert profile_result.checked == 1
    assert profile_result.passed == 1


def test_profile_polyline_closed():
    """Test that closed polyline in profile layer passes."""
    svg = """<?xml version="1.0"?>
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100mm" height="100mm">
        <g id="PROFILE_CUTS">
            <polyline points="10,10 90,10 90,90 10,90 10,10"/>
        </g>
    </svg>
    """

    results = check_svg_invariants(svg)

    profile_result = next(r for r in results if r.id == "SVG_CLOSED_PROFILES")
    assert profile_result.status == Verdict.PASS
    assert profile_result.checked == 1
    assert profile_result.passed == 1


def test_profile_polyline_unclosed():
    """Test that unclosed polyline in profile layer fails."""
    svg = """<?xml version="1.0"?>
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100mm" height="100mm">
        <g id="PROFILE_CUTS">
            <polyline points="10,10 90,10 90,90 10,90"/>
        </g>
    </svg>
    """

    results = check_svg_invariants(svg)

    profile_result = next(r for r in results if r.id == "SVG_CLOSED_PROFILES")
    assert profile_result.status == Verdict.FAIL
    assert "not closed" in str(profile_result.failures).lower()


def test_unclosed_pocket():
    """Test that unclosed pocket paths fail SVG_CLOSED_POCKETS."""
    svg = """<?xml version="1.0"?>
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100mm" height="100mm">
        <g id="POCKET_REGIONS">
            <path d="M 20 20 L 80 20 L 80 80 L 20 80"/>
        </g>
    </svg>
    """

    results = check_svg_invariants(svg)

    pocket_result = next(r for r in results if r.id == "SVG_CLOSED_POCKETS")
    assert pocket_result.status == Verdict.FAIL
    assert "not closed" in str(pocket_result.failures).lower()


def test_closed_pocket():
    """Test that closed pocket paths pass SVG_CLOSED_POCKETS."""
    svg = """<?xml version="1.0"?>
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100mm" height="100mm">
        <g id="POCKET_REGIONS">
            <path d="M 20 20 L 80 20 L 80 80 L 20 80 z"/>
        </g>
    </svg>
    """

    results = check_svg_invariants(svg)

    pocket_result = next(r for r in results if r.id == "SVG_CLOSED_POCKETS")
    assert pocket_result.status == Verdict.PASS


def test_empty_expected_layer():
    """Test that empty expected layers produce warning."""
    svg = """<?xml version="1.0"?>
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100mm" height="100mm">
        <g id="SHEET_OUTLINE">
        </g>
    </svg>
    """

    results = check_svg_invariants(svg, expected_layers=["SHEET_OUTLINE"])

    layer_result = next(r for r in results if r.id == "SVG_NO_EMPTY_LAYERS")
    assert layer_result.status == Verdict.WARN
    assert "empty" in str(layer_result.failures).lower()


def test_nonempty_expected_layer():
    """Test that non-empty expected layers pass."""
    svg = """<?xml version="1.0"?>
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100mm" height="100mm">
        <g id="SHEET_OUTLINE">
            <rect x="0" y="0" width="100" height="100"/>
        </g>
    </svg>
    """

    results = check_svg_invariants(svg, expected_layers=["SHEET_OUTLINE"])

    layer_result = next(r for r in results if r.id == "SVG_NO_EMPTY_LAYERS")
    assert layer_result.status == Verdict.PASS


def test_missing_expected_layer():
    """Test that missing expected layers produce warning."""
    svg = """<?xml version="1.0"?>
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100mm" height="100mm">
        <g id="PROFILE_CUTS">
            <rect x="0" y="0" width="100" height="100"/>
        </g>
    </svg>
    """

    results = check_svg_invariants(svg, expected_layers=["SHEET_OUTLINE", "PROFILE_CUTS"])

    layer_result = next(r for r in results if r.id == "SVG_NO_EMPTY_LAYERS")
    assert layer_result.status == Verdict.WARN
    assert "missing" in str(layer_result.failures).lower()
    assert layer_result.checked == 2
    assert layer_result.passed == 1


def test_no_dimensions():
    """Test that SVG without dimensions produces warning."""
    svg = """<?xml version="1.0"?>
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100mm" height="100mm">
        <g id="PROFILE_CUTS">
            <rect x="10" y="10" width="80" height="80"/>
        </g>
    </svg>
    """

    results = check_svg_invariants(svg)

    dim_result = next(r for r in results if r.id == "SVG_DIMENSIONS_PRESENT")
    assert dim_result.status == Verdict.WARN


def test_dimensions_in_layer():
    """Test that SVG with DIMENSIONS layer content passes."""
    svg = """<?xml version="1.0"?>
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100mm" height="100mm">
        <g id="DIMENSIONS">
            <line x1="0" y1="0" x2="100" y2="0"/>
            <text x="50" y="10">100mm</text>
        </g>
    </svg>
    """

    results = check_svg_invariants(svg)

    dim_result = next(r for r in results if r.id == "SVG_DIMENSIONS_PRESENT")
    assert dim_result.status == Verdict.PASS


def test_content_within_viewbox():
    """Test that content within viewBox passes."""
    svg = """<?xml version="1.0"?>
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100mm" height="100mm">
        <g id="SHEET_OUTLINE">
            <rect x="10" y="10" width="80" height="80"/>
        </g>
    </svg>
    """

    results = check_svg_invariants(svg)

    bounds_result = next(r for r in results if r.id == "SVG_BOUNDS_WITHIN_VIEWBOX")
    assert bounds_result.status == Verdict.PASS


def test_content_outside_viewbox():
    """Test that content outside viewBox fails."""
    svg = """<?xml version="1.0"?>
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100mm" height="100mm">
        <g id="SHEET_OUTLINE">
            <rect x="-10" y="10" width="80" height="80"/>
        </g>
    </svg>
    """

    results = check_svg_invariants(svg)

    bounds_result = next(r for r in results if r.id == "SVG_BOUNDS_WITHIN_VIEWBOX")
    assert bounds_result.status == Verdict.FAIL
    assert "x_min" in str(bounds_result.failures)


def test_invariant_result_to_dict():
    """Test that invariant results serialize correctly."""
    svg = """<?xml version="1.0"?>
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100mm" height="100mm">
        <rect x="0" y="0" width="100" height="100"/>
    </svg>
    """

    results = check_svg_invariants(svg)

    for r in results:
        d = r.to_dict()
        assert "invariant" in d
        assert "id" in d["invariant"]
        assert "category" in d["invariant"]
        assert "artifact" in d["invariant"]
        assert "description" in d["invariant"]
        assert "status" in d["invariant"]
        assert "details" in d["invariant"]


def test_all_invariant_ids_present():
    """Test that all expected invariant IDs are returned."""
    svg = """<?xml version="1.0"?>
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100mm" height="100mm">
        <g id="SHEET_OUTLINE">
            <rect x="0" y="0" width="100" height="100"/>
        </g>
        <g id="PROFILE_CUTS">
            <path d="M 10 10 L 90 10 L 90 90 L 10 90 Z"/>
        </g>
    </svg>
    """

    results = check_svg_invariants(svg)
    result_ids = [r.id for r in results]

    for expected_id in SVG_INVARIANT_IDS:
        assert expected_id in result_ids, f"Missing invariant: {expected_id}"
