# tests/test_cli_validate_cam.py - Tests for CAM validation CLI
#
# Tests the command-line interface for the validation pipeline.

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from cli.validate_cam import main, EXIT_PASS, EXIT_WARN, EXIT_FAIL


# Test data directories
RECIPE_DIR = Path(__file__).parent.parent / "docs" / "recipes"


def run_cli(*args: str) -> tuple[int, str, str]:
    """Run CLI with given arguments, return (exit_code, stdout, stderr)."""
    import io
    from contextlib import redirect_stdout, redirect_stderr

    stdout_capture = io.StringIO()
    stderr_capture = io.StringIO()

    with patch.object(sys, "argv", ["validate_cam"] + list(args)):
        with redirect_stdout(stdout_capture):
            with redirect_stderr(stderr_capture):
                try:
                    exit_code = main()
                except SystemExit as e:
                    exit_code = e.code if e.code is not None else 0

    return exit_code, stdout_capture.getvalue(), stderr_capture.getvalue()


# ============================================================================
# Basic CLI tests
# ============================================================================


def test_cli_no_args_fails():
    """CLI with no arguments exits with error."""
    exit_code, stdout, stderr = run_cli()
    assert exit_code != EXIT_PASS
    assert "error" in stderr.lower() or "required" in stderr.lower()
    print("PASS: test_cli_no_args_fails")


def test_cli_help():
    """CLI --help shows usage."""
    exit_code, stdout, stderr = run_cli("--help")
    # argparse uses SystemExit(0) for --help
    assert exit_code == 0
    assert "validate" in stdout.lower() or "validate" in stderr.lower()
    print("PASS: test_cli_help")


def test_cli_missing_file_fails():
    """CLI with nonexistent file exits with FAIL."""
    exit_code, stdout, stderr = run_cli("--svg", "/nonexistent/file.svg")
    assert exit_code == EXIT_FAIL
    assert "not found" in stderr.lower() or "error" in stderr.lower()
    print("PASS: test_cli_missing_file_fails")


# ============================================================================
# Recipe validation tests
# ============================================================================


def test_cli_recipe_simple_profile():
    """CLI validates recipe 01_simple_profile."""
    recipe_dir = RECIPE_DIR / "01_simple_profile"

    if not recipe_dir.exists():
        print("SKIP: test_cli_recipe_simple_profile (recipe not found)")
        return

    exit_code, stdout, stderr = run_cli("--recipe", str(recipe_dir), "--quiet")
    assert exit_code in (EXIT_PASS, EXIT_WARN), f"Unexpected exit code {exit_code}: {stderr}"

    # Verify JSON output (wrapped in validation_result)
    data = json.loads(stdout)
    result = data.get("validation_result", data)
    assert "verdict" in result
    assert "metrics" in result
    assert result["verdict"] in ("pass", "warn")
    print("PASS: test_cli_recipe_simple_profile")


def test_cli_recipe_with_summary():
    """CLI --summary outputs human-readable text."""
    recipe_dir = RECIPE_DIR / "01_simple_profile"

    if not recipe_dir.exists():
        print("SKIP: test_cli_recipe_with_summary (recipe not found)")
        return

    exit_code, stdout, stderr = run_cli("--recipe", str(recipe_dir), "--summary")
    assert exit_code in (EXIT_PASS, EXIT_WARN)

    # Summary should have human-readable text, not JSON
    assert "Validation Result:" in stdout
    assert "Metrics extracted:" in stdout or "Invariants:" in stdout
    print("PASS: test_cli_recipe_with_summary")


def test_cli_recipe_with_output_file():
    """CLI --output writes to file."""
    recipe_dir = RECIPE_DIR / "01_simple_profile"

    if not recipe_dir.exists():
        print("SKIP: test_cli_recipe_with_output_file (recipe not found)")
        return

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        output_path = f.name

    try:
        exit_code, stdout, stderr = run_cli(
            "--recipe", str(recipe_dir),
            "--output", output_path,
        )
        assert exit_code in (EXIT_PASS, EXIT_WARN)

        # Verify file was written
        assert os.path.exists(output_path)
        with open(output_path) as f:
            data = json.load(f)
        result = data.get("validation_result", data)
        assert "verdict" in result
        print("PASS: test_cli_recipe_with_output_file")
    finally:
        if os.path.exists(output_path):
            os.unlink(output_path)


