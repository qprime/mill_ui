from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

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


@pytest.mark.parametrize("profile_child", [False, True])
def test_plot_rectangle_closes_on_design_centerline(tmp_path: Path, profile_child: bool):
    source = _write_simple_profile(tmp_path)
    if profile_child:
        source.write_text(
            SIMPLE_PROFILE_PML.replace(
                "    feature:\n      type: profile\n      depth: through\n      side: outside",
                "    children:\n    - Profile: {side: outside, depth: through}",
            )
        )
    out = tmp_path / "plot"
    result = _run_cli(["-m", "cli.mill", "--input", str(source), "--out", str(out), "--plot"])
    assert result.stdout == ""
    program = (out / "part.pml.plot.nc").read_text()
    assert "Z" not in program
    assert "M3" not in program and "M4" not in program
    moves = [line for line in program.splitlines() if line.startswith("G1 ")]
    assert len(moves) == 5
    assert moves[0] == moves[-1]
    corners = [tuple(float(word[1:]) for word in line.split()[1:]) for line in moves]
    assert max(p[0] for p in corners) - min(p[0] for p in corners) == 200
    assert max(p[1] for p in corners) - min(p[1] for p in corners) == 150
    preview = ET.parse(out / "part.pml.plot.svg")
    assert preview.find("{*}g/{*}polygon") is not None
    start = "Start G54 X125.000 Y250.000 mm"
    assert preview.findtext("{*}text") == start
    assert start in result.stderr


@pytest.mark.parametrize("size", ["diameter: 50mm", "radius: 25mm"])
def test_plot_circle_stroke_width_only_changes_svg(tmp_path: Path, size: str):
    source = tmp_path / "circle.pml.yml"
    source.write_text(
        "Sheet: {width: 200mm, height: 200mm, thickness: 19mm}\n"
        f"children:\n- Circle: {{id: plotted-circle, {size}}}\n"
    )
    default, thin, wide = (tmp_path / name for name in ("default", "thin", "wide"))
    args = ["-m", "cli.mill", "--input", str(source), "--plot"]
    _run_cli([*args, "--out", str(default)])
    _run_cli([*args, "--out", str(thin), "--plot-stroke-width", "0.5"])
    _run_cli([*args, "--out", str(wide), "--plot-stroke-width", "160"])
    program = (default / "circle.pml.plot.nc").read_text()
    assert program == (thin / "circle.pml.plot.nc").read_text()
    assert "I25.000 J0" in program and "I-25.000 J0" in program
    assert 'r="25.000"' in (default / "circle.pml.plot.svg").read_text()
    assert 'stroke-width="1"' in (default / "circle.pml.plot.svg").read_text()
    assert 'stroke-width="0.5"' in (thin / "circle.pml.plot.svg").read_text()
    assert program == (wide / "circle.pml.plot.nc").read_text()
    wide_view = ET.parse(wide / "circle.pml.plot.svg").getroot()
    assert wide_view.findtext("{*}text") == "Start G54 X75.000 Y100.000 mm"
    x, y, width, height = map(float, wide_view.attrib["viewBox"].split())
    assert x < -5 and x + width > 205
    assert y < -5 and y + height > 205
    assert float(wide_view.attrib["width"].removesuffix("mm")) == width
    assert float(wide_view.attrib["height"].removesuffix("mm")) == height


def test_plot_rejection_never_emits_a_program(tmp_path: Path):
    source = tmp_path / "part.pml.yml"
    source.write_text(OUT_OF_BOUNDS_PML.replace("x: 52mm", "x: 40mm"))
    out = tmp_path / "plot"
    result = _run_cli(["-m", "cli.mill", "--input", str(source), "--out", str(out), "--plot"], check=False)
    assert result.returncode == 3
    assert "sheet working area" in result.stderr
    assert not out.exists()


@pytest.mark.parametrize(
    "children",
    [
        "- Rect: {}\n- Circle: {diameter: 20mm}",
        "- RoundedRect: {radius: 10mm}",
        "- Rect:\n    children:\n    - Rect: {at: {x: 35mm, y: 35mm, width: 10mm, height: 10mm}}",
    ],
)
def test_plot_rejects_unsupported_geometry(tmp_path: Path, children: str):
    source = tmp_path / "part.pml.yml"
    source.write_text(f"Sheet: {{width: 140mm, height: 120mm, thickness: 6mm}}\nchildren:\n{children}\n")
    out = tmp_path / "plot"
    result = _run_cli(["-m", "cli.mill", "--plot", "--input", str(source), "--out", str(out)], check=False)
    assert result.returncode == 3, result.stderr
    assert "single front-face" in result.stderr or "exactly one shape" in result.stderr
    assert not out.exists()


