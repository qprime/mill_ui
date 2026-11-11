from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

SIMPLE_PROFILE_PML = """Sheet:
  width: 450mm
  height: 650mm
  thickness: 19mm
  material: mdf
children:
- Rect:
    id: part
    feature:
      type: profile
      depth: through
      side: outside
    at:
      x: 225mm
      y: 325mm
      width: 200mm
      height: 150mm
"""


def _write_simple_profile(tmp_path: Path) -> Path:
    source = tmp_path / "part.pml.yml"
    source.write_text(SIMPLE_PROFILE_PML)
    return source


def _check_optional_deps() -> dict[str, bool]:
    import importlib.util

    return {
        "shapely": importlib.util.find_spec("shapely") is not None,
        "numpy": importlib.util.find_spec("numpy") is not None,
    }


OPTIONAL_DEPS = _check_optional_deps()


def _skip_if_missing(dep: str) -> None:
    if not OPTIONAL_DEPS.get(dep, False):
        pytest.skip(f"missing {dep}")


def _run_cli(args: list[str], check: bool = True) -> subprocess.CompletedProcess:
    result = subprocess.run(
        [sys.executable, *args],
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent.parent,
    )
    if check and result.returncode != 0:
        raise AssertionError(f"CLI failed with code {result.returncode}:\n{result.stderr}")
    return result


def test_export_blueprint_produces_svg(tmp_path: Path):

    _skip_if_missing("shapely")

    output_path = tmp_path / "out"
    result = _run_cli(
        [
            "-m",
            "cli.mill",
            "--input",
            str(_write_simple_profile(tmp_path)),
            "--out",
            str(output_path),
            "--theme",
            "dark",
        ]
    )

    svg_files = list(output_path.glob("*.svg"))
    assert len(svg_files) > 0, f"No SVG files generated. stderr: {result.stderr}"

    expected_svg = output_path / "part.pml.svg"
    assert expected_svg.exists(), f"Expected SVG not found. Files: {list(output_path.iterdir())}"

    svg_content = expected_svg.read_text()
    assert "<svg" in svg_content, "SVG file missing <svg> tag"
    assert "</svg>" in svg_content, "SVG file missing closing </svg> tag"


def test_convert_layout_pml_to_json(tmp_path: Path):
    json_file = tmp_path / "output.json"

    result = _run_cli(
        [
            "-m",
            "cli.convert_layout",
            "--from",
            "pml",
            "--to",
            "json",
            str(_write_simple_profile(tmp_path)),
            str(json_file),
        ]
    )

    assert json_file.exists(), f"JSON file not created. stderr: {result.stderr}"

    data = json.loads(json_file.read_text())

    assert "sheet" in data, "JSON missing 'sheet' key"
    assert "items" in data, "JSON missing 'items' key"
    assert data["sheet"]["width_mm"] == 450, f"Unexpected sheet width: {data['sheet']}"
    assert data["sheet"]["height_mm"] == 650, f"Unexpected sheet height: {data['sheet']}"


def test_convert_layout_json_to_pml(tmp_path: Path):
    json_file = tmp_path / "intermediate.json"
    pml_file = tmp_path / "roundtrip.pml.yml"

    _run_cli(
        [
            "-m",
            "cli.convert_layout",
            "--from",
            "pml",
            "--to",
            "json",
            str(_write_simple_profile(tmp_path)),
            str(json_file),
        ]
    )

    _run_cli(
        [
            "-m",
            "cli.convert_layout",
            "--from",
            "json",
            "--to",
            "pml",
            str(json_file),
            str(pml_file),
        ]
    )

    assert pml_file.exists(), "PML roundtrip file not created"

    pml_content = pml_file.read_text()
    assert "Sheet" in pml_content, "PML missing 'Sheet' declaration"
    assert "450" in pml_content, "PML missing sheet width"
    assert "650" in pml_content, "PML missing sheet height"


def test_cli_missing_input_fails():

    result = _run_cli(
        [
            "-m",
            "cli.mill",
            "--input",
            "/nonexistent/path/to/file.pml.yml",
            "--out",
            "/tmp",
        ],
        check=False,
    )

    assert result.returncode != 0, "CLI should fail with missing input"
    assert "not found" in result.stderr.lower() or "error" in result.stderr.lower()


def test_cli_invalid_format_fails(tmp_path: Path):
    invalid_file = tmp_path / "layout.xyz"
    invalid_file.write_text("invalid content")

    result = _run_cli(
        ["-m", "cli.mill", "--input", str(invalid_file), "--out", str(tmp_path / "out")],
        check=False,
    )

    assert result.returncode == 1, result.stderr
    assert "unsupported input format" in result.stderr.lower()


OUT_OF_BOUNDS_PML = """Sheet:
  width: 300mm
  height: 200mm
  thickness: 19mm
  margin: 10mm
  material: mdf
children:
- Rect:
    id: part
    feature:
      type: profile
      depth: through
      side: outside
    at:
      x: 52mm
      y: 100mm
      width: 100mm
      height: 50mm
"""


def test_cli_design_error_exits_3_and_lists_errors(tmp_path: Path):
    source = tmp_path / "part.pml.yml"
    source.write_text(OUT_OF_BOUNDS_PML)
    out_dir = tmp_path / "out"

    result = _run_cli(["-m", "cli.mill", "--input", str(source), "--out", str(out_dir)], check=False)

    assert result.returncode == 3, result.stderr
    metrics = json.loads((out_dir / "metrics.json").read_text())
    assert any("margin zone" in error for error in metrics["errors"]), metrics["errors"]
    assert (out_dir / "part.pml.svg").exists()


