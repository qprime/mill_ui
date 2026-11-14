from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from cli.mill import write_recipe_outputs
from cli.validate_cam import EXIT_FAIL, EXIT_PASS, EXIT_WARN, main
from validation.recipes import recipe_at

FRAME_PML = """Sheet:
  width: 200mm
  height: 150mm
  thickness: 19mm
  material: mdf
children:
- Rect:
    id: frame
    feature:
      type: profile
      depth: through
      side: outside
    at:
      x: 100mm
      y: 75mm
      width: 160mm
      height: 110mm
- Rect:
    id: frame_rebate
    feature:
      type: pocket
      depth: 4mm
    at:
      x: 100mm
      y: 75mm
      width: 80mm
      height: 50mm
- Circle:
    id: frame_hole
    diameter: 6mm
    feature:
      type: hole
      depth: 8mm
    at:
      x: 35mm
      y: 35mm
"""


def _make_recipe(tmp_path: Path) -> Path:
    recipe_dir = tmp_path / "frame"
    recipe_dir.mkdir()
    source = recipe_dir / "example.pml.yml"
    source.write_text(FRAME_PML)
    recipe = recipe_at(recipe_dir)
    assert recipe is not None
    write_recipe_outputs(recipe, recipe_dir / "output")
    return recipe_dir


def _make_svg(tmp_path: Path) -> Path:
    return _make_recipe(tmp_path) / "output" / "frame.svg"


def _write_baseline(tmp_path: Path, metrics: dict) -> Path:
    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text(json.dumps(metrics))
    return baseline_path


def run_cli(*args: str) -> tuple[int, str, str]:
    import io
    from contextlib import redirect_stderr, redirect_stdout

    stdout_capture = io.StringIO()
    stderr_capture = io.StringIO()

    with (
        patch.object(sys, "argv", ["validate_cam", *args]),
        redirect_stdout(stdout_capture),
        redirect_stderr(stderr_capture),
    ):
        try:
            exit_code = main()
        except SystemExit as e:
            exit_code = e.code if isinstance(e.code, int) else 0

    return exit_code, stdout_capture.getvalue(), stderr_capture.getvalue()


def test_cli_no_args_fails():
    """CLI with no arguments exits with error."""
    exit_code, _stdout, stderr = run_cli()
    assert exit_code != EXIT_PASS
    assert "error" in stderr.lower() or "required" in stderr.lower()


def test_cli_help():
    """CLI --help shows usage."""
    exit_code, stdout, stderr = run_cli("--help")
    assert exit_code == 0
    assert "validate" in stdout.lower() or "validate" in stderr.lower()


def test_cli_missing_file_fails():
    """CLI with nonexistent file exits with FAIL."""
    exit_code, _stdout, stderr = run_cli("--svg", "/nonexistent/file.svg")
    assert exit_code == EXIT_FAIL
    assert "not found" in stderr.lower() or "error" in stderr.lower()


def test_cli_recipe(tmp_path: Path):
    """CLI validates a recipe directory."""
    exit_code, stdout, stderr = run_cli("--recipe", str(_make_recipe(tmp_path)), "--quiet")
    assert exit_code in (EXIT_PASS, EXIT_WARN), f"Unexpected exit code {exit_code}: {stderr}"

    data = json.loads(stdout)
    result = data.get("validation_result", data)
    assert "verdict" in result
    assert "metrics" in result
    assert result["verdict"] in ("pass", "warn")


def test_cli_recipe_with_summary(tmp_path: Path):
    """CLI --summary outputs human-readable text."""
    exit_code, stdout, _stderr = run_cli("--recipe", str(_make_recipe(tmp_path)), "--summary")
    assert exit_code in (EXIT_PASS, EXIT_WARN)

    assert "Validation Result:" in stdout
    assert "Metrics extracted:" in stdout or "Invariants:" in stdout


def test_cli_recipe_with_output_file(tmp_path: Path):
    """CLI --output writes to file."""
    output_path = tmp_path / "result.json"

    exit_code, _stdout, _stderr = run_cli("--recipe", str(_make_recipe(tmp_path)), "--output", str(output_path))
    assert exit_code in (EXIT_PASS, EXIT_WARN)

    data = json.loads(output_path.read_text())
    result = data.get("validation_result", data)
    assert "verdict" in result


def test_cli_svg_only(tmp_path: Path):
    """CLI validates single SVG file."""
    exit_code, stdout, _stderr = run_cli("--svg", str(_make_svg(tmp_path)), "--quiet")
    assert exit_code in (EXIT_PASS, EXIT_WARN)

    data = json.loads(stdout)
    result = data.get("validation_result", data)
    assert "svg" in result["metrics"]


