from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from cli.mill import write_recipe_outputs
from layout_ast.layout import (
    Feature,
    Geometry,
    Item,
    LayoutAST,
    Placement,
    Sheet,
)
from pml import parse_pml
from validation.core import CAMValidationResult, Verdict
from validation.recipes import recipe_at
from validation.runner import (
    ValidationInput,
    ValidationOptions,
    _merge_gcode_metrics,
    validate,
    validate_recipe,
)

PLATE_PML = """Sheet:
  width: 220mm
  height: 160mm
  thickness: 19mm
  material: mdf
children:
- Rect:
    id: plate
    feature:
      type: profile
      depth: through
      side: outside
    at:
      x: 110mm
      y: 80mm
      width: 180mm
      height: 120mm
- Rect:
    id: plate_recess
    feature:
      type: pocket
      depth: 3mm
    at:
      x: 110mm
      y: 80mm
      width: 100mm
      height: 60mm
- Circle:
    id: plate_hole
    diameter: 6mm
    feature:
      type: hole
      depth: 10mm
    at:
      x: 40mm
      y: 40mm
"""

BACK_FACE_DOOR_PML = """Sheet:
  width: 440mm
  height: 640mm
  thickness: 19mm
  material: mdf
  min_web: 4mm
children:
- Rect:
    id: door
    at:
      x: 220mm
      y: 320mm
      width: 400mm
      height: 600mm
    children:
    - Profile:
        side: outside
        depth: through
- Circle:
    id: hinge_cup
    diameter: 35mm
    feature:
      type: pocket
      depth: 12.5mm
      face: back
    at:
      x: 42.5mm
      y: 120mm
- Circle:
    id: hinge_pilot
    diameter: 3mm
    feature:
      type: hole
      depth: 10mm
      face: back
    at:
      x: 33mm
      y: 97.5mm
"""


def _make_recipe(tmp_path: Path, pml: str) -> Path:
    recipe_dir = tmp_path / "recipe"
    recipe_dir.mkdir()
    source = recipe_dir / "example.pml.yml"
    source.write_text(pml)
    recipe = recipe_at(recipe_dir)
    assert recipe is not None
    write_recipe_outputs(recipe, recipe_dir / "output")
    return recipe_dir


def test_validate_recipe_extracts_metrics_and_passes_invariants(tmp_path: Path):
    result = validate_recipe(_make_recipe(tmp_path, PLATE_PML))

    assert "svg" in result.metrics
    assert "gcode" in result.metrics
    assert result.invariants.total > 0
    assert result.invariants.failed == 0


def test_validate_recipe_with_ast_passes_assertions(tmp_path: Path):
    result = validate_recipe(_make_recipe(tmp_path, PLATE_PML), ast=parse_pml(PLATE_PML))

    assert result.assertions.total > 0
    assert result.assertions.failed == 0


def make_simple_profile_ast() -> LayoutAST:
    return LayoutAST(
        sheet=Sheet(width_mm=450.0, height_mm=650.0, thickness_mm=19.0, margin_mm=0.0),
        items=(
            Item(
                kind="shape",
                type="Rect",
                geometry=Geometry(data={"w_mm": 200.0, "h_mm": 150.0}),
                placement=Placement(center_xy_mm=(225.0, 325.0)),
                feature=Feature(type="profile", depth_mm=0.0, is_through=True, side="outside"),
                shape_id="part",
            ),
        ),
    )


def make_minimal_svg() -> str:
    return """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 450 650" width="450mm" height="650mm">
        <rect x="0" y="0" width="450" height="650" fill="#1a1a1a"/>
        <g id="SHEET_OUTLINE"><rect x="0" y="0" width="450" height="650"/></g>
        <g id="PROFILE_CUTS"><rect x="125" y="250" width="200" height="150"/></g>
        <g id="POCKET_REGIONS"/>
        <g id="HOLES"/>
        <g id="DIMENSIONS"><text x="10" y="10">200mm</text></g>
        <g id="NOTES"><text x="10" y="20">Sheet: 450 x 650 x 19mm</text></g>
    </svg>"""


def test_validation_input_defaults():
    inputs = ValidationInput()
    assert inputs.source_file is None
    assert inputs.ast is None
    assert inputs.svg_path is None
    assert inputs.gcode_paths == []


def test_validation_options_defaults():
    options = ValidationOptions()
    assert options.extract_metrics is True
    assert options.check_invariants is True
    assert options.check_assertions is True
    assert options.check_regressions is True


def test_validate_with_svg_content():
    inputs = ValidationInput(
        svg_content=make_minimal_svg(),
    )
    options = ValidationOptions(
        check_assertions=False,
        check_regressions=False,
    )

    result = validate(inputs, options)

    assert isinstance(result, CAMValidationResult)
    assert "svg" in result.metrics
    assert result.invariants.total > 0


def test_validate_with_ast():
    inputs = ValidationInput(
        svg_content=make_minimal_svg(),
        ast=make_simple_profile_ast(),
    )
    options = ValidationOptions(
        check_regressions=False,
    )

    result = validate(inputs, options)

    assert result.assertions.total > 0