# ============================================================================
# Artifact validation tests
# ============================================================================


def test_cli_svg_only():
    """CLI validates single SVG file."""
    recipe_dir = RECIPE_DIR / "01_simple_profile"
    svg_path = recipe_dir / "output" / "01_simple_profile.svg"

    if not svg_path.exists():
        print("SKIP: test_cli_svg_only (SVG not found)")
        return

    exit_code, stdout, stderr = run_cli("--svg", str(svg_path), "--quiet")
    assert exit_code in (EXIT_PASS, EXIT_WARN)

    data = json.loads(stdout)
    result = data.get("validation_result", data)
    assert "svg" in result["metrics"]
    print("PASS: test_cli_svg_only")


def test_cli_gcode_only():
    """CLI validates single G-code file."""
    recipe_dir = RECIPE_DIR / "01_simple_profile"
    output_dir = recipe_dir / "output"

    # Find any .nc file (exclude macOS metadata files starting with ._)
    nc_files = [f for f in output_dir.glob("*.nc") if not f.name.startswith("._")] if output_dir.exists() else []
    if not nc_files:
        print("SKIP: test_cli_gcode_only (G-code not found)")
        return

    exit_code, stdout, stderr = run_cli("--gcode", str(nc_files[0]), "--quiet")
    assert exit_code in (EXIT_PASS, EXIT_WARN), f"Unexpected exit {exit_code}: {stderr}"

    data = json.loads(stdout)
    result = data.get("validation_result", data)
    assert "gcode" in result["metrics"]
    print("PASS: test_cli_gcode_only")


def test_cli_multiple_gcode():
    """CLI validates multiple G-code files."""
    # Use recipe 02 which has both profile and pocket NC files
    recipe_dir = RECIPE_DIR / "02_simple_pocket"
    output_dir = recipe_dir / "output"

    # Find .nc files (exclude macOS metadata files starting with ._)
    nc_files = [f for f in output_dir.glob("*.nc") if not f.name.startswith("._")] if output_dir.exists() else []
    if len(nc_files) < 2:
        print("SKIP: test_cli_multiple_gcode (not enough G-code files)")
        return

    exit_code, stdout, stderr = run_cli(
        "--gcode", str(nc_files[0]), str(nc_files[1]),
        "--quiet"
    )
    assert exit_code in (EXIT_PASS, EXIT_WARN), f"Unexpected exit {exit_code}: {stderr}"

    data = json.loads(stdout)
    result = data.get("validation_result", data)
    assert "gcode" in result["metrics"]
    # Multiple files should be merged
    assert result["metrics"]["gcode"].get("file_count", 1) >= 2
    print("PASS: test_cli_multiple_gcode")


# ============================================================================
# Options tests
# ============================================================================


def test_cli_metrics_only():
    """CLI --metrics-only skips invariant/assertion checks."""
    recipe_dir = RECIPE_DIR / "01_simple_profile"
    svg_path = recipe_dir / "output" / "01_simple_profile.svg"

    if not svg_path.exists():
        print("SKIP: test_cli_metrics_only (SVG not found)")
        return

    exit_code, stdout, stderr = run_cli(
        "--svg", str(svg_path),
        "--metrics-only",
        "--quiet"
    )
    assert exit_code == EXIT_PASS  # No checks = pass

    data = json.loads(stdout)
    result = data.get("validation_result", data)
    # Should have metrics but no invariant results
    assert "svg" in result["metrics"]
    assert result["invariants"]["total"] == 0
    print("PASS: test_cli_metrics_only")


