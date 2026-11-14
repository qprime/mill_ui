from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path

import pytest

from cli.mill import write_recipe_outputs
from cli.recipes import (
    REPO_ROOT,
    check_nest_recipe,
    check_recipe_outputs,
    check_tree,
    compare_output_dirs,
    regenerate_recipe,
    regenerate_tree,
    run_on_recipes,
    untracked_recipe_files,
)
from config.machine_loader import MachineConfig, load_machine_by_name
from validation.recipe_docs import parse_detect_rule, readme_problems, rule_matches
from validation.recipes import find_recipe, find_recipes, misplaced_inputs, recipe_at, recipe_job_stem
from validation.runner import validate_recipe

CATALOG = """categories:
  doors:
    title: Doors
    description: Doors cut from one sheet.
  panels:
    title: Panels
    description: Flat parts.
guide:
  - group: Cutting parts out
    capabilities:
      - name: Tabs
        summary: Bridges that hold a part in the sheet.
        spec: pml/syntax_spec.md#profile
        detect: [{param: tab_count}]
      - name: Multi-sheet partitioning
        summary: Panels split across sheets.
        spec: pml/syntax_spec.md#multi-sheet-partitioning
"""

PART_PML = """Sheet:
  width: 300mm
  height: 200mm
  thickness: 19mm
  material: mdf
children:
- Rect:
    id: part
    feature:
      type: profile
      depth: through
      side: outside
      tab_count: 4
      tab_height: 3mm
    at:
      x: 150mm
      y: 100mm
      width: 200mm
      height: 120mm
"""

OVERSIZED_PML = PART_PML.replace("width: 300mm", "width: 1400mm").replace("height: 200mm", "height: 1400mm")

LONG_SHEET_NEST = """Nest:
  algorithm: maxrects
  Sheet:
    width: 1220mm
    height: 2440mm
    thickness: 19mm
  margin: 10mm
  parts:
    - name: panel
      width: 400mm
      height: 600mm
      quantity: 6
"""


CABINET_NEST = """Nest:
  algorithm: maxrects
  Sheet:
    width: 400mm
    height: 300mm
    thickness: 19mm
  kerf: 6.35mm
  margin: 10mm
  holding:
    onion_skin: 0.3mm
  parts:
    - name: door
      width: 300mm
      height: 180mm
      quantity: 2
      template: shaker
"""


def _altmill() -> MachineConfig:
    return load_machine_by_name("altmill_4x4")


def _write_dir(directory: Path, files: Mapping[str, str]) -> Path:
    directory.mkdir(parents=True)
    for name, text in files.items():
        (directory / name).write_text(text)
    return directory


def _make_root(tmp_path: Path, catalog: str = CATALOG) -> Path:
    root = tmp_path / "docs" / "recipes"
    root.mkdir(parents=True)
    (root / "catalog.yml").write_text(catalog)
    return root


def _make_recipe(root: Path, category: str, name: str, sources: Mapping[str, str] | None = None) -> Path:
    files = dict(sources) if sources is not None else {f"{name}.pml.yml": PART_PML}
    files["README.md"] = f"# {name}\n\n![Blueprint](output/{name}.svg)\n\n**Demonstrates:** A part.\n"
    return _write_dir(root / category / name, files)


def test_compare_output_dirs_flags_changed_svg(tmp_path: Path):
    committed = _write_dir(tmp_path / "committed", {"profile-3.17mm.nc": "G1\n", "door.svg": "<svg>a</svg>"})
    generated = _write_dir(tmp_path / "generated", {"profile-3.17mm.nc": "G1\n", "door.svg": "<svg>b</svg>"})

    assert compare_output_dirs(committed, generated) == [
        "door.svg differs: 1 lines changed (1 generated vs 1 committed)"
    ]


def test_compare_output_dirs_flags_changed_metrics(tmp_path: Path):
    committed = _write_dir(tmp_path / "committed", {"metrics.json": '{"errors": []}'})
    generated = _write_dir(tmp_path / "generated", {"metrics.json": '{"errors": ["too deep"]}'})

    assert compare_output_dirs(committed, generated) == [
        "metrics.json differs: 1 lines changed (1 generated vs 1 committed)"
    ]


