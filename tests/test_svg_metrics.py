from __future__ import annotations

from cam.pipeline import run_pipeline
from pml import parse_pml
from validation.metrics.svg_metrics import (
    extract_svg_metrics,
    extract_svg_metrics_from_file,
)

TRAY_PML = """Sheet:
  width: 300mm
  height: 220mm
  thickness: 19mm
  material: mdf
children:
- Rect:
    id: tray
    feature:
      type: profile
      depth: through
      side: outside
    at:
      x: 150mm
      y: 110mm
      width: 240mm
      height: 160mm
- Rect:
    id: tray_well
    feature:
      type: pocket
      depth: 6mm
    at:
      x: 150mm
      y: 110mm
      width: 180mm
      height: 100mm
"""


def _make_svg() -> str:
    result = run_pipeline(parse_pml(TRAY_PML))
    assert result.svg is not None
    return result.svg


def _without_timing(metrics: dict) -> dict:
    metrics["svg"]["extraction_time_ms"] = 0
    return metrics


def test_extract_svg_metrics_from_pipeline_svg():
    metrics = extract_svg_metrics(_make_svg())

    assert metrics.document.width_mm > 0
    assert metrics.document.height_mm > 0
    assert len(metrics.document.viewbox) == 4
    assert metrics.layer_count >= 3, f"Layer count: {metrics.layer_count}"
    assert "SHEET_OUTLINE" in metrics.layer_names
    pocket_layer = metrics.layers.get("POCKET_REGIONS")
    assert pocket_layer is not None
    assert pocket_layer.rect_count >= 1, f"Pocket rects: {pocket_layer.rect_count}"
    profile_layer = metrics.layers.get("PROFILE_CUTS")
    assert profile_layer is not None
    assert profile_layer.rect_count >= 1, f"Profile rects: {profile_layer.rect_count}"
    assert metrics.paths.total_count >= 1, f"Path count: {metrics.paths.total_count}"
    assert metrics.paths.closed_count >= 1, f"Closed count: {metrics.paths.closed_count}"
    assert metrics.text.count >= 1, f"Text count: {metrics.text.count}"
    assert len(metrics.text.dimension_labels) >= 1, f"Dimensions: {metrics.text.dimension_labels}"


def test_svg_metrics_from_file_match_string(tmp_path):
    svg = _make_svg()
    svg_path = tmp_path / "tray.svg"
    svg_path.write_text(svg, encoding="utf-8")

    from_file = extract_svg_metrics_from_file(str(svg_path)).to_dict()

    assert _without_timing(from_file) == _without_timing(extract_svg_metrics(svg).to_dict())


def test_svg_metrics_empty_layers():
    """Test handling of empty layers."""
    svg_content = """<?xml version="1.0"?>
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100mm" height="100mm">
        <g id="EMPTY_LAYER"></g>
        <g id="WITH_CONTENT">
            <rect x="10" y="10" width="80" height="80"/>
        </g>
    </svg>
    """
    metrics = extract_svg_metrics(svg_content)

    assert "EMPTY_LAYER" in metrics.layer_names
    assert "WITH_CONTENT" in metrics.layer_names
    assert metrics.layers["EMPTY_LAYER"].element_count == 0
    assert metrics.layers["WITH_CONTENT"].element_count == 1


def test_svg_metrics_invalid_svg():
    """Test error handling for invalid SVG."""
    invalid_svg = "not valid xml"

    try:
        extract_svg_metrics(invalid_svg)
        raise AssertionError("Should have raised ValueError")
    except ValueError as e:
        assert "Invalid SVG" in str(e)


def test_svg_metrics_minimal_svg():
    """Test handling of minimal valid SVG."""
    minimal_svg = """<svg xmlns="http://www.w3.org/2000/svg"></svg>"""

    metrics = extract_svg_metrics(minimal_svg)

    assert metrics.document.width_mm == 0.0
    assert metrics.document.height_mm == 0.0
    assert metrics.layer_count == 0


def test_svg_metrics_with_circles():
    """Test circle metric extraction."""
    svg_content = """<?xml version="1.0"?>
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100mm" height="100mm">
        <g id="HOLES">
            <circle cx="25" cy="25" r="5"/>
            <circle cx="75" cy="25" r="5"/>
            <circle cx="50" cy="75" r="10"/>
        </g>
    </svg>
    """
    metrics = extract_svg_metrics(svg_content)

    assert metrics.circles.count == 3
    assert sorted(metrics.circles.radii_mm) == [5.0, 5.0, 10.0]


def test_svg_metrics_bounds_exclude_background():
    """Test that bounds exclude background rect (Codex review feedback)."""
    svg_content = """<?xml version="1.0"?>
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 730 930" width="730mm" height="930mm">
        <rect x="0" y="0" width="730" height="930" fill="#1a1a1a"/>
        <g id="SHEET_OUTLINE">
            <rect x="140" y="140" width="450" height="650"/>
        </g>
    </svg>
    """
    metrics = extract_svg_metrics(svg_content)

    assert metrics.bounds.x_min == 140.0, f"x_min should be 140, got {metrics.bounds.x_min}"
    assert metrics.bounds.y_min == 140.0, f"y_min should be 140, got {metrics.bounds.y_min}"
    assert metrics.bounds.x_max == 590.0, f"x_max should be 590, got {metrics.bounds.x_max}"
    assert metrics.bounds.y_max == 790.0, f"y_max should be 790, got {metrics.bounds.y_max}"
    assert metrics.rects.count == 1, f"Should have 1 rect (excluding bg), got {metrics.rects.count}"


def test_svg_metrics_dimension_text():
    """Test dimension label extraction."""
    svg_content = """<?xml version="1.0"?>
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100mm" height="100mm">
        <g id="DIMENSIONS">
            <text x="50" y="10">200.0mm</text>
            <text x="90" y="50">150.0mm</text>
        </g>
        <g id="NOTES">
            <text x="10" y="90">Sheet: 450 x 650mm</text>
        </g>
    </svg>
    """
    metrics = extract_svg_metrics(svg_content)

    assert metrics.text.count == 3
    assert "200.0mm" in metrics.text.dimension_labels
    assert "150.0mm" in metrics.text.dimension_labels
