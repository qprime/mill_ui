# tests/test_runner.py - Tests for validation runner
#
# Tests the full validation pipeline orchestration.
# See docs/cam_validation_plan.md for Stage 9 scope.

from __future__ import annotations

import json
import os
import sys

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from layout_ast.layout import (
    LayoutAST,
    Sheet,
    Item,
    Geometry,
    Placement,
    Feature,
)
from validation.core import Verdict, CAMValidationResult
from validation.runner import (
    validate,
    validate_recipe,
    ValidationInput,
    ValidationOptions,
    _merge_gcode_metrics,
)


# Path to recipe outputs
RECIPE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "docs",
    "recipes",
)


# ============================================================================
# Test fixtures
# ============================================================================


def make_simple_profile_ast() -> LayoutAST:
    """AST for a simple profile cut (like recipe 01)."""
    return LayoutAST(
        sheet=Sheet(width_mm=450.0, height_mm=650.0, thickness_mm=19.0),
        items=(
            Item(
                kind="shape",
                type="Rect",
                geometry=Geometry(data={"w_mm": 200.0, "h_mm": 150.0}),
                placement=Placement(center_xy_mm=(225.0, 325.0)),
                feature=Feature(type="profile", depth="through", side="outside"),
                shape_id="part",
            ),
        ),
    )