def test_validate_computes_verdict():
    inputs = ValidationInput(
        svg_content=make_minimal_svg(),
    )
    options = ValidationOptions(
        check_assertions=False,
        check_regressions=False,
    )

    result = validate(inputs, options)

    assert result.verdict in [Verdict.PASS, Verdict.WARN, Verdict.FAIL]
    assert result.verdict_reason != ""
    assert result.execution_time_ms > 0


def test_validate_output_json_serializable():
    inputs = ValidationInput(
        svg_content=make_minimal_svg(),
    )
    options = ValidationOptions(
        check_assertions=False,
        check_regressions=False,
    )

    result = validate(inputs, options)
    json_str = result.to_json()

    parsed = json.loads(json_str)
    assert "validation_result" in parsed
    assert parsed["validation_result"]["verdict"] in ["pass", "warn", "fail"]


def test_validate_with_golden_metrics():
    inputs = ValidationInput(
        svg_content=make_minimal_svg(),
        golden_metrics={"svg": {"document": {"width_mm": 450.0}}},
        golden_file="/path/to/golden.json",
    )
    options = ValidationOptions(
        check_assertions=False,
    )

    result = validate(inputs, options)

    assert result.regressions.compared is True
    assert result.regressions.golden_file == "/path/to/golden.json"
    assert result.regressions.total > 0


def test_validate_empty_inputs():
    inputs = ValidationInput()
    options = ValidationOptions(
        check_assertions=False,
        check_regressions=False,
    )

    result = validate(inputs, options)

    assert isinstance(result, CAMValidationResult)
    assert result.verdict == Verdict.PASS


def test_validate_with_gcode_content():
    gcode_content = """(begin)
G90
G21
G17
M3 S14000
G0 X0 Y0 Z6.0
G1 Z-1.0 F300.0
G1 X100.0 Y0 F900.0
G1 X100.0 Y100.0
G1 X0 Y100.0
G1 X0 Y0
G0 Z6.0
M5
M2
(end)
"""
    inputs = ValidationInput(
        gcode_content=[gcode_content],
    )
    options = ValidationOptions(
        check_assertions=False,
        check_regressions=False,
    )

    result = validate(inputs, options)

    assert isinstance(result, CAMValidationResult)
    assert "gcode" in result.metrics
    gcode_invariants = [i for i in result.invariants.results if i.artifact == "gcode"]
    assert len(gcode_invariants) > 0


def test_merge_gcode_metrics_empty():
    result = _merge_gcode_metrics([])
    assert result == {}


def test_merge_gcode_metrics_single():
    class MockGCodeMetrics:
        def to_dict(self):
            return {"gcode": {"summary": {"total_lines": 100}}}

    result = _merge_gcode_metrics([MockGCodeMetrics()])  # type: ignore[list-item]
    assert result["summary"]["total_lines"] == 100


def test_merge_gcode_metrics_sums_counts():
    class MockGCodeMetrics:
        def __init__(self, total_lines):
            self._total_lines = total_lines

        def to_dict(self):
            return {
                "gcode": {
                    "summary": {"total_lines": self._total_lines},
                    "motion": {"g1_count": self._total_lines // 2},
                }
            }

    metrics_list: list[Any] = [MockGCodeMetrics(100), MockGCodeMetrics(200)]
    result = _merge_gcode_metrics(metrics_list)

    assert result["summary"]["total_lines"] == 300
    assert result["motion"]["g1_count"] == 150
    assert result["file_count"] == 2


def test_output_format_matches_schema():
    inputs = ValidationInput(
        source_file="test.pml.yml",
        svg_content=make_minimal_svg(),
    )
    options = ValidationOptions(
        check_assertions=False,
        check_regressions=False,
    )

    result = validate(inputs, options)
    output = result.to_dict()

    assert "validation_result" in output
    vr = output["validation_result"]

    assert "version" in vr
    assert "timestamp" in vr
    assert "input_file" in vr
    assert "verdict" in vr
    assert "metrics" in vr
    assert "invariants" in vr
    assert "assertions" in vr
    assert "regressions" in vr
    assert "summary" in vr

    inv = vr["invariants"]
    assert "total" in inv
    assert "passed" in inv
    assert "warned" in inv
    assert "failed" in inv
    assert "results" in inv

    assertions = vr["assertions"]
    assert "total" in assertions
    assert "passed" in assertions
    assert "failed" in assertions
    assert "results" in assertions

    reg = vr["regressions"]
    assert "compared" in reg
    assert "golden_file" in reg
    assert "total" in reg
    assert "within_tolerance" in reg
    assert "exceeded_tolerance" in reg
    assert "results" in reg

    summary = vr["summary"]
    assert "verdict_reason" in summary
    assert "execution_time_ms" in summary


def test_output_verdict_values():
    inputs = ValidationInput(
        svg_content=make_minimal_svg(),
    )
    options = ValidationOptions(
        check_assertions=False,
        check_regressions=False,
    )

    result = validate(inputs, options)
    output = result.to_dict()

    verdict = output["validation_result"]["verdict"]
    assert verdict in ["pass", "warn", "fail"]