def test_cli_gcode_only(tmp_path: Path):
    """CLI validates single G-code file."""
    nc_files = sorted((_make_recipe(tmp_path) / "output").glob("*.nc"))

    exit_code, stdout, stderr = run_cli("--gcode", str(nc_files[0]), "--quiet")
    assert exit_code in (EXIT_PASS, EXIT_WARN), f"Unexpected exit {exit_code}: {stderr}"

    data = json.loads(stdout)
    result = data.get("validation_result", data)
    assert "gcode" in result["metrics"]


def test_cli_multiple_gcode(tmp_path: Path):
    """CLI validates multiple G-code files."""
    nc_files = sorted((_make_recipe(tmp_path) / "output").glob("*.nc"))
    assert len(nc_files) >= 2, f"expected several G-code files, found {len(nc_files)}"

    exit_code, stdout, stderr = run_cli("--gcode", str(nc_files[0]), str(nc_files[1]), "--quiet")
    assert exit_code in (EXIT_PASS, EXIT_WARN), f"Unexpected exit {exit_code}: {stderr}"

    data = json.loads(stdout)
    result = data.get("validation_result", data)
    assert "gcode" in result["metrics"]
    assert result["metrics"]["gcode"].get("file_count", 1) >= 2


def test_cli_metrics_only(tmp_path: Path):
    """CLI --metrics-only skips invariant/assertion checks."""
    exit_code, stdout, _stderr = run_cli("--svg", str(_make_svg(tmp_path)), "--metrics-only", "--quiet")
    assert exit_code == EXIT_PASS

    data = json.loads(stdout)
    result = data.get("validation_result", data)
    assert "svg" in result["metrics"]
    assert result["invariants"]["total"] == 0


def test_cli_metrics_only_with_golden(tmp_path: Path):
    """CLI --metrics-only disables regression even with --golden."""
    svg_path = _make_svg(tmp_path)
    golden_path = _write_baseline(tmp_path, {"svg": {"document": {"width_mm": 9999.0}}})

    exit_code, stdout, stderr = run_cli(
        "--svg", str(svg_path), "--metrics-only", "--golden", str(golden_path), "--quiet"
    )
    assert exit_code == EXIT_PASS, f"Expected PASS, got {exit_code}: {stderr}"

    data = json.loads(stdout)
    result = data.get("validation_result", data)
    assert result["regressions"]["compared"] is False
    assert result["regressions"]["total"] == 0


def test_cli_compact_json(tmp_path: Path):
    """CLI --compact outputs single-line JSON."""
    exit_code, stdout, _stderr = run_cli("--svg", str(_make_svg(tmp_path)), "--compact", "--quiet")
    assert exit_code in (EXIT_PASS, EXIT_WARN)

    lines = [line for line in stdout.strip().split("\n") if line.strip()]
    assert len(lines) <= 2, f"Expected compact JSON, got {len(lines)} lines"
    data = json.loads(stdout)
    result = data.get("validation_result", data)
    assert "verdict" in result


def test_cli_with_pml_assertions(tmp_path: Path):
    """CLI --pml enables intent assertions."""
    recipe_dir = _make_recipe(tmp_path)
    svg_path = recipe_dir / "output" / "frame.svg"
    pml_path = recipe_dir / "example.pml.yml"

    exit_code, stdout, _stderr = run_cli("--svg", str(svg_path), "--pml", str(pml_path), "--quiet")
    assert exit_code in (EXIT_PASS, EXIT_WARN, EXIT_FAIL)

    data = json.loads(stdout)
    result = data.get("validation_result", data)
    assert result["assertions"]["total"] > 0


def test_cli_with_golden_regression(tmp_path: Path):
    """CLI --golden enables regression comparison."""
    from validation.metrics.svg_metrics import extract_svg_metrics_from_file

    svg_path = _make_svg(tmp_path)
    golden_path = _write_baseline(tmp_path, extract_svg_metrics_from_file(str(svg_path)).to_dict())

    exit_code, stdout, stderr = run_cli(
        "--svg", str(svg_path), "--golden", str(golden_path), "--no-assertions", "--quiet"
    )
    assert exit_code == EXIT_PASS, f"Unexpected exit {exit_code}: {stderr}"

    data = json.loads(stdout)
    result = data.get("validation_result", data)
    assert result["regressions"]["compared"] is True
    assert result["regressions"]["total"] > 0


def test_cli_golden_not_found(tmp_path: Path):
    """CLI with nonexistent golden file fails."""
    exit_code, _stdout, stderr = run_cli("--svg", str(_make_svg(tmp_path)), "--golden", "/nonexistent/golden.json")
    assert exit_code == EXIT_FAIL
    assert "not found" in stderr.lower()


