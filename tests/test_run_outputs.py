from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from cam.model.machine import Machine
from cam.model.stock import Stock
from cam.moves import CutMove, RapidMove
from cam.pipeline import (
    GcodeFile,
    PipelineResult,
    SheetRun,
    build_machining_summary,
    build_run_metrics,
    write_run_outputs,
)
from cam.planner.passes import PassAccumulator, PassRecord
from cam.planner.passes.tools import ToolSelection
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
        "machining_summary.json",
        "metrics.json",
        "sheet_1.profile-3.17mm.nc",
        "sheet_2.profile-3.17mm.nc",
    ]
    metrics = json.loads((tmp_path / "out" / "metrics.json").read_text())
    assert metrics["total_sheets"] == 2


def _profile_pass() -> PassRecord:
    tool = ToolSelection(name="t", diameter=3.175, kind="flat", rpm=18000, feed_xy=1200.0, feed_z=300.0)
    acc = PassAccumulator(
        machine=Machine(), stock=Stock(width=300, height=200, thickness=19), safe_z=3.0, prime_spindle=False
    )
    record = acc.get_record("profile", tool)
    record.add_moves([RapidMove(x=0.0, y=0.0, z=3.0), CutMove(z=0.0, feed=300.0), CutMove(x=1200.0, feed=1200.0)])
    return record


def _summary_run(sheet_index: int, job_name: str, gcode_name: str) -> SheetRun:
    result = _result(gcode_name=gcode_name)
    gcode_files = {gcode_name: GcodeFile(face="front", passes=(_profile_pass(),))}
    return SheetRun(
        source="box.pml.yml",
        sheet_index=sheet_index,
        job_name=job_name,
        result=replace(result, gcode_files=gcode_files),
    )


def test_single_sheet_machining_summary_lists_files_and_total_runtime():
    summary = build_machining_summary([_summary_run(1, "box", "profile-3.17mm")])

    assert summary["files"] == [
        {
            "filename": "profile-3.17mm.nc",
            "operation": "profile",
            "tool_diameter_mm": 3.175,
            "estimated_runtime_min": 1.0,
        }
    ]
    assert summary["total_runtime_min"] == 1.0


def test_multi_sheet_machining_summary_keeps_every_sheet_and_sums_runtime():
    runs = [
        _summary_run(1, "box_sheet_1", "sheet_1.profile-3.17mm"),
        _summary_run(2, "box_sheet_2", "sheet_2.profile-3.17mm"),
    ]

    summary = build_machining_summary(runs)

    assert summary["total_sheets"] == 2
    assert [sheet["job_name"] for sheet in summary["sheets"]] == ["box_sheet_1", "box_sheet_2"]
    assert summary["sheets"][1]["files"][0]["filename"] == "sheet_2.profile-3.17mm.nc"
    assert summary["total_runtime_min"] == 2.0