def test_missing_roundover_tool_exits_3_and_replaces_old_gcode_with_diagnostics(tmp_path: Path):
    source = _write_simple_profile(tmp_path)
    out_dir = tmp_path / "out"
    args = ["-m", "cli.mill", "--input", str(source), "--out", str(out_dir)]
    _run_cli(args)
    assert list(out_dir.glob("*.nc"))
    source.write_text(SIMPLE_PROFILE_PML + "    children:\n    - Roundover: {radius: 6mm}\n")

    result = _run_cli(args, check=False)

    assert result.returncode == 3, result.stderr
    metrics = json.loads((out_dir / "metrics.json").read_text())
    error = next(error for error in metrics["errors"] if "no roundover bit" in error)
    assert "6.0mm radius" in error and "roundover" in error
    assert error in result.stderr
    assert metrics["output_size"]["files"] == {}
    assert not list(out_dir.glob("*.nc"))
    assert (out_dir / "part.pml.svg").exists()
    summary = json.loads((out_dir / "machining_summary.json").read_text())
    assert summary["files"] == []


def test_cli_multi_file_run_keeps_every_file_and_writes_one_metrics_file(tmp_path: Path):
    input_dir = tmp_path / "project"
    input_dir.mkdir()
    (input_dir / "a.pml.yml").write_text(SIMPLE_PROFILE_PML)
    (input_dir / "b.pml.yml").write_text(SIMPLE_PROFILE_PML)
    out_dir = tmp_path / "out"

    _run_cli(["-m", "cli.mill", "--input", str(input_dir), "--out", str(out_dir), "--no-svg"])

    metrics = json.loads((out_dir / "metrics.json").read_text())
    assert metrics["total_sheets"] == 2
    assert [sheet["source"] for sheet in metrics["sheets"]] == ["a.pml.yml", "b.pml.yml"]
    assert metrics["build"]["sources"] == ["a.pml.yml", "b.pml.yml"]
    assert metrics["errors"] == []
    assert sorted(path.name for path in out_dir.glob("*.nc")) == [
        "a.pml.profile-6.35mm.nc",
        "b.pml.profile-6.35mm.nc",
    ]
    summary = json.loads((out_dir / "machining_summary.json").read_text())
    assert [sheet["files"][0]["filename"] for sheet in summary["sheets"]] == [
        "a.pml.profile-6.35mm.nc",
        "b.pml.profile-6.35mm.nc",
    ]
    manifest = json.loads((out_dir / "manifest.json").read_text())
    assert manifest["sources"] == ["a.pml.yml", "b.pml.yml"]


OVERSIZED_SHEET_PML = SIMPLE_PROFILE_PML.replace("width: 450mm", "width: 1400mm").replace(
    "height: 650mm", "height: 1400mm"
)


def test_cli_unknown_machine_exits_1_and_lists_machines(tmp_path: Path):
    result = _run_cli(
        [
            "-m",
            "cli.mill",
            "--input",
            str(_write_simple_profile(tmp_path)),
            "--out",
            str(tmp_path / "out"),
            "--machine",
            "no_such_mill",
        ],
        check=False,
    )

    assert result.returncode == 1, result.stderr
    assert "Unknown machine 'no_such_mill'" in result.stderr
    assert "altmill_4x4" in result.stderr


def test_cli_default_machine_rejects_sheet_beyond_envelope(tmp_path: Path):
    source = tmp_path / "big.pml.yml"
    source.write_text(OVERSIZED_SHEET_PML)
    out_dir = tmp_path / "out"

    result = _run_cli(["-m", "cli.mill", "--input", str(source), "--out", str(out_dir)], check=False)

    assert result.returncode == 3, result.stderr
    metrics = json.loads((out_dir / "metrics.json").read_text())
    assert any(error.startswith("Machine bounds:") for error in metrics["errors"]), metrics["errors"]
    assert list(out_dir.glob("*.nc")) == []
    assert list(out_dir.glob("*.svg")) == []


def test_cli_recipe_runs_without_default_machine(tmp_path: Path):
    recipe_dir = tmp_path / "big_recipe"
    recipe_dir.mkdir()
    (recipe_dir / "example.pml.yml").write_text(OVERSIZED_SHEET_PML)

    _run_cli(["-m", "cli.mill", "--recipe", str(recipe_dir), "--no-svg"])

    metrics = json.loads((recipe_dir / "output" / "metrics.json").read_text())
    assert metrics["errors"] == []
    assert list((recipe_dir / "output").glob("*.nc"))


def test_cli_recipe_run_omits_provenance(tmp_path: Path):
    recipe_dir = tmp_path / "recipe"
    recipe_dir.mkdir()
    (recipe_dir / "example.pml.yml").write_text(SIMPLE_PROFILE_PML)

    _run_cli(["-m", "cli.mill", "--recipe", str(recipe_dir), "--no-svg"])

    metrics = json.loads((recipe_dir / "output" / "metrics.json").read_text())
    assert "provenance" not in metrics


def test_cli_input_run_records_provenance(tmp_path: Path):
    out_dir = tmp_path / "out"

    _run_cli(["-m", "cli.mill", "--input", str(_write_simple_profile(tmp_path)), "--out", str(out_dir), "--no-svg"])

    metrics = json.loads((out_dir / "metrics.json").read_text())
    assert set(metrics["provenance"]) == {"mill_ui"}