def test_cli_metrics_only_with_golden():
    """CLI --metrics-only disables regression even with --golden."""
    recipe_dir = RECIPE_DIR / "01_simple_profile"
    svg_path = recipe_dir / "output" / "01_simple_profile.svg"

    if not svg_path.exists():
        print("SKIP: test_cli_metrics_only_with_golden (SVG not found)")
        return

    # Create a golden file with deliberately different values
    # If regressions ran, this would cause a FAIL
    golden_metrics = {"svg": {"document": {"width_mm": 9999.0}}}

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
        json.dump(golden_metrics, f)
        golden_path = f.name

    try:
        exit_code, stdout, stderr = run_cli(
            "--svg", str(svg_path),
            "--metrics-only",
            "--golden", golden_path,
            "--quiet"
        )
        # Should PASS because --metrics-only disables all checks including regressions
        assert exit_code == EXIT_PASS, f"Expected PASS, got {exit_code}: {stderr}"

        data = json.loads(stdout)
        result = data.get("validation_result", data)
        # Regressions should not have been compared
        assert result["regressions"]["compared"] is False
        assert result["regressions"]["total"] == 0
        print("PASS: test_cli_metrics_only_with_golden")
    finally:
        if os.path.exists(golden_path):
            os.unlink(golden_path)


def test_cli_compact_json():
    """CLI --compact outputs single-line JSON."""
    recipe_dir = RECIPE_DIR / "01_simple_profile"
    svg_path = recipe_dir / "output" / "01_simple_profile.svg"

    if not svg_path.exists():
        print("SKIP: test_cli_compact_json (SVG not found)")
        return

    exit_code, stdout, stderr = run_cli(
        "--svg", str(svg_path),
        "--compact",
        "--quiet"
    )
    assert exit_code in (EXIT_PASS, EXIT_WARN)

    # Compact JSON should be single line (or few lines)
    lines = [l for l in stdout.strip().split("\n") if l.strip()]
    assert len(lines) <= 2, f"Expected compact JSON, got {len(lines)} lines"
    # Should still be valid JSON
    data = json.loads(stdout)
    result = data.get("validation_result", data)
    assert "verdict" in result
    print("PASS: test_cli_compact_json")


def test_cli_with_pml_assertions():
    """CLI --pml enables intent assertions."""
    recipe_dir = RECIPE_DIR / "01_simple_profile"
    pml_path = recipe_dir / "example.pml"
    output_dir = recipe_dir / "output"

    if not pml_path.exists() or not output_dir.exists():
        print("SKIP: test_cli_with_pml_assertions (recipe not found)")
        return

    svg_path = output_dir / "01_simple_profile.svg"
    if not svg_path.exists():
        print("SKIP: test_cli_with_pml_assertions (SVG not found)")
        return

    exit_code, stdout, stderr = run_cli(
        "--svg", str(svg_path),
        "--pml", str(pml_path),
        "--quiet"
    )
    # Note: May fail if assertions check G-code metrics which aren't provided
    # We just verify assertions are generated, not that they all pass
    assert exit_code in (EXIT_PASS, EXIT_WARN, EXIT_FAIL)

    data = json.loads(stdout)
    result = data.get("validation_result", data)
    # Should have assertions since PML provided
    assert result["assertions"]["total"] > 0
    print(f"PASS: test_cli_with_pml_assertions ({result['assertions']['total']} assertions, {result['assertions']['passed']} passed)")


# ============================================================================
# Regression tests
# ============================================================================


def test_cli_with_golden_regression():
    """CLI --golden enables regression comparison."""
    recipe_dir = RECIPE_DIR / "01_simple_profile"
    svg_path = recipe_dir / "output" / "01_simple_profile.svg"

    if not svg_path.exists():
        print("SKIP: test_cli_with_golden_regression (SVG not found)")
        return

    # Create a golden file from the same SVG (should all pass)
    from validation.metrics.svg_metrics import extract_svg_metrics_from_file
    golden_metrics = extract_svg_metrics_from_file(str(svg_path)).to_dict()

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
        json.dump(golden_metrics, f)
        golden_path = f.name

    try:
        # Use --no-assertions since we're testing regression only
        exit_code, stdout, stderr = run_cli(
            "--svg", str(svg_path),
            "--golden", golden_path,
            "--no-assertions",
            "--quiet"
        )
        assert exit_code == EXIT_PASS, f"Unexpected exit {exit_code}: {stderr}"

        data = json.loads(stdout)
        result = data.get("validation_result", data)
        assert result["regressions"]["compared"] is True
        assert result["regressions"]["total"] > 0
        print(f"PASS: test_cli_with_golden_regression ({result['regressions']['total']} comparisons)")
    finally:
        if os.path.exists(golden_path):
            os.unlink(golden_path)