def test_compare_output_dirs_flags_file_no_longer_generated(tmp_path: Path):
    committed = _write_dir(tmp_path / "committed", {"pocket-3.17mm.nc": "G0\n", "profile-3.17mm.nc": "G1\n"})
    generated = _write_dir(tmp_path / "generated", {"profile-3.17mm.nc": "G1\n"})

    assert compare_output_dirs(committed, generated) == ["File no longer generated: pocket-3.17mm.nc"]


def test_compare_output_dirs_flags_missing_file(tmp_path: Path):
    committed = _write_dir(tmp_path / "committed", {"profile-3.17mm.nc": "G1\n"})
    generated = _write_dir(tmp_path / "generated", {"profile-3.17mm.nc": "G1\n", "machining_summary.json": "{}"})

    assert compare_output_dirs(committed, generated) == ["Missing generated file: machining_summary.json"]


def test_compare_output_dirs_accepts_identical_dirs(tmp_path: Path):
    files = {"profile-3.17mm.nc": "G1\n", "door.svg": "<svg/>", "metrics.json": "{}"}
    committed = _write_dir(tmp_path / "committed", files)
    generated = _write_dir(tmp_path / "generated", files)

    assert compare_output_dirs(committed, generated) == []


def test_untracked_recipe_files_lists_outputs_and_generated_documents(tmp_path: Path):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    root = tmp_path / "docs" / "recipes"
    output_dir = _write_dir(root / "doors" / "x" / "output", {"a.nc": "G0\n", "b.svg": "<svg/>"})
    (root / "doors" / "README.md").write_text("# Doors\n")
    (root / "doors" / "x" / "x.pml.yml").write_text("Sheet: {}")
    subprocess.run(["git", "add", str(output_dir / "a.nc")], cwd=tmp_path, check=True)

    untracked = untracked_recipe_files(tmp_path, root, [root / "doors" / "README.md"])

    assert untracked == ["docs/recipes/doors/README.md", "docs/recipes/doors/x/output/b.svg"]


def test_find_recipes_reads_category_folders(tmp_path: Path):
    root = _make_root(tmp_path)
    _make_recipe(root, "doors", "shaker_door")
    _make_recipe(root, "panels", "plate")

    assert [(recipe.category, recipe.name) for recipe in find_recipes(root)] == [
        ("doors", "shaker_door"),
        ("panels", "plate"),
    ]


def test_find_recipes_does_not_search_inside_a_recipe(tmp_path: Path):
    root = _make_root(tmp_path)
    folder = _make_recipe(root, "doors", "x")
    _write_dir(folder / "output", {"sheet_1.pml.yml": PART_PML})

    (recipe,) = find_recipes(root)

    assert recipe.pml_sources == (folder / "x.pml.yml",)
    assert misplaced_inputs(root) == ()


def test_find_recipes_rejects_duplicate_names(tmp_path: Path):
    root = _make_root(tmp_path)
    first = _make_recipe(root, "doors", "x")
    second = _make_recipe(root, "panels", "x")

    with pytest.raises(ValueError, match="Two recipes are named x") as raised:
        find_recipes(root)

    assert str(first) in str(raised.value)
    assert str(second) in str(raised.value)


def test_find_recipe_names_a_missing_recipe(tmp_path: Path):
    root = _make_root(tmp_path)
    folder = _make_recipe(root, "doors", "x")

    assert find_recipe("x", root).path == folder
    with pytest.raises(KeyError, match="No recipe named nope"):
        find_recipe("nope", root)


def test_misplaced_inputs_lists_files_at_the_wrong_depth(tmp_path: Path):
    root = _make_root(tmp_path)
    folder = _make_recipe(root, "doors", "x")
    _write_dir(folder / "output", {"sheet_1.pml.yml": PART_PML})
    _write_dir(folder / "variants", {"v2.pml.yml": PART_PML})
    (root / "loose.pml.yml").write_text(PART_PML)
    (root / "doors" / "in_category.nest.yml").write_text(LONG_SHEET_NEST)

    assert misplaced_inputs(root) == (
        root / "doors" / "in_category.nest.yml",
        folder / "variants" / "v2.pml.yml",
        root / "loose.pml.yml",
    )


