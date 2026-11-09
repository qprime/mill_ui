from __future__ import annotations

import json
from pathlib import Path

from cam.pipeline import PipelineResult, SheetRun, build_run_metrics, write_run_outputs
from layout_ast.layout import LayoutAST, Sheet

BUILD = {"kerf_mm": 3.175, "theme": "dark", "y_origin": "back"}


def _result(
    *,
    errors: list[str] | None = None,
    warnings: list[str] | None = None,
    gcode_name: str = "profile-3.17mm",
) -> PipelineResult:
    return PipelineResult(
        ast=LayoutAST(sheet=Sheet(width_mm=300.0, height_mm=200.0, thickness_mm=19.0), items=()),
        intents=[],
        passes=[],
        gcode={gcode_name: "G0 Z5\n"},
        svg="<svg></svg>",
        metrics={"timing": {"total_ms": 1.0}, "complexity": {"total_moves": 1}},
        errors=errors or [],
        warnings=warnings or [],
    )


def _run(
    source: str,
    sheet_index: int,
    job_name: str,
    *,
    errors: list[str] | None = None,
    warnings: list[str] | None = None,
) -> SheetRun:
    return SheetRun(
        source=source,
        sheet_index=sheet_index,
        job_name=job_name,
        result=_result(errors=errors, warnings=warnings),
    )


def test_single_sheet_metrics_stay_flat_with_errors_and_warnings():
    metrics = build_run_metrics([_run("door.pml.yml", 1, "door", errors=["too deep"], warnings=["thin web"])], BUILD)

    assert "sheets" not in metrics
    assert "timing" not in metrics
    assert metrics["complexity"] == {"total_moves": 1}
    assert metrics["errors"] == ["too deep"]
    assert metrics["warnings"] == ["thin web"]
    assert metrics["build"] == {**BUILD, "source": "door.pml.yml"}


def test_single_sheet_without_issues_lists_empty_errors_and_warnings():
    metrics = build_run_metrics([_run("door.pml.yml", 1, "door")], BUILD)

    assert metrics["errors"] == []
    assert metrics["warnings"] == []


def test_multi_sheet_metrics_keep_every_sheet_and_prefix_top_level_issues():
    runs = [
        _run("box.pml.yml", 1, "box_sheet_1", errors=["overlap"]),
        _run("box.pml.yml", 2, "box_sheet_2", warnings=["thin web"]),
    ]

    metrics = build_run_metrics(runs, BUILD)

    assert metrics["total_sheets"] == 2
    assert [sheet["job_name"] for sheet in metrics["sheets"]] == ["box_sheet_1", "box_sheet_2"]
    assert metrics["sheets"][0]["errors"] == ["overlap"]
    assert metrics["sheets"][1]["errors"] == []
    assert metrics["sheets"][1]["warnings"] == ["thin web"]
    assert "timing" not in metrics["sheets"][0]
    assert metrics["errors"] == ["sheet 1: overlap"]
    assert metrics["warnings"] == ["sheet 2: thin web"]
    assert metrics["build"]["source"] == "box.pml.yml"


def test_multi_source_metrics_label_issues_with_source():
    runs = [
        _run("door.pml.yml", 1, "door", errors=["too deep"]),
        _run("panel.pml.yml", 1, "panel"),
    ]

    metrics = build_run_metrics(runs, BUILD)

    assert metrics["total_sheets"] == 2
    assert [sheet["source"] for sheet in metrics["sheets"]] == ["door.pml.yml", "panel.pml.yml"]
    assert metrics["errors"] == ["door.pml.yml sheet 1: too deep"]
    assert metrics["build"]["sources"] == ["door.pml.yml", "panel.pml.yml"]
    assert "source" not in metrics["build"]


def test_write_run_outputs_writes_every_sheet_and_one_metrics_file(tmp_path: Path):
    runs = [
        SheetRun(
            source="box.pml.yml",
            sheet_index=index,
            job_name=f"box_sheet_{index}",
            result=_result(gcode_name=f"sheet_{index}.profile-3.17mm"),
        )
        for index in (1, 2)
    ]

    write_run_outputs(runs, tmp_path / "out", build_params=BUILD)

    names = sorted(path.name for path in (tmp_path / "out").iterdir())
    assert names == [
        "box_sheet_1.svg",
        "box_sheet_2.svg",
        "metrics.json",
        "sheet_1.profile-3.17mm.nc",
        "sheet_2.profile-3.17mm.nc",
    ]
    metrics = json.loads((tmp_path / "out" / "metrics.json").read_text())
    assert metrics["total_sheets"] == 2
