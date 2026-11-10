from __future__ import annotations

import subprocess
from collections.abc import Mapping
from pathlib import Path

from cli.recipes import (
    check_pml_recipe,
    compare_output_dirs,
    find_pml_sources,
    regenerate_pml_recipe,
    run_on_recipes,
    untracked_recipe_outputs,
)

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
    at:
      x: 150mm
      y: 100mm
      width: 200mm
      height: 120mm
"""


def _write_dir(directory: Path, files: Mapping[str, str]) -> Path:
    directory.mkdir(parents=True)
    for name, text in files.items():
        (directory / name).write_text(text)
    return directory


def _make_recipe_source(recipes_dir: Path) -> Path:
    recipe_dir = recipes_dir / "part"
    recipe_dir.mkdir(parents=True)
    source = recipe_dir / "example.pml.yml"
    source.write_text(PART_PML)
    return source


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


def test_untracked_recipe_outputs_lists_new_output_file(tmp_path: Path):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    output_dir = _write_dir(tmp_path / "docs" / "recipes" / "x" / "output", {"a.nc": "G0\n", "b.svg": "<svg/>"})
    _write_dir(tmp_path / "docs" / "recipes" / "x" / "src", {"example.pml.yml": "Sheet: {}"})
    subprocess.run(["git", "add", str(output_dir / "a.nc")], cwd=tmp_path, check=True)

    assert untracked_recipe_outputs(tmp_path) == ["docs/recipes/x/output/b.svg"]


def test_find_pml_sources_reads_one_level_and_skips_outputs(tmp_path: Path):
    source = _make_recipe_source(tmp_path)
    _write_dir(source.parent / "output", {"sheet_1.pml.yml": PART_PML})

    assert find_pml_sources(tmp_path) == [source]


def test_regenerated_recipe_passes_the_check(tmp_path: Path):
    source = _make_recipe_source(tmp_path)

    assert regenerate_pml_recipe(source) == []
    assert check_pml_recipe(source) == []


def test_check_reports_a_stale_output_file(tmp_path: Path):
    source = _make_recipe_source(tmp_path)
    regenerate_pml_recipe(source)
    (source.parent / "output" / "metrics.json").write_text("{}")

    failures = run_on_recipes([source], check_pml_recipe)

    assert len(failures) == 1
    assert failures[0].startswith("part: metrics.json differs: ")


def test_run_on_recipes_reports_an_unreadable_source(tmp_path: Path):
    source = _make_recipe_source(tmp_path)
    source.write_text("Sheet: [")

    failures = run_on_recipes([source], check_pml_recipe)

    assert len(failures) == 1
    assert failures[0].startswith("part: ")
