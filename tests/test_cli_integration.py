from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.usefixtures("machining_config")

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


@pytest.mark.parametrize("clearance, error", [(0, "2 disconnected pieces"), (100, "remove the entire")])
def test_notch_topology_errors_reach_the_cli_and_remove_stale_programs(tmp_path: Path, clearance, error):
    fixture = Path(__file__).parent / "fixtures/assemblies/notch_topology.pml.yml"
    text = fixture.read_text()
    source = tmp_path / "part.pml.yml"
    source.write_text(text.replace("width: 30mm", "width: 100mm"))
    out_dir = tmp_path / "out"
    args = ["-m", "cli.mill", "--input", str(source), "--out", str(out_dir)]
    _run_cli(args)
    assert list(out_dir.glob("*.nc"))
    source.write_text(text.replace("clearance: 0mm", f"clearance: {clearance}mm"))
    result = _run_cli(args, check=False)
    assert result.returncode == 1
    assert error in result.stderr and "front" in result.stderr
    assert not list(out_dir.glob("*.nc"))


def test_missing_roundover_tool_exits_3_and_replaces_old_gcode_with_diagnostics(tmp_path: Path):
    source = _write_simple_profile(tmp_path)
    out_dir = tmp_path / "out"
    args = ["-m", "cli.mill", "--input", str(source), "--out", str(out_dir)]
    _run_cli(args)
    assert list(out_dir.glob("*.nc"))
    source.write_text(SIMPLE_PROFILE_PML + "    children:\n    - Roundover: {radius: 10mm}\n")

    result = _run_cli(args, check=False)

    assert result.returncode == 3, result.stderr
    metrics = json.loads((out_dir / "metrics.json").read_text())
    error = next(error for error in metrics["errors"] if "no roundover bit" in error)
    assert "10.0mm radius" in error and "roundover" in error
    assert error in result.stderr
    assert metrics["output_size"]["files"] == {}
    assert not list(out_dir.glob("*.nc"))
    assert (out_dir / "part.pml.svg").exists()
    summary = json.loads((out_dir / "machining_summary.json").read_text())
    assert summary["files"] == []