@pytest.mark.parametrize("machine_limit", [False, True])
def test_plot_rejects_out_of_bounds_after_rounding(tmp_path: Path, machining_config: Path, machine_limit: bool):
    source = tmp_path / "part.pml.yml"
    machine = machining_config / "cnc/plot_router.yml"
    machine.write_text("name: Plot router\nenvelope: {x_min: 0, y_min: 0, x_max: 44.9996, y_max: 100}\n")
    margin, center = ("0", "34.99959") if machine_limit else ("10.0004", "10.00001")
    source.write_text(
        f"Sheet: {{width: 140mm, height: 120mm, thickness: 6mm, margin: {margin}mm}}\n"
        f"children:\n- Rect: {{at: {{x: {center}mm, y: 35mm, width: 20mm, height: 20mm}}}}\n"
    )
    out = tmp_path / "plot"
    result = _run_cli(
        ["-m", "cli.mill", "--plot", "--input", str(source), "--out", str(out), "--machine", "plot_router"],
        check=False,
    )
    assert result.returncode == 3
    assert ("effective envelope x_max" if machine_limit else "sheet working area") in result.stderr
    assert not out.exists()


def test_plot_uses_machine_envelope_without_a_cutting_preset(tmp_path: Path, machining_config: Path):
    (machining_config / "cnc/plot_router.yml").write_text(
        "name: Plot router\nenvelope: {x_min: 0, y_min: 0, x_max: 400, y_max: 400}\n"
    )
    source = tmp_path / "part.pml.yml"
    source.write_text(
        "Sheet: {width: 500mm, height: 120mm, thickness: 6mm, material: paper}\n"
        "children:\n- Rect: {at: {x: 60mm, y: 60mm, width: 20mm, height: 20mm}}\n"
    )
    out = tmp_path / "plot"
    _run_cli(["-m", "cli.mill", "--plot", "--input", str(source), "--out", str(out), "--machine", "plot_router"])
    assert (out / "part.pml.plot.nc").is_file()


@pytest.mark.parametrize("scenario", ["unsupported_input", "multiple_inputs", "existing_output"])
def test_plot_input_and_output_errors_exit_one(tmp_path: Path, scenario: str):
    source = _write_simple_profile(tmp_path)
    out = tmp_path / "plot"
    if scenario == "unsupported_input":
        source = source.rename(tmp_path / "part.nest.yml")
    elif scenario == "multiple_inputs":
        (tmp_path / "second.pml.yml").write_text(SIMPLE_PROFILE_PML)
        source = tmp_path
    else:
        out.mkdir()
        (out / "existing").write_text("keep")
    result = _run_cli(["-m", "cli.mill", "--plot", "--input", str(source), "--out", str(out)], check=False)
    assert result.returncode == 1
    assert not list(out.glob("*.nc"))
    if scenario == "existing_output":
        assert (out / "existing").read_text() == "keep"


@pytest.mark.parametrize(
    ("geometry", "vertices"),
    [
        ("Triangle: {base: 40mm, height: 30mm, feature: {type: profile, depth: through}}", 3),
        ("Polygon: {points: [[20,20],[60,20],[70,40],[40,65],[15,45]], feature: {type: profile, depth: through}}", 5),
    ],
)
def test_plot_authored_polygon_preserves_contour(tmp_path: Path, geometry: str, vertices: int):
    source = tmp_path / "polygon.pml.yml"
    source.write_text("Sheet: {width: 150mm, height: 150mm, thickness: 19mm}\nchildren:\n- " + geometry)
    out = tmp_path / "plot"
    _run_cli(["-m", "cli.mill", "--input", str(source), "--out", str(out), "--plot"])
    moves = [line for line in (out / "polygon.pml.plot.nc").read_text().splitlines() if line.startswith("G1 ")]
    assert len(moves) == vertices + 1
    assert moves[0] == moves[-1]