def test_recipe_at_accepts_source_named_after_recipe(tmp_path: Path):
    folder = _make_recipe(_make_root(tmp_path), "doors", "x")

    recipe = recipe_at(folder)

    assert recipe is not None
    assert recipe.pml_sources == (folder / "x.pml.yml",)
    assert recipe.category == "doors"


def test_recipe_job_stem_uses_source_stems_for_multi_file_recipes(tmp_path: Path):
    root = _make_root(tmp_path)
    single = recipe_at(_make_recipe(root, "doors", "x"))
    double = recipe_at(_make_recipe(root, "panels", "y", {"a.pml.yml": PART_PML, "b.pml.yml": PART_PML}))
    assert single is not None
    assert double is not None

    assert recipe_job_stem(single, single.pml_sources[0]) == "x"
    assert [recipe_job_stem(double, source) for source in double.pml_sources] == ["a.pml", "b.pml"]


def test_two_source_recipe_writes_outputs_per_source(tmp_path: Path):
    recipe = recipe_at(
        _make_recipe(_make_root(tmp_path), "panels", "y", {"a.pml.yml": PART_PML, "b.pml.yml": PART_PML})
    )
    assert recipe is not None

    regenerate_recipe(recipe)
    names = sorted(path.name for path in (recipe.path / "output").iterdir())

    assert {"a.pml.svg", "b.pml.svg", "manifest.json"} <= set(names)
    assert [name for name in names if name.endswith(".nc")] == ["a.pml.profile-3.17mm.nc", "b.pml.profile-3.17mm.nc"]


def test_gate_passes_with_no_recipes(tmp_path: Path):
    root = _make_root(tmp_path)

    assert regenerate_tree(root) == []
    assert check_tree(root, _altmill()) == []


def test_regenerated_tree_passes_the_check(tmp_path: Path):
    root = _make_root(tmp_path)
    _make_recipe(root, "doors", "door")

    assert regenerate_tree(root) == []
    assert check_tree(root, _altmill()) == []


def test_check_reports_a_stale_output_file(tmp_path: Path):
    recipe = recipe_at(_make_recipe(_make_root(tmp_path), "doors", "door"))
    assert recipe is not None
    regenerate_recipe(recipe)
    (recipe.path / "output" / "metrics.json").write_text("{}")

    failures = run_on_recipes([recipe], lambda r: check_recipe_outputs(r, _altmill()))

    assert len(failures) == 1
    assert failures[0].startswith("door: metrics.json differs: ")


def test_gate_rejects_design_errors_even_when_outputs_match(tmp_path: Path):
    pml = PART_PML.replace("x: 150mm", "x: 100mm")
    recipe = recipe_at(_make_recipe(_make_root(tmp_path), "doors", "door", {"door.pml.yml": pml}))
    assert recipe is not None
    regenerate_recipe(recipe)

    failures = check_recipe_outputs(recipe, _altmill())

    assert len(failures) == 1
    assert "door.pml.yml sheet 1: Cutting edge extends" in failures[0]
    assert "left margin zone" in failures[0]


def test_run_on_recipes_reports_an_unreadable_source(tmp_path: Path):
    recipe = recipe_at(_make_recipe(_make_root(tmp_path), "doors", "door"))
    assert recipe is not None
    recipe.pml_sources[0].write_text("Sheet: [")

    failures = run_on_recipes([recipe], lambda r: check_recipe_outputs(r, _altmill()))

    assert len(failures) == 1
    assert failures[0].startswith("door: ")


def test_detect_rules():
    document = {
        "children": [{"SvgStamp": {"file": "art.svg"}}, {"Rect": {"feature": {"tab_count": 4}}}],
        "interfaces": [{"joinery": "step"}],
    }

    assert rule_matches(parse_detect_rule({"node": "SvgStamp"}), "x", [document])
    assert rule_matches(parse_detect_rule({"param": "tab_count"}), "x", [document])
    assert rule_matches(parse_detect_rule({"value": {"joinery": "step"}}), "x", [document])
    assert rule_matches(parse_detect_rule({"recipes": ["x"]}), "x", [{}])
    assert not rule_matches(parse_detect_rule({"value": {"joinery": "finger"}}), "x", [document])
    assert not rule_matches(parse_detect_rule({"node": "Voronoi"}), "x", [document])
    with pytest.raises(ValueError, match="Malformed detect rule"):
        parse_detect_rule({"param": "a", "node": "B"})