def test_cli_golden_not_found():
    """CLI with nonexistent golden file fails."""
    recipe_dir = RECIPE_DIR / "01_simple_profile"
    svg_path = recipe_dir / "output" / "01_simple_profile.svg"

    if not svg_path.exists():
        print("SKIP: test_cli_golden_not_found (SVG not found)")
        return

    exit_code, stdout, stderr = run_cli(
        "--svg", str(svg_path),
        "--golden", "/nonexistent/golden.json",
    )
    assert exit_code == EXIT_FAIL
    assert "not found" in stderr.lower()
    print("PASS: test_cli_golden_not_found")


def test_cli_tolerance_override():
    """CLI --tolerance overrides default comparison tolerance."""
    recipe_dir = RECIPE_DIR / "01_simple_profile"
    svg_path = recipe_dir / "output" / "01_simple_profile.svg"

    if not svg_path.exists():
        print("SKIP: test_cli_tolerance_override (SVG not found)")
        return

    # Create golden with slightly different values
    from validation.metrics.svg_metrics import extract_svg_metrics_from_file
    golden_metrics = extract_svg_metrics_from_file(str(svg_path)).to_dict()

    # Perturb a value by 0.05%
    if "svg" in golden_metrics and "document" in golden_metrics["svg"]:
        if "width_mm" in golden_metrics["svg"]["document"]:
            golden_metrics["svg"]["document"]["width_mm"] *= 0.9995  # 0.05% change

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
        json.dump(golden_metrics, f)
        golden_path = f.name

    try:
        # With tight tolerance, should warn or fail
        exit_code1, stdout1, stderr1 = run_cli(
            "--svg", str(svg_path),
            "--golden", golden_path,
            "--tolerance", "0.01",
            "--quiet"
        )

        # With loose tolerance, should pass
        exit_code2, stdout2, stderr2 = run_cli(
            "--svg", str(svg_path),
            "--golden", golden_path,
            "--tolerance", "1.0",
            "--quiet"
        )

        # Tight tolerance should be at least as bad or worse than loose
        assert exit_code1 >= exit_code2
        print("PASS: test_cli_tolerance_override")
    finally:
        if os.path.exists(golden_path):
            os.unlink(golden_path)


# ============================================================================
# Exit code tests
# ============================================================================


def test_cli_exit_codes():
    """Verify exit code constants match plan."""
    assert EXIT_PASS == 0
    assert EXIT_WARN == 1
    assert EXIT_FAIL == 2
    print("PASS: test_cli_exit_codes")


# ============================================================================
# Test runner
# ============================================================================


if __name__ == "__main__":
    tests = [
        # Basic CLI tests
        test_cli_no_args_fails,
        test_cli_help,
        test_cli_missing_file_fails,
        # Recipe validation tests
        test_cli_recipe_simple_profile,
        test_cli_recipe_with_summary,
        test_cli_recipe_with_output_file,
        # Artifact validation tests
        test_cli_svg_only,
        test_cli_gcode_only,
        test_cli_multiple_gcode,
        # Options tests
        test_cli_metrics_only,
        test_cli_metrics_only_with_golden,
        test_cli_compact_json,
        test_cli_with_pml_assertions,
        # Regression tests
        test_cli_with_golden_regression,
        test_cli_golden_not_found,
        test_cli_tolerance_override,
        # Exit code tests
        test_cli_exit_codes,
    ]

    passed = 0
    failed = 0
    skipped = 0

    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"FAIL: {test.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"ERROR: {test.__name__}: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print(f"\n{'='*60}")
    print(f"Results: {passed} passed, {failed} failed")

    sys.exit(0 if failed == 0 else 1)