def test_plot_blueprint_preserves_selected_box_outline(tmp_path: Path):
    source = Path("docs/recipes/assemblies/finger_jointed_box/output/finger_jointed_box.svg")
    out = tmp_path / "plot"
    _run_cli(
        [
            "-m",
            "cli.mill",
            "--input",
            str(source),
            "--out",
            str(out),
            "--plot",
            "--plot-svg-stroke",
            "generated_assembly_left_side_21_left_side_outer",
        ]
    )
    program = (out / "finger_jointed_box.plot.nc").read_text()
    moves = [line for line in program.splitlines() if line.startswith("G1 ")]
    assert "Z" not in program and "M3" not in program and "M4" not in program
    assert len(moves) == 29
    assert moves[0] == moves[-1] == "G1 X110.000 Y10.030"
    preview = ET.parse(out / "finger_jointed_box.plot.svg").getroot()
    outline = preview.find("{*}g/{*}polygon")
    assert outline is not None
    xs, ys = zip(*(map(float, point.split(",")) for point in outline.attrib["points"].split()), strict=True)
    assert (max(xs) - min(xs), max(ys) - min(ys)) == (110, 70)
    assert preview.find("{*}text") is None


@pytest.mark.parametrize("duplicates", [False, True])
def test_plot_blueprint_rejects_indeterminate_selection(tmp_path: Path, duplicates: bool):
    source = tmp_path / "blueprint.svg"
    stroke = '<path id="outline" d="M0 0 L20 0 L20 20 L0 20 Z"/>'
    marks = stroke * 2 if duplicates else stroke.replace("outline", "other")
    source.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="20mm" height="20mm" viewBox="0 0 20 20">' + marks + "</svg>"
    )
    out = tmp_path / "plot"
    result = _run_cli(
        [
            "-m",
            "cli.mill",
            "--input",
            str(source),
            "--out",
            str(out),
            "--plot",
            "--plot-svg-stroke",
            "outline",
        ],
        check=False,
    )
    assert result.returncode == 3
    assert "Select exactly one blueprint stroke ID" in result.stderr
    assert not out.exists()


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


@pytest.mark.parametrize("same_directory", [False, True])
def test_nest_build_machines_source_without_intermediate_exports(tmp_path, same_directory):
    source = tmp_path / "job.nest.yml"
    source.write_text("""Nest:
  algorithm: maxrects
  Sheet: {width: 400mm, height: 400mm, thickness: 12mm, material: mdf}
  machining:
    tools: {profile: 'test_flat_6'}
  parts:
  - {name: panel, width: 100mm, height: 100mm, quantity: 2}
""")
    unrelated = tmp_path / "unrelated.txt"
    unrelated.write_text("keep")
    original = source.read_text()
    output = tmp_path if same_directory else tmp_path / "out"
    _run_cli(["-m", "cli.nest", str(source), "-o", str(output)])
    assert source.read_text() == original
    assert unrelated.read_text() == "keep"
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


@pytest.mark.parametrize("module", ["cli.mill", "cli.nest"])
def test_explicit_preset_is_used_and_identified_in_outputs(tmp_path, machining_config, module):
    from ruamel.yaml import YAML

    yaml = YAML(typ="safe")
    data = yaml.load((machining_config / "cutting_presets/test_cutting.yml").read_text())
    data["materials"]["mdf"]["parameters"]["profile"]["test_profile"]["feed_xy"] = 777
    preset = tmp_path / "custom_preset.yml"
    with preset.open("w") as handle:
        yaml.dump(data, handle)
    output = tmp_path / "out"
    if module == "cli.mill":
        source = _write_simple_profile(tmp_path)
        arguments = ["--input", str(source), "--out", str(output)]
    else:
        source = tmp_path / "job.nest.yml"
        source.write_text("""Nest:
  algorithm: maxrects
  Sheet: {width: 400mm, height: 400mm, thickness: 12mm, material: mdf}
  parts:
  - {name: panel, width: 100mm, height: 100mm, quantity: 1}
""")
        arguments = [str(source), "-o", str(output)]
    _run_cli(["-m", module, *arguments, "--preset", str(preset), "--no-svg"])
    summary = json.loads((output / "machining_summary.json").read_text())
    metrics = json.loads((output / "metrics.json").read_text())
    assert summary["machining"]["preset"] == str(preset)
    assert metrics["build"]["machining"][source.name]["preset"] == str(preset)
    assert "F777.0" in next(output.glob("*.nc")).read_text()