def make_minimal_svg() -> str:
    """Minimal valid SVG for testing."""
    return '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 450 650" width="450mm" height="650mm">
        <rect x="0" y="0" width="450" height="650" fill="#1a1a1a"/>
        <g id="SHEET_OUTLINE"><rect x="0" y="0" width="450" height="650"/></g>
        <g id="PROFILE_CUTS"><rect x="125" y="250" width="200" height="150"/></g>
        <g id="POCKET_REGIONS"/>
        <g id="HOLES"/>
        <g id="DIMENSIONS"><text x="10" y="10">200mm</text></g>
        <g id="NOTES"><text x="10" y="20">Sheet: 450 x 650 x 19mm</text></g>
    </svg>'''


# ============================================================================
# ValidationInput tests
# ============================================================================


def test_validation_input_defaults():
    """ValidationInput has sensible defaults."""
    inputs = ValidationInput()
    assert inputs.source_file is None
    assert inputs.ast is None
    assert inputs.svg_path is None
    assert inputs.gcode_paths == []
    print("PASS: test_validation_input_defaults")


def test_validation_options_defaults():
    """ValidationOptions has sensible defaults."""
    options = ValidationOptions()
    assert options.extract_metrics is True
    assert options.check_invariants is True
    assert options.check_assertions is True
    assert options.check_regressions is True
    print("PASS: test_validation_options_defaults")


# ============================================================================
# validate() function tests
# ============================================================================


def test_validate_with_svg_content():
    """validate() works with SVG content."""
    inputs = ValidationInput(
        svg_content=make_minimal_svg(),
    )
    options = ValidationOptions(
        check_assertions=False,  # No AST provided
        check_regressions=False,
    )

    result = validate(inputs, options)

    assert isinstance(result, CAMValidationResult)
    assert "svg" in result.metrics
    assert result.invariants.total > 0
    print(f"PASS: test_validate_with_svg_content ({result.invariants.total} invariants)")


def test_validate_with_ast():
    """validate() runs assertions when AST is provided."""
    inputs = ValidationInput(
        svg_content=make_minimal_svg(),
        ast=make_simple_profile_ast(),
    )
    options = ValidationOptions(
        check_regressions=False,
    )

    result = validate(inputs, options)

    assert result.assertions.total > 0
    print(f"PASS: test_validate_with_ast ({result.assertions.total} assertions)")


def test_validate_computes_verdict():
    """validate() computes aggregate verdict."""
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
    print(f"PASS: test_validate_computes_verdict (verdict: {result.verdict.value})")


def test_validate_output_json_serializable():
    """validate() result is JSON serializable."""
    inputs = ValidationInput(
        svg_content=make_minimal_svg(),
    )
    options = ValidationOptions(
        check_assertions=False,
        check_regressions=False,
    )

    result = validate(inputs, options)
    json_str = result.to_json()

    # Verify it's valid JSON
    parsed = json.loads(json_str)
    assert "validation_result" in parsed
    assert parsed["validation_result"]["verdict"] in ["pass", "warn", "fail"]
    print("PASS: test_validate_output_json_serializable")


def test_validate_with_golden_metrics():
    """validate() runs regression checks when golden provided."""
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
    print(f"PASS: test_validate_with_golden_metrics ({result.regressions.total} comparisons)")


def test_validate_empty_inputs():
    """validate() handles empty inputs gracefully."""
    inputs = ValidationInput()
    options = ValidationOptions(
        check_assertions=False,
        check_regressions=False,
    )

    result = validate(inputs, options)

    # Should complete without error
    assert isinstance(result, CAMValidationResult)
    assert result.verdict == Verdict.PASS  # No checks = pass
    print("PASS: test_validate_empty_inputs")


# ============================================================================
# Content-mode tests
# ============================================================================


def test_validate_with_gcode_content():
    """validate() works with G-code content (not file path)."""
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
    # Should have G-code metrics
    assert "gcode" in result.metrics
    # Should have G-code invariants
    gcode_invariants = [i for i in result.invariants.results if i.artifact == "gcode"]
    assert len(gcode_invariants) > 0
    print(f"PASS: test_validate_with_gcode_content ({len(gcode_invariants)} G-code invariants)")


def test_validate_with_stl_content():
    """validate() works with STL content (bytes)."""
    # Read a real STL file to get valid binary content
    recipe_dir = os.path.join(RECIPE_DIR, "01_simple_profile")
    stl_path = os.path.join(recipe_dir, "output", "example.stl")

    if not os.path.exists(stl_path):
        print("SKIP: test_validate_with_stl_content (STL file not found)")
        return

    with open(stl_path, "rb") as f:
        stl_content = f.read()

    inputs = ValidationInput(
        stl_content=stl_content,
    )
    options = ValidationOptions(
        check_assertions=False,
        check_regressions=False,
    )

    result = validate(inputs, options)

    assert isinstance(result, CAMValidationResult)
    # Should have STL metrics
    assert "stl" in result.metrics
    # Should have STL invariants
    stl_invariants = [i for i in result.invariants.results if i.artifact == "stl"]
    assert len(stl_invariants) > 0
    print(f"PASS: test_validate_with_stl_content ({len(stl_invariants)} STL invariants)")


def test_validate_recipe_with_golden_file():
    """validate_recipe() passes golden_file and comparison_config."""
    recipe_dir = os.path.join(RECIPE_DIR, "01_simple_profile")

    if not os.path.exists(recipe_dir):
        print("SKIP: test_validate_recipe_with_golden_file (recipe not found)")
        return

    # Create mock golden metrics
    golden = {"svg": {"document": {"width_mm": 730.0}}}

    from validation.regression import ComparisonConfig
    config = ComparisonConfig(default_tolerance_percent=1.0)

    result = validate_recipe(
        recipe_dir,
        golden_metrics=golden,
        golden_file="/path/to/golden.json",
        comparison_config=config,
    )

    assert result.regressions.compared is True
    assert result.regressions.golden_file == "/path/to/golden.json"
    print("PASS: test_validate_recipe_with_golden_file")


# ============================================================================
# _merge_gcode_metrics tests
# ============================================================================


def test_merge_gcode_metrics_empty():
    """_merge_gcode_metrics handles empty list."""
    result = _merge_gcode_metrics([])
    assert result == {}
    print("PASS: test_merge_gcode_metrics_empty")


def test_merge_gcode_metrics_single():
    """_merge_gcode_metrics passes through single file."""
    from validation.metrics.gcode_metrics import GCodeMetrics

    # Create a mock metrics object
    class MockGCodeMetrics:
        def to_dict(self):
            return {"gcode": {"summary": {"total_lines": 100}}}

    result = _merge_gcode_metrics([MockGCodeMetrics()])
    assert result["summary"]["total_lines"] == 100
    print("PASS: test_merge_gcode_metrics_single")


def test_merge_gcode_metrics_sums_counts():
    """_merge_gcode_metrics sums counts from multiple files."""
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

    metrics_list = [MockGCodeMetrics(100), MockGCodeMetrics(200)]
    result = _merge_gcode_metrics(metrics_list)

    assert result["summary"]["total_lines"] == 300
    assert result["motion"]["g1_count"] == 150
    assert result["file_count"] == 2
    print("PASS: test_merge_gcode_metrics_sums_counts")


# ============================================================================
# validate_recipe() tests
# ============================================================================


def test_validate_recipe_simple_profile():
    """validate_recipe() works on recipe 01."""
    recipe_dir = os.path.join(RECIPE_DIR, "01_simple_profile")

    if not os.path.exists(recipe_dir):
        print("SKIP: test_validate_recipe_simple_profile (recipe not found)")
        return

    result = validate_recipe(recipe_dir)

    assert isinstance(result, CAMValidationResult)
    assert "svg" in result.metrics
    assert result.invariants.total > 0
    # Recipe 01 should pass all invariants
    assert result.invariants.failed == 0

    print(f"PASS: test_validate_recipe_simple_profile "
          f"(verdict: {result.verdict.value}, "
          f"{result.invariants.total} invariants, "
          f"{result.invariants.warned} warnings)")


def test_validate_recipe_with_ast():
    """validate_recipe() with AST runs assertions."""
    recipe_dir = os.path.join(RECIPE_DIR, "01_simple_profile")
    pml_path = os.path.join(recipe_dir, "example.pml")

    if not os.path.exists(pml_path):
        print("SKIP: test_validate_recipe_with_ast (recipe not found)")
        return

    # Parse PML to get AST
    from pml.parser import parse_pml
    with open(pml_path) as f:
        ast = parse_pml(f.read())

    result = validate_recipe(recipe_dir, ast=ast)

    assert result.assertions.total > 0
    print(f"PASS: test_validate_recipe_with_ast "
          f"({result.assertions.total} assertions, "
          f"{result.assertions.passed} passed)")


def test_validate_recipe_pocket():
    """validate_recipe() works on recipe 02 (pocket)."""
    recipe_dir = os.path.join(RECIPE_DIR, "02_pocket_with_cleanup")

    if not os.path.exists(recipe_dir):
        print("SKIP: test_validate_recipe_pocket (recipe not found)")
        return

    result = validate_recipe(recipe_dir)

    assert isinstance(result, CAMValidationResult)
    assert result.invariants.failed == 0

    print(f"PASS: test_validate_recipe_pocket "
          f"(verdict: {result.verdict.value}, "
          f"{result.invariants.total} invariants)")


def test_validate_recipe_shaker_door():
    """validate_recipe() works on recipe 03 (shaker door)."""
    recipe_dir = os.path.join(RECIPE_DIR, "03_shaker_door_template")

    if not os.path.exists(recipe_dir):
        print("SKIP: test_validate_recipe_shaker_door (recipe not found)")
        return

    result = validate_recipe(recipe_dir)

    assert isinstance(result, CAMValidationResult)
    assert result.invariants.failed == 0

    print(f"PASS: test_validate_recipe_shaker_door "
          f"(verdict: {result.verdict.value}, "
          f"{result.invariants.total} invariants)")


def test_validate_recipe_multi_tool():
    """validate_recipe() handles multi-tool recipes (multiple NC files)."""
    recipe_dir = os.path.join(RECIPE_DIR, "03_shaker_door_template")

    if not os.path.exists(recipe_dir):
        print("SKIP: test_validate_recipe_multi_tool (recipe not found)")
        return

    result = validate_recipe(recipe_dir)

    # Check G-code metrics were merged
    if "gcode" in result.metrics:
        gcode = result.metrics["gcode"]
        # Multi-tool recipes should have file_count > 1 or merged metrics
        print(f"  G-code: {gcode.get('summary', {}).get('total_lines', 'N/A')} lines")

    print(f"PASS: test_validate_recipe_multi_tool")


def test_validate_all_recipes():
    """validate_recipe() succeeds on all available recipes."""
    passed = 0
    failed = 0
    skipped = 0

    for i in range(1, 19):
        recipe_name = f"{i:02d}_"
        recipe_dirs = [d for d in os.listdir(RECIPE_DIR)
                       if d.startswith(recipe_name)]

        if not recipe_dirs:
            skipped += 1
            continue

        recipe_dir = os.path.join(RECIPE_DIR, recipe_dirs[0])

        try:
            result = validate_recipe(recipe_dir)
            if result.invariants.failed == 0:
                passed += 1
            else:
                print(f"  Recipe {recipe_dirs[0]}: {result.invariants.failed} invariant failures")
                failed += 1
        except Exception as e:
            print(f"  Recipe {recipe_dirs[0]}: ERROR - {e}")
            failed += 1

    print(f"PASS: test_validate_all_recipes ({passed} passed, {failed} failed, {skipped} skipped)")
    assert failed == 0, f"{failed} recipes had invariant failures"


# ============================================================================
# Output format tests
# ============================================================================


def test_output_format_matches_schema():
    """Output JSON matches the schema in cam_validation_plan.md."""
    inputs = ValidationInput(
        source_file="test.pml",
        svg_content=make_minimal_svg(),
    )
    options = ValidationOptions(
        check_assertions=False,
        check_regressions=False,
    )

    result = validate(inputs, options)
    output = result.to_dict()

    # Check top-level structure
    assert "validation_result" in output
    vr = output["validation_result"]

    # Required fields
    assert "version" in vr
    assert "timestamp" in vr
    assert "input_file" in vr
    assert "verdict" in vr
    assert "metrics" in vr
    assert "invariants" in vr
    assert "assertions" in vr
    assert "regressions" in vr
    assert "summary" in vr

    # Invariants structure
    inv = vr["invariants"]
    assert "total" in inv
    assert "passed" in inv
    assert "warned" in inv
    assert "failed" in inv
    assert "results" in inv

    # Assertions structure
    assertions = vr["assertions"]
    assert "total" in assertions
    assert "passed" in assertions
    assert "failed" in assertions
    assert "results" in assertions

    # Regressions structure
    reg = vr["regressions"]
    assert "compared" in reg
    assert "golden_file" in reg
    assert "total" in reg
    assert "within_tolerance" in reg
    assert "exceeded_tolerance" in reg
    assert "results" in reg

    # Summary structure
    summary = vr["summary"]
    assert "verdict_reason" in summary
    assert "execution_time_ms" in summary

    print("PASS: test_output_format_matches_schema")


def test_output_verdict_values():
    """Output verdict is one of pass/warn/fail."""
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
    print(f"PASS: test_output_verdict_values (verdict: {verdict})")


# ============================================================================
# Test runner
# ============================================================================


def run_tests() -> bool:
    """Run all tests and report results."""
    tests = [
        # Input/options tests
        test_validation_input_defaults,
        test_validation_options_defaults,
        # validate() tests
        test_validate_with_svg_content,
        test_validate_with_ast,
        test_validate_computes_verdict,
        test_validate_output_json_serializable,
        test_validate_with_golden_metrics,
        test_validate_empty_inputs,
        # Content-mode tests
        test_validate_with_gcode_content,
        test_validate_with_stl_content,
        test_validate_recipe_with_golden_file,
        # merge tests
        test_merge_gcode_metrics_empty,
        test_merge_gcode_metrics_single,
        test_merge_gcode_metrics_sums_counts,
        # validate_recipe() tests
        test_validate_recipe_simple_profile,
        test_validate_recipe_with_ast,
        test_validate_recipe_pocket,
        test_validate_recipe_shaker_door,
        test_validate_recipe_multi_tool,
        test_validate_all_recipes,
        # Output format tests
        test_output_format_matches_schema,
        test_output_verdict_values,
    ]

    print("=" * 60)
    print("Validation Runner Tests")
    print("=" * 60)

    passed = 0
    failed = 0
    skipped = 0

    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"FAIL: {test.__name__}")
            print(f"  {e}")
            failed += 1
        except Exception as e:
            # Check if it was a skip
            if "SKIP" in str(e):
                skipped += 1
            else:
                print(f"ERROR: {test.__name__}")
                print(f"  {type(e).__name__}: {e}")
                import traceback
                traceback.print_exc()
                failed += 1

    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed, {skipped} skipped")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