@pytest.mark.parametrize("width,height", [(2, 2), (2, 40)])
def test_unmachinable_pocket_fails_and_removes_stale_programs(tmp_path: Path, width, height):
    source = _write_simple_profile(tmp_path)
    out_dir = tmp_path / "out"
    args = ["-m", "cli.mill", "--input", str(source), "--out", str(out_dir)]
    _run_cli(args)
    assert list(out_dir.glob("*.nc"))
    source.write_text(
        SIMPLE_PROFILE_PML.replace("type: profile", "type: pocket")
        .replace("      side: outside\n", "")
        .replace("depth: through", "depth: 3mm")
        .replace("width: 200mm", f"width: {width}mm")
        .replace("height: 150mm", f"height: {height}mm")
    )
    result = _run_cli(args, check=False)
    assert result.returncode != 0
    assert "Pocket 'part'" in result.stderr
    assert "infeasible" in result.stderr
    assert not list(out_dir.glob("*.nc"))


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
        "a.pml.profile-9.53mm.nc",
        "b.pml.profile-9.53mm.nc",
    ]
    summary = json.loads((out_dir / "machining_summary.json").read_text())
    assert [sheet["files"][0]["filename"] for sheet in summary["sheets"]] == [
        "a.pml.profile-9.53mm.nc",
        "b.pml.profile-9.53mm.nc",
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
    assert "test_router" in result.stderr


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


def test_cli_recipe_uses_configured_production_machine(tmp_path: Path):
    recipe_dir = tmp_path / "big_recipe"
    recipe_dir.mkdir()
    (recipe_dir / "example.pml.yml").write_text(OVERSIZED_SHEET_PML)

    result = _run_cli(["-m", "cli.mill", "--recipe", str(recipe_dir), "--no-svg"], check=False)
    assert result.returncode == 3

    metrics = json.loads((recipe_dir / "output" / "metrics.json").read_text())
    assert any("Machine bounds" in error for error in metrics["errors"])
    assert not list((recipe_dir / "output").glob("*.nc"))


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


def test_project_cutter_override_reaches_packing_and_physical_cut_bounds(tmp_path):
    source = tmp_path / "beam.pml.yml"
    source.write_text("""kerf: 12mm
Sheet: {physical_width: 600mm, physical_height: 600mm, thickness: 19mm, margin: 10mm}
children:
- Beam: {name: rail, length: 300mm, width: 40mm, thickness: 19mm, layers: 2}
""")
    out_dir = tmp_path / "out"
    _run_cli(["-m", "cli.mill", "--input", str(source), "--out", str(out_dir), "--kerf", "6.35"])
    metrics = json.loads((out_dir / "metrics.json").read_text())
    assert metrics["build"]["kerf_mm"] == 6.35
    assert metrics["build"]["selected_profile_diameter_mm"] == 6.35
    assert metrics["build"]["requested_kerf_mm"] == 6.35
    import re

    code = (out_dir / "profile-6.35mm.nc").read_text()
    positions = [(float(x), float(y)) for x, y in re.findall(r"^G1 X(-?[0-9.]+) Y(-?[0-9.]+)", code, re.MULTILINE)]
    assert positions
    assert min(x for x, _ in positions) - 6.35 / 2 == pytest.approx(10, abs=0.001)
    assert min(y for _, y in positions) - 6.35 / 2 == pytest.approx(10, abs=0.001)


PACKED_REVIEW_BEAM = """kerf: 0mm
Sheet: {physical_width: 600mm, physical_height: 600mm, thickness: 19mm, margin: 10mm}
children:
- Beam: {name: rail, length: 300mm, width: 40mm, thickness: 19mm, layers: 2}
"""


def test_mixed_sources_record_requested_and_actual_profile_diameters_consistently(tmp_path):
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    (inputs / "beam.pml.yml").write_text(PACKED_REVIEW_BEAM)
    (inputs / "plain.pml.yml").write_text(SIMPLE_PROFILE_PML)
    out = tmp_path / "out"
    _run_cli(["-m", "cli.mill", "--input", str(inputs), "--out", str(out), "--kerf", "6.35"])
    build = json.loads((out / "metrics.json").read_text())["build"]
    assert build["kerf_mm"] == build["requested_kerf_mm"] == 6.35
    assert build["selected_profile_diameter_mm"] == 6.35
    assert "source_kerfs_mm" not in build
    assert {c["requested_kerf_mm"] for c in build["machining"].values()} == {6.35}
    assert {c["selected_profile_diameter_mm"] for c in build["machining"].values()} == {6.35}


def test_beam_fixed_gap_error_offers_a_supported_cutter_remedy(tmp_path):
    source = tmp_path / "beam.pml.yml"
    source.write_text(PACKED_REVIEW_BEAM)
    result = _run_cli(
        ["-m", "cli.mill", "--input", str(source), "--out", str(tmp_path / "out"), "--kerf", "12.7"], check=False
    )
    assert result.returncode != 0
    assert "Layout gap 10mm must be at least selected profile cutter diameter 12.7mm" in result.stderr
    assert "Select an available flat profile cutter no wider than 10mm" in result.stderr


def test_physical_clearance_failure_preserves_the_independent_back_setup(tmp_path):
    source = tmp_path / "two_faces.pml.yml"
    source.write_text("""Sheet: {physical_width: 200mm, physical_height: 200mm, thickness: 19mm, margin: 10mm}
children:
- Rect:
    at: {x: 1mm, y: 80mm, width: 2mm, height: 60mm}
    feature: {type: profile, side: outside, depth: through}
- Circle:
    diameter: 20mm
    at: {x: 80mm, y: 80mm}
    feature: {type: pocket, face: back, depth: 2mm}
""")
    out = tmp_path / "out"
    result = _run_cli(["-m", "cli.mill", "--input", str(source), "--out", str(out)], check=False)
    assert result.returncode == 3
    programs = list(out.glob("*.nc"))
    assert programs and all(path.name.startswith("back-") for path in programs)
    assert (out / "two_faces.pml.svg").exists()
    assert (out / "two_faces.pml.back.svg").exists()


def test_requested_kerf_cannot_understate_the_actual_cutter_in_bounds_checks(tmp_path):
    source = tmp_path / "part.pml.yml"
    source.write_text("""Sheet: {physical_width: 200mm, physical_height: 200mm, thickness: 19mm, margin: 10mm}
children:
- Rect:
    at: {x: 55.5mm, y: 90mm, width: 100mm, height: 60mm}
    feature: {type: profile, side: outside, depth: through}
""")
    out = tmp_path / "out"
    result = _run_cli(["-m", "cli.mill", "--input", str(source), "--out", str(out), "--kerf", "6.35"], check=False)
    assert result.returncode == 3
    assert "0.85mm into left margin zone" in result.stderr
    assert not list(out.glob("*.nc"))


def test_legacy_layout_json_is_rejected_with_a_source_rebuild_instruction(tmp_path):
    source = tmp_path / "old.json"
    source.write_text('{"sheet":{},"items":[],"compilation":{"tools":"obsolete"}}')
    output = tmp_path / "out"
    result = _run_cli(["-m", "cli.mill", "--input", str(source), "--out", str(output)], check=False)
    assert result.returncode != 0
    assert "original .pml.yml or .nest.yml source" in result.stderr
    assert not list(output.glob("*.nc"))


def test_operation_override_reaches_gcode_and_effective_setup_report(tmp_path):
    source = tmp_path / "pocket.pml.yml"
    source.write_text("""machining:
  tools: {pocket: 'test_pocket'}
  feeds: {feed_z: 500, feed_xy: 2000}
Sheet: {width: 200mm, height: 200mm, thickness: 19mm}
children:
- Rect:
    id: pocket
    at: {x: 100mm, y: 100mm, width: 100mm, height: 100mm}
    feature:
      type: pocket
      depth: 3mm
      tool: 'test_flat_6'
      feeds: {rpm: 14000, feed_xy: 900}
""")
    output = tmp_path / "out"
    _run_cli(["-m", "cli.mill", "--input", str(source), "--out", str(output), "--no-svg"])
    code = (output / "pocket-6.35mm.nc").read_text()
    assert "M3 S14000" in code
    assert "F900.0" in code
    summary = json.loads((output / "machining_summary.json").read_text())
    (entry,) = summary["files"]
    assert entry["tool_name"] == "test_flat_6"
    assert (entry["rpm"], entry["feed_xy_mm_min"], entry["feed_z_mm_min"], entry["stepdown_mm"]) == (14000, 900, 500, 3)
    assert summary["machining"]["preset"] == "test_cutting"
    assert "compilation_contexts" not in (output / "metrics.json").read_text()


def test_nest_build_machines_source_without_intermediate_exports(tmp_path):
    source = tmp_path / "job.nest.yml"
    source.write_text("""Nest:
  algorithm: maxrects
  Sheet: {width: 400mm, height: 400mm, thickness: 12mm, material: mdf}
  machining:
    tools: {profile: 'test_flat_6'}
  parts:
  - {name: panel, width: 100mm, height: 100mm, quantity: 2}
""")
    output = tmp_path / "out"
    _run_cli(["-m", "cli.nest", str(source), "-o", str(output)])
    assert list(output.glob("*.nc")) and list(output.glob("*.svg"))
    assert not list(output.glob("*.pml.yml"))
    assert {path.name for path in output.glob("*.json")} == {"metrics.json", "machining_summary.json"}
    build = json.loads((output / "metrics.json").read_text())["build"]
    assert build["machining"][source.name]["selected_profile_tool"] == "test_flat_6"


@pytest.mark.parametrize("module", ["cli.mill", "cli.nest", "cli.recipes", "cli.validate_cam"])
def test_cli_imports_and_help_do_not_require_default_configuration(tmp_path, monkeypatch, module):
    monkeypatch.setenv("MILL_UI_MACHINES_DIR", str(tmp_path / "no_configuration"))
    result = _run_cli(["-m", module, "--help"])
    assert result.returncode == 0
    assert "usage:" in result.stdout


def test_cli_uses_only_the_supplied_configuration_root(tmp_path, monkeypatch):
    monkeypatch.setenv("MILL_UI_MACHINES_DIR", str(tmp_path / "missing_configuration"))
    result = _run_cli(
        ["-m", "cli.mill", "--input", str(_write_simple_profile(tmp_path)), "--out", str(tmp_path / "out")], check=False
    )
    assert result.returncode != 0
    assert "missing_configuration/defaults.yml" in result.stderr
    assert not list((tmp_path / "out").glob("*.nc"))