def test_recipes_rule_naming_a_missing_recipe_fails(tmp_path: Path):
    root = _make_root(tmp_path, CATALOG + "        detect: [{recipes: [nope]}]\n")
    regenerate_tree(root)

    assert check_tree(root, _altmill()) == [
        "catalog.yml: capability 'Multi-sheet partitioning' names recipe 'nope', which does not exist"
    ]


def test_recipe_docs_render_index_category_and_guide(tmp_path: Path):
    root = _make_root(tmp_path)
    _make_recipe(root, "doors", "door")

    regenerate_tree(root)
    index = (root / "README.md").read_text()
    guide = (root.parent / "feature_guide.md").read_text()

    assert '### [door](doors/door/)\n\n<img src="doors/door/output/door.svg" width="240">\n\nA part.' in index
    assert "## Panels\n\nFlat parts.\n\nNo recipes yet." in index
    assert "## [door](door/)" in (root / "doors" / "README.md").read_text()
    assert not (root / "panels" / "README.md").exists()
    assert "Recipes: [door](recipes/doors/door/)" in guide
    assert "Spec: [pml/syntax_spec.md#profile](../pml/syntax_spec.md#profile)" in guide
    assert guide.endswith("## No recipe yet\n\n- Multi-sheet partitioning (Cutting parts out)\n")


def test_untracked_or_stale_generated_document_is_reported(tmp_path: Path):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    root = _make_root(tmp_path)
    _make_recipe(root, "doors", "door")
    regenerate_tree(root)
    (root / "panels").mkdir()
    (root / "panels" / "README.md").write_text("# Panels\n")

    failures = check_tree(root, _altmill(), repo_root=tmp_path)

    assert any(
        f.startswith(f"Generated document is no longer generated: {root / 'panels' / 'README.md'}") for f in failures
    )
    assert "Untracked recipe file: docs/recipes/doors/README.md" in failures
    assert "Untracked recipe file: docs/feature_guide.md" in failures


def test_recipe_readme_requires_demonstrates_and_blueprint(tmp_path: Path):
    root = _make_root(tmp_path)
    folder = _make_recipe(root, "doors", "door")
    (folder / "README.md").write_text("# Door\n\n![Blueprint](output/door.svg)\n")
    nest_folder = _write_dir(
        root / "production" / "job",
        {"job.nest.yml": LONG_SHEET_NEST, "README.md": "# Job\n\n**Demonstrates:** Nesting.\n"},
    )
    recipe = recipe_at(folder)
    nest_recipe = recipe_at(nest_folder)
    assert recipe is not None
    assert nest_recipe is not None

    assert readme_problems(recipe) == [
        "README.md has no **Demonstrates:** line",
        "README.md embeds no image from its own output/ that exists",
    ]
    assert readme_problems(nest_recipe) == ["README.md embeds no image from its own output/ that exists"]


def test_recipe_must_fit_altmill(tmp_path: Path):
    root = _make_root(tmp_path)
    pml_recipe = recipe_at(_make_recipe(root, "doors", "big", {"big.pml.yml": OVERSIZED_PML}))
    nest_recipe = recipe_at(_write_dir(root / "production" / "job", {"job.nest.yml": LONG_SHEET_NEST}))
    assert pml_recipe is not None
    assert nest_recipe is not None
    regenerate_recipe(pml_recipe)

    assert any("does not fit altmill_4x4" in problem for problem in check_recipe_outputs(pml_recipe, _altmill()))
    assert any(
        problem.startswith("job.nest.yml does not fit altmill_4x4: Job y_max")
        for problem in check_nest_recipe(nest_recipe, _altmill())
    )