def test_cli_tolerance_override(tmp_path: Path):
    """CLI --tolerance overrides default comparison tolerance."""
    from validation.metrics.svg_metrics import extract_svg_metrics_from_file

    svg_path = _make_svg(tmp_path)
    golden_metrics = extract_svg_metrics_from_file(str(svg_path)).to_dict()
    golden_metrics["svg"]["document"]["width_mm"] *= 0.9995
    golden_path = _write_baseline(tmp_path, golden_metrics)

    exit_code1, _stdout1, _stderr1 = run_cli(
        "--svg", str(svg_path), "--golden", str(golden_path), "--tolerance", "0.01", "--quiet"
    )
    exit_code2, _stdout2, _stderr2 = run_cli(
        "--svg", str(svg_path), "--golden", str(golden_path), "--tolerance", "1.0", "--quiet"
    )

    assert exit_code1 >= exit_code2


def test_cli_exit_codes():
    """Verify exit code constants match plan."""
    assert EXIT_PASS == 0
    assert EXIT_WARN == 1
    assert EXIT_FAIL == 2


MULTI_SHEET_PML = """Sheet:
  physical_width: 500mm
  physical_height: 500mm
  thickness: 6mm
  margin: 10mm
children:
- Assembly:
    type: box
    width: 400mm
    depth: 300mm
    height: 200mm
    thickness: 6mm
    joinery: finger
    finger_width: 12mm
    clearance: 0.15mm
    bottom: captured
    top: none
    show_labels: true
"""


def _make_multi_sheet_recipe(tmp_path):
    recipe_dir = tmp_path / "box"
    recipe_dir.mkdir()
    (recipe_dir / "box.pml.yml").write_text(MULTI_SHEET_PML)
    recipe = recipe_at(recipe_dir)
    assert recipe is not None
    runs, _ = write_recipe_outputs(recipe, recipe_dir / "output")
    assert len(runs) > 1
    return recipe_dir, runs


def test_multi_sheet_recipe_checks_every_sheet_with_its_own_intent(tmp_path):
    recipe_dir, runs = _make_multi_sheet_recipe(tmp_path)
    code, stdout, stderr = run_cli("--recipe", str(recipe_dir), "--quiet")
    assert code in (EXIT_PASS, EXIT_WARN), stderr
    result = json.loads(stdout)["validation_result"]
    assert len(result["sheets"]) == len(runs)
    for index, sheet in enumerate(result["sheets"], start=1):
        assert f"sheet_{index}" in sheet["input_file"]
        assert sheet["assertions"]["total"] > 0
        assert sheet["assertions"]["failed"] == 0
        assert sheet["metrics"]["gcode"].get("file_count", 1) == len(runs[index - 1].result.gcode)
    assert result["invariants"]["total"] == sum(s["invariants"]["total"] for s in result["sheets"])


def test_multi_sheet_corruption_on_later_sheet_fails_the_whole_job(tmp_path):
    recipe_dir, runs = _make_multi_sheet_recipe(tmp_path)
    nc = next((recipe_dir / "output").glob(f"sheet_{len(runs)}.*.nc"))
    nc.write_text(nc.read_text() + "\nG1 X99999 Y99999 Z-30 F1000\n")
    code, stdout, stderr = run_cli("--recipe", str(recipe_dir), "--quiet")
    assert code == EXIT_FAIL, stderr
    result = json.loads(stdout)["validation_result"]
    assert result["sheets"][-1]["verdict"] == "fail"
    assert result["sheets"][0]["verdict"] != "fail"


@pytest.mark.parametrize("artifact", ["svg", "nc"])
def test_multi_sheet_missing_later_artifacts_fail_explicitly(tmp_path, artifact):
    recipe_dir, runs = _make_multi_sheet_recipe(tmp_path)
    pattern = f"box_sheet_{len(runs)}.svg" if artifact == "svg" else f"sheet_{len(runs)}.*.nc"
    for path in (recipe_dir / "output").glob(pattern):
        path.unlink()
    code, _, stderr = run_cli("--recipe", str(recipe_dir))
    assert code == EXIT_FAIL
    assert f"sheet_{len(runs)}: missing" in stderr


def test_multi_sheet_summary_and_metrics_only(tmp_path):
    recipe_dir, runs = _make_multi_sheet_recipe(tmp_path)
    code, stdout, stderr = run_cli("--recipe", str(recipe_dir), "--metrics-only", "--summary")
    assert code == EXIT_PASS, stderr
    for index in range(1, len(runs) + 1):
        assert f"Sheet {index}: PASS" in stdout


def test_multi_sheet_golden_uses_separate_sheet_metrics(tmp_path):
    recipe_dir, _ = _make_multi_sheet_recipe(tmp_path)
    _, stdout, _ = run_cli("--recipe", str(recipe_dir), "--quiet")
    metrics = json.loads(stdout)["validation_result"]["metrics"]
    golden = _write_baseline(tmp_path, metrics)
    code, stdout, stderr = run_cli("--recipe", str(recipe_dir), "--golden", str(golden), "--quiet")
    assert code in (EXIT_PASS, EXIT_WARN), stderr
    assert json.loads(stdout)["validation_result"]["regressions"]["exceeded_tolerance"] == 0