def test_category_recipe_outputs_are_not_gitignored():
    result = subprocess.run(
        ["git", "check-ignore", "--no-index", "docs/recipes/doors/x/output/x.svg"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1, result.stdout


def _run_mill_recipe(recipe_dir: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "cli.mill", "--recipe", str(recipe_dir), "--no-svg"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )


def test_cli_recipe_runs_source_named_after_recipe(tmp_path: Path):
    folder = _make_recipe(_make_root(tmp_path), "doors", "x")

    result = _run_mill_recipe(folder)

    assert result.returncode == 0, result.stderr
    assert (folder / "output" / "metrics.json").exists()


def test_cli_recipe_runs_nest_only_folder(tmp_path: Path):
    folder = _write_dir(tmp_path / "production" / "job", {"job.nest.yml": LONG_SHEET_NEST})

    result = _run_mill_recipe(folder)

    assert result.returncode == 0, result.stderr
    output = folder / "output"
    assert (output / "metrics.json").exists()
    assert list(output.glob("*.nc"))


def test_validate_recipe_rejects_several_pml_sources(tmp_path: Path):
    recipe = recipe_at(
        _make_recipe(_make_root(tmp_path), "panels", "y", {"a.pml.yml": PART_PML, "b.pml.yml": PART_PML})
    )
    assert recipe is not None
    write_recipe_outputs(recipe, recipe.path / "output")

    with pytest.raises(ValueError, match="handles one PML source"):
        validate_recipe(recipe.path)


@pytest.mark.parametrize("artifact", ["job_sheet_1.svg", "sheet_1.profile-6.35mm.nc"])
def test_nest_recipe_generates_and_checks_machining_outputs(tmp_path: Path, artifact: str):
    recipe = recipe_at(_make_recipe(_make_root(tmp_path), "doors", "job", {"job.nest.yml": CABINET_NEST}))
    assert recipe is not None
    (recipe.path / "README.md").write_text(
        "# Job\n\n![Blueprint](output/job_sheet_1.svg)\n\n**Demonstrates:** Nested doors.\n"
    )

    regenerate_recipe(recipe)

    assert readme_problems(recipe) == []
    assert check_recipe_outputs(recipe, _altmill()) == []
    summary = json.loads((recipe.path / "output" / "machining_summary.json").read_text())
    assert summary["total_sheets"] == 2
    assert summary["kerf_mm"] == 6.35
    for sheet in summary["sheets"]:
        assert sheet["feature_counts"] == {"pocket": 1, "profile": 1}
    (recipe.path / "output" / artifact).write_text("stale\n")

    assert any(f"{artifact} differs" in error for error in check_recipe_outputs(recipe, _altmill()))


def test_recipe_compiles_both_pml_and_nest_sources(tmp_path: Path):
    recipe = recipe_at(
        _make_recipe(_make_root(tmp_path), "doors", "job", {"part.pml.yml": PART_PML, "doors.nest.yml": CABINET_NEST})
    )
    assert recipe is not None

    runs, outputs = write_recipe_outputs(recipe, recipe.path / "output")

    assert len(runs) == 3
    assert {run.source for run in runs} == {"part.pml.yml", "doors.nest.yml"}
    assert all(not run.result.errors for run in runs)
    assert (recipe.path / "output" / "part.pml.svg").exists()
    assert (recipe.path / "output" / "doors.nest_sheet_1.svg").exists()
    metrics = json.loads(outputs["metrics"].read_text())
    assert metrics["build"]["kerf_mm"] is None
    assert metrics["build"]["source_kerfs_mm"] == {"part.pml.yml": 3.175, "doors.nest.yml": 6.35}


def test_nest_recipe_kerf_override_applies_to_packing_and_machining(tmp_path: Path):
    recipe = recipe_at(_make_recipe(_make_root(tmp_path), "doors", "job", {"job.nest.yml": CABINET_NEST}))
    assert recipe is not None

    runs, outputs = write_recipe_outputs(recipe, recipe.path / "output", kerf_mm=3.175)

    assert all(not run.result.errors for run in runs)
    assert runs[0].result.ast.kerf_width_mm == 3.175
    assert "sheet_1.profile-3.17mm" in runs[0].result.gcode
    summary = json.loads(outputs["machining_summary"].read_text())
    assert summary["kerf_mm"] == 3.175


def test_nest_recipe_rejects_unplaced_parts(tmp_path: Path):
    nest = CABINET_NEST.replace("width: 300mm", "width: 500mm")
    recipe = recipe_at(_make_recipe(_make_root(tmp_path), "doors", "job", {"job.nest.yml": nest}))
    assert recipe is not None

    with pytest.raises(ValueError, match=r"job\.nest\.yml: parts do not fit.*2x door"):
        regenerate_recipe(recipe)


PACKED_BOX_PML = """kerf: 12mm
Sheet:
  physical_width: 600mm
  physical_height: 600mm
  thickness: 19mm
  margin: 10mm
children:
- Assembly:
    type: box
    width: 200mm
    depth: 150mm
    height: 100mm
    thickness: 19mm
    joinery: butt
    bottom: none
    top: none
    layout_gap: 10mm
"""

PACKED_BEAM_PML = """kerf: 12mm
Sheet:
  physical_width: 600mm
  physical_height: 600mm
  thickness: 19mm
  margin: 10mm
children:
- Beam:
    name: rail
    length: 300mm
    width: 40mm
    thickness: 19mm
    layers: 2
"""


def _profile_bounds(asts):
    from adapters.ast_to_removal import ast_to_removal_intents

    return [intent.bounds for ast in asts for intent in ast_to_removal_intents(ast) if intent.hint_type == "profile"]


@pytest.mark.parametrize("source", [PACKED_BOX_PML, PACKED_BEAM_PML])
@pytest.mark.parametrize("kerf", [3.175, 6.35])
def test_packed_sources_use_the_selected_cutter_and_preserve_authored_kerf(tmp_path, source, kerf):
    from cli.mill import load_pml_asts
    from pml import parse_pml_yaml
    from resolution.layout_resolver import resolve_layout_multi

    path = tmp_path / "parts.pml.yml"
    path.write_text(source)
    parsed = parse_pml_yaml(source)
    original = resolve_layout_multi(parsed)
    resolved = load_pml_asts(path, kerf_mm=kerf)
    bounds = _profile_bounds(resolved)
    assert min(b.x_min for b in bounds) == pytest.approx(kerf)
    assert min(b.y_min for b in bounds) == pytest.approx(kerf)
    assert sorted((round(b.width, 8), round(b.height, 8)) for b in bounds) == sorted(
        (round(b.width, 8), round(b.height, 8)) for b in _profile_bounds(original)
    )
    assert all(ast.kerf_width_mm == 12 for ast in resolved)
    assert all(
        ast.machining_clearance is not None and ast.machining_clearance.profile_diameter_mm == kerf for ast in resolved
    )
    assert parsed == parse_pml_yaml(source)


def test_embedded_assembly_receives_cutter_context(tmp_path):
    from cli.mill import load_pml_asts

    source = PACKED_BOX_PML.replace(
        "- Assembly:",
        "- AtPosition:\n    x: 290mm\n    y: 290mm\n    width: 580mm\n    height: 580mm\n    child:\n      Assembly:",
    )
    head, body = source.split("      Assembly:\n")
    source = head + "      Assembly:\n" + "\n".join("    " + line for line in body.splitlines()) + "\n"
    path = tmp_path / "embedded.pml.yml"
    path.write_text(source)
    bounds = _profile_bounds(load_pml_asts(path, kerf_mm=3.175))
    assert min(b.x_min for b in bounds) == pytest.approx(3.175)
    assert min(b.y_min for b in bounds) == pytest.approx(3.175)


def test_actual_library_cutter_reaches_recipe_packing_and_planning(tmp_path):
    from config.machine_loader import Endmill, FeedsEntry

    endmills = [Endmill("custom_3mm", 3, 20, 3, 2, "straight")]
    feeds = [FeedsEntry("custom_3mm", "mdf", 0.05, 18000, 2, 0.3)]
    path = tmp_path / "box"
    path.mkdir()
    (path / "box.pml.yml").write_text(PACKED_BOX_PML)
    recipe = recipe_at(path)
    assert recipe is not None
    runs, _ = write_recipe_outputs(recipe, path / "output", kerf_mm=5, endmills=endmills, feeds=feeds)
    assert min(b.x_min for b in _profile_bounds([run.result.ast for run in runs])) == pytest.approx(3)
    assert all(p.tool_selection.diameter == 3 for run in runs for p in run.result.passes if p.op == "profile")
    assert all(not run.result.errors for run in runs)
    metrics = json.loads((path / "output" / "metrics.json").read_text())
    assert metrics["build"]["kerf_mm"] == 5
    assert metrics["build"]["requested_kerf_mm"] == 5
    assert metrics["build"]["selected_profile_diameter_mm"] == 3


def test_packed_context_rejects_a_changed_profile_library(tmp_path):
    from cam.pipeline import run_pipeline
    from cli.mill import load_pml_asts

    path = tmp_path / "box.pml.yml"
    path.write_text(PACKED_BOX_PML)
    (ast,) = load_pml_asts(path, kerf_mm=3.175)
    with pytest.raises(ValueError, match="Profile cutter changed after packing"):
        run_pipeline(ast, kerf_mm=6.35)


def test_packed_context_rejects_gap_smaller_than_selected_cutter(tmp_path):
    from cli.mill import load_pml_asts
    from resolution.layout_resolver import ResolutionAssertionError

    path = tmp_path / "box.pml.yml"
    path.write_text(PACKED_BOX_PML)
    with pytest.raises(
        ResolutionAssertionError, match=r"Layout gap 10mm must be at least selected profile cutter diameter 12\.7mm"
    ):
        load_pml_asts(path, kerf_mm=12.7)


def test_recipe_and_project_paths_agree_with_an_explicit_kerf(tmp_path):
    from cli.mill import load_pml_asts

    path = tmp_path / "box"
    path.mkdir()
    source = path / "box.pml.yml"
    source.write_text(PACKED_BOX_PML)
    recipe = recipe_at(path)
    assert recipe is not None
    runs, _ = write_recipe_outputs(recipe, path / "output", kerf_mm=5)
    project = load_pml_asts(source, kerf_mm=5)
    assert [run.result.ast for run in runs] == project
    assert project[0].machining_clearance is not None
    assert project[0].machining_clearance.profile_diameter_mm == 6.35
    assert min(b.x_min for b in _profile_bounds(project)) == pytest.approx(6.35)


def test_custom_cutter_snapshot_drives_validation_without_default_tool_reselection(tmp_path):
    from unittest.mock import patch

    from cam.compilation import CompilationContext
    from config.machine_loader import Endmill, FeedsEntry
    from resolution.layout_resolver import resolve_layout_multi

    folder = tmp_path / "custom"
    folder.mkdir()
    (folder / "beam.pml.yml").write_text(PACKED_BEAM_PML)
    recipe = recipe_at(folder)
    assert recipe is not None
    endmills = [Endmill("custom3", 3, 20, 3, 2, "straight")]
    feeds = [FeedsEntry("custom3", "mdf", 0.05, 18000, 2, 0.3)]
    runs, _ = write_recipe_outputs(recipe, folder / "output", kerf_mm=5, endmills=endmills, feeds=feeds)
    metrics_path = folder / "output" / "metrics.json"
    metrics = json.loads(metrics_path.read_text())
    saved = metrics["build"]["compilation_contexts"]["beam.pml.yml"]
    assert CompilationContext.from_dict(saved).profile_diameter_mm == 3
    with patch("cam.compilation.resolve_layout_multi", wraps=resolve_layout_multi) as spy:
        result = validate_recipe(folder)
    assert spy.call_args.kwargs["machining_clearance"].profile_diameter_mm == 3
    assert not result.assertions.failed
    assert not result.invariants.failed
    assert runs[0].result.ast.machining_clearance is not None
    assert runs[0].result.ast.machining_clearance.profile_diameter_mm == 3
    saved["selected_profile_diameter_mm"] = 3.175
    metrics_path.write_text(json.dumps(metrics))
    with pytest.raises(ValueError, match="fingerprint or selected cutter disagrees"):
        validate_recipe(folder)


def test_packed_recipe_validation_requires_saved_context_instead_of_guessing_defaults(tmp_path):
    folder = tmp_path / "legacy"
    folder.mkdir()
    (folder / "beam.pml.yml").write_text(PACKED_BEAM_PML)
    with pytest.raises(ValueError, match="saved compilation context is missing"):
        validate_recipe(folder)
