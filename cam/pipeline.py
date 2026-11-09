from __future__ import annotations

import json
import shutil
import time
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from adapters.ast_to_removal import ast_to_removal_intents
from adapters.removal_to_planner import removal_intents_to_planner_input
from cam.config import Config
from cam.model.machine import Machine
from cam.model.stock import Stock
from cam.moves import CutMove, RapidMove
from cam.planner.capabilities import audit_constraints
from cam.planner.passes import PassRecord, plan_passes
from cam.planner.passes.summary import summarise_gcode_file
from cam.planner.passes.tools import normalize_tool_entries
from cam.post.gcode import write_gcode
from config.machine_loader import (
    Endmill,
    FeedsEntry,
    MachineConfig,
    build_tool_db,
    load_machine_tool_db,
)
from core.constants import BACK_SVG_SUFFIX
from ir.removal_intent import RemovalIntent
from layout_ast.layout import LayoutAST, mirror_item_about_x
from pml.revision_header import build_provenance
from validation.removal_checks import (
    check_back_face_support,
    check_cross_face_web,
    check_depth_feasibility,
    check_edge_feature,
    check_heightfield,
    check_overlap,
    check_toolpath_clearance,
    check_working_area_bounds,
)
from validation.toolpath_checks import verify_passes_avoid_keepouts

NON_DETERMINISTIC_METRICS = frozenset({"timing"})
DEFAULT_SAFE_Z_MM = 6.0
PROFILE_CUT_THROUGH_MM = 0.2


@dataclass(frozen=True)
class GcodeFile:
    face: str
    passes: tuple[PassRecord, ...]


@dataclass(frozen=True)
class PipelineResult:
    ast: LayoutAST
    intents: list[RemovalIntent]
    passes: list[PassRecord]
    gcode: dict[str, str]
    svg: str | None
    metrics: dict[str, Any]
    errors: list[str]
    warnings: list[str]
    svg_back: str | None = None
    gcode_files: dict[str, GcodeFile] = field(default_factory=dict)


@dataclass(frozen=True)
class SheetRun:
    source: str
    sheet_index: int
    job_name: str
    result: PipelineResult


@dataclass(frozen=True)
class PipelineTiming:
    ir_ms: float = 0.0
    hints_ms: float = 0.0
    plan_ms: float = 0.0
    gcode_ms: float = 0.0
    svg_ms: float = 0.0
    total_ms: float = 0.0


@dataclass(frozen=True)
class FaceOutput:
    passes: list[PassRecord]
    gcode: dict[str, str]
    gcode_files: dict[str, GcodeFile]
    total_moves: int
    rapid_moves: int
    cut_moves: int
    hints_ms: float
    plan_ms: float
    gcode_ms: float


def _attach_surface_cooling(planner_input, ast: LayoutAST):
    from dataclasses import replace as _replace

    from cam.planner.planner_input import SurfaceCooling

    surface_map: dict[str, dict] = {}
    for item in ast.items:
        if item.params and "surface_cooling" in item.params:
            surface_map[item.shape_id or ""] = item.params["surface_cooling"]

    if not surface_map:
        return planner_input

    new_pockets = []
    for pocket in planner_input.pockets:
        sc_data = surface_map.get(pocket.id)
        if sc_data is not None:
            cooling = SurfaceCooling(
                stepover_pct=sc_data["stepover_pct"],
                direction=sc_data["direction"],
                cool_every=sc_data["cool_every"],
                cool_dwell_s=sc_data["cool_dwell_s"],
                start_depth_mm=sc_data.get("start_depth_mm", 0.0),
            )
            new_pockets.append(_replace(pocket, surface_cooling=cooling))
        else:
            new_pockets.append(pocket)

    return _replace(planner_input, pockets=tuple(new_pockets))


def _plan_and_emit_face(
    ast: LayoutAST,
    intents: list[RemovalIntent],
    *,
    gcode_prefix: str,
    kerf_mm: float,
    min_channel_width_mm: float,
    tools: list[Any],
    machine: Machine,
    stock: Stock,
    safe_z: float,
    park_z_mm: float | None,
    y_origin: str,
    errors: list[str],
    warnings: list[str],
    face: str,
) -> FaceOutput:
    hints_start = time.perf_counter()
    planner_input = removal_intents_to_planner_input(
        intents,
        kerf_width_mm=kerf_mm,
        min_channel_width_mm=min_channel_width_mm,
        warnings=warnings,
    )
    planner_input = _attach_surface_cooling(planner_input, ast)
    hints_ms = (time.perf_counter() - hints_start) * 1000

    plan_start = time.perf_counter()
    passes, _, planner_warnings = plan_passes(
        planner_input,
        config=Config(),
        tool_db=tools,
        machine=machine,
        stock=stock,
        safe_z=safe_z,
        profile_opts={"cut_through_mm": PROFILE_CUT_THROUGH_MM},
    )
    plan_ms = (time.perf_counter() - plan_start) * 1000
    warnings.extend(planner_warnings)

    if planner_input.keepouts:
        keepout_dicts = [k.to_dict() for k in planner_input.keepouts]
        keepout_result = verify_passes_avoid_keepouts(passes, keepout_dicts)
        if keepout_result.has_violations():
            for error_msg in keepout_result.format_errors():
                errors.append(f"Keepout violation: {error_msg}")

    gcode_start = time.perf_counter()
    gcode_dict: dict[str, str] = {}
    gcode_files: dict[str, GcodeFile] = {}
    total_moves = 0
    total_rapid_moves = 0
    total_cut_moves = 0

    margin_mm = ast.sheet.margin_mm

    if ast.sheet.gcode_output == "per-tool":
        tool_groups: dict[float, list[PassRecord]] = {}
        for p in passes:
            tool_groups.setdefault(p.setup.tool.diameter, []).append(p)

        for diameter, group in tool_groups.items():
            merged_moves: list = []
            for p in group:
                merged_moves.extend(p.moves)
            setup = group[0].setup
            gcode_files[f"{gcode_prefix}{diameter:.2f}mm"] = GcodeFile(face=face, passes=tuple(group))
            gcode_dict[f"{gcode_prefix}{diameter:.2f}mm"] = write_gcode(
                merged_moves,
                safe_z=setup.safe_z,
                machine=machine,
                sheet_height=ast.sheet.height_mm,
                y_origin=y_origin,
                margin_mm=margin_mm,
                park_z_mm=park_z_mm,
            )

            for move in merged_moves:
                total_moves += 1
                if isinstance(move, RapidMove):
                    total_rapid_moves += 1
                elif isinstance(move, CutMove):
                    total_cut_moves += 1
    else:
        for p in passes:
            gcode_files[f"{gcode_prefix}{p.op}-{p.setup.tool.diameter:.2f}mm"] = GcodeFile(face=face, passes=(p,))
            gcode_dict[f"{gcode_prefix}{p.op}-{p.setup.tool.diameter:.2f}mm"] = write_gcode(
                p.moves,
                safe_z=p.setup.safe_z,
                machine=machine,
                sheet_height=ast.sheet.height_mm,
                y_origin=y_origin,
                margin_mm=margin_mm,
                park_z_mm=park_z_mm,
            )

            total_moves += len(p.moves)
            for move in p.moves:
                if isinstance(move, RapidMove):
                    total_rapid_moves += 1
                elif isinstance(move, CutMove):
                    total_cut_moves += 1

    gcode_ms = (time.perf_counter() - gcode_start) * 1000

    return FaceOutput(
        passes=passes,
        gcode=gcode_dict,
        gcode_files=gcode_files,
        total_moves=total_moves,
        rapid_moves=total_rapid_moves,
        cut_moves=total_cut_moves,
        hints_ms=hints_ms,
        plan_ms=plan_ms,
        gcode_ms=gcode_ms,
    )


def run_pipeline(  # noqa: C901 — sequential pipeline orchestrator
    ast: LayoutAST,
    *,
    kerf_mm: float = 6.35,
    min_channel_width_mm: float = 12.0,
    tool_db: list[dict[str, Any]] | None = None,
    generate_svg: bool = True,
    svg_theme: str = "dark",
    y_origin: str = "back",
    machine_config: MachineConfig | None = None,
    endmill: Endmill | None = None,
    validate_machine_bounds: bool = True,
    endmills: list[Endmill] | None = None,
    feeds: list[FeedsEntry] | None = None,
) -> PipelineResult:
    if tool_db is not None:
        effective_tool_db = tool_db
    elif endmills is not None and feeds is not None:
        effective_tool_db = build_tool_db(endmills, feeds, ast.sheet.material)
    else:
        effective_tool_db = load_machine_tool_db(ast.sheet.material)
    tools = normalize_tool_entries(effective_tool_db)

    errors: list[str] = []
    warnings: list[str] = []

    ir_start = time.perf_counter()
    intents = ast_to_removal_intents(ast)
    _ir_ms = (time.perf_counter() - ir_start) * 1000

    non_surface_intents = [i for i in intents if "surface_pass_" not in i.region_id]

    constraint_audit = audit_constraints(intents)
    for error in constraint_audit.errors:
        errors.append(f"Constraint audit: {error}")
    for warning in constraint_audit.warnings:
        warnings.append(f"Constraint audit: {warning}")

    overlap_result = check_overlap(non_surface_intents)
    if overlap_result.has_issues():
        for issue in overlap_result.errors:
            errors.append(issue.message)
        for issue in overlap_result.warnings:
            warnings.append(issue.message)

    web_result = check_cross_face_web(non_surface_intents, ast.sheet.thickness_mm, ast.sheet.min_web_mm)
    for issue in web_result.errors:
        errors.append(issue.message)
    for issue in web_result.warnings:
        warnings.append(issue.message)

    v_angles: list[float] | None = [
        float(t["v_angle_deg"]) for t in effective_tool_db if t.get("kind") == "v" and t.get("v_angle_deg") is not None
    ] or None

    for intent in intents:
        depth_result = check_depth_feasibility(intent, ast.sheet.thickness_mm)
        if depth_result.has_issues():
            for issue in depth_result.errors:
                errors.append(issue.message)
            for issue in depth_result.warnings:
                warnings.append(issue.message)

        if intent.depth_profile.mode == "heightfield":
            heightfield_result = check_heightfield(intent, ast.sheet.thickness_mm)
            if heightfield_result.has_issues():
                for issue in heightfield_result.errors:
                    errors.append(issue.message)
                for issue in heightfield_result.warnings:
                    warnings.append(issue.message)

        edge_result = check_edge_feature(intent, ast.sheet.thickness_mm, available_v_angles=v_angles)
        if edge_result.has_issues():
            for issue in edge_result.errors:
                errors.append(issue.message)
            for issue in edge_result.warnings:
                warnings.append(issue.message)

        face_result = check_back_face_support(intent)
        for issue in face_result.errors:
            errors.append(issue.message)
        for issue in face_result.warnings:
            warnings.append(issue.message)

    tool_radius = kerf_mm / 2.0
    bounds_result = check_working_area_bounds(
        non_surface_intents,
        ast.sheet.working_width_mm,
        ast.sheet.working_height_mm,
        tool_radius_mm=tool_radius,
    )
    if bounds_result.has_issues():
        for issue in bounds_result.errors:
            errors.append(issue.message)
        for issue in bounds_result.warnings:
            warnings.append(issue.message)

    clearance_result = check_toolpath_clearance(intents, kerf_mm)
    if clearance_result.has_issues():
        for issue in clearance_result.errors:
            errors.append(issue.message)
        for issue in clearance_result.warnings:
            warnings.append(issue.message)

    exceeds_machine = False
    if machine_config is not None and validate_machine_bounds:
        from validation.machine_checks import check_sheet_fits_machine

        machine_result = check_sheet_fits_machine(ast, machine_config, endmill)
        if machine_result.status.value == "fail":
            exceeds_machine = True
            for failure in machine_result.failures:
                errors.append(f"Machine bounds: {failure}")
        elif machine_result.status.value == "warn":
            for failure in machine_result.failures:
                warnings.append(f"Machine bounds: {failure}")

    if ast.sheet.safe_z_mm is not None:
        safe_z = ast.sheet.safe_z_mm
    elif machine_config is not None:
        safe_z = machine_config.defaults.safe_z_mm
    else:
        safe_z = DEFAULT_SAFE_Z_MM
    park_z_mm = machine_config.defaults.park_z_mm if machine_config is not None else None

    constraint_summary = {
        entry.constraint: {
            "status": entry.status.value,
            "count": entry.count,
            "safety_critical": entry.safety_critical,
        }
        for entry in constraint_audit.entries
        if entry.count > 0
    }

    if constraint_audit.has_errors() or exceeds_machine:
        return PipelineResult(
            ast=ast,
            intents=intents,
            passes=[],
            gcode={},
            svg=None,
            metrics={
                "timing": {"ir_ms": round(_ir_ms, 2), "total_ms": round(_ir_ms, 2)},
                "constraint_audit": constraint_summary,
            },
            errors=errors,
            warnings=warnings,
        )

    stock = Stock(
        width=ast.sheet.width_mm,
        height=ast.sheet.height_mm,
        thickness=ast.sheet.thickness_mm,
    )
    machine = Machine(name="default_grbl")

    back_items = ast.face_items("back")
    front_ast = replace(ast, items=ast.face_items("front"))
    front_intents = [i for i in intents if i.face == "front"]

    back_ast: LayoutAST | None = None
    back_intents: list[RemovalIntent] = []
    if back_items:
        try:
            back_ast = replace(
                ast,
                items=tuple(mirror_item_about_x(item, ast.sheet.working_height_mm) for item in back_items),
            )
        except ValueError as exc:
            errors.append(f"Back-face mirror: {exc}")
            return PipelineResult(
                ast=ast,
                intents=intents,
                passes=[],
                gcode={},
                svg=None,
                metrics={"timing": {"ir_ms": round(_ir_ms, 2), "total_ms": round(_ir_ms, 2)}},
                errors=errors,
                warnings=warnings,
            )
        back_intents = ast_to_removal_intents(back_ast, warnings=warnings)

    face_runs: list[tuple[LayoutAST, list[RemovalIntent], str, str]] = []
    if back_ast is not None:
        face_runs.append((back_ast, back_intents, "back-", "back"))
    face_runs.append((front_ast, front_intents, "", "front"))

    outputs = [
        _plan_and_emit_face(
            face_ast,
            face_intents,
            gcode_prefix=prefix,
            kerf_mm=kerf_mm,
            min_channel_width_mm=min_channel_width_mm,
            tools=tools,
            machine=machine,
            stock=stock,
            safe_z=safe_z,
            park_z_mm=park_z_mm,
            y_origin=y_origin,
            errors=errors,
            warnings=warnings,
            face=face,
        )
        for face_ast, face_intents, prefix, face in face_runs
    ]

    passes = [record for output in outputs for record in output.passes]
    gcode_dict = {name: gcode for output in outputs for name, gcode in output.gcode.items()}
    gcode_files = {name: gcode_file for output in outputs for name, gcode_file in output.gcode_files.items()}
    total_moves = sum(output.total_moves for output in outputs)
    total_rapid_moves = sum(output.rapid_moves for output in outputs)
    total_cut_moves = sum(output.cut_moves for output in outputs)
    _hints_ms = sum(output.hints_ms for output in outputs)
    _plan_ms = sum(output.plan_ms for output in outputs)
    _gcode_ms = sum(output.gcode_ms for output in outputs)

    svg_string: str | None = None
    svg_back_string: str | None = None
    _svg_ms = 0.0
    if generate_svg:
        svg_start = time.perf_counter()
        try:
            from export.blueprint_svg import render_blueprint_svg

            svg_string = render_blueprint_svg(
                replace(front_ast, kerf_width_mm=float(kerf_mm)),
                front_intents,
                theme=svg_theme,
                y_origin=y_origin,
            )
            if back_ast is not None:
                svg_back_string = render_blueprint_svg(
                    replace(back_ast, kerf_width_mm=float(kerf_mm)),
                    back_intents,
                    theme=svg_theme,
                    y_origin=y_origin,
                    view_face="back",
                )
        except Exception as e:
            warnings.append(f"SVG generation failed: {e}")
        _svg_ms = (time.perf_counter() - svg_start) * 1000

    timing = PipelineTiming(
        ir_ms=_ir_ms,
        hints_ms=_hints_ms,
        plan_ms=_plan_ms,
        gcode_ms=_gcode_ms,
        svg_ms=_svg_ms,
        total_ms=_ir_ms + _hints_ms + _plan_ms + _gcode_ms + _svg_ms,
    )

    total_gcode_size = sum(len(gc) for gc in gcode_dict.values())
    total_gcode_lines = sum(gc.count("\n") for gc in gcode_dict.values())

    metrics = {
        "timing": {
            "ir_ms": round(timing.ir_ms, 2),
            "hints_ms": round(timing.hints_ms, 2),
            "plan_ms": round(timing.plan_ms, 2),
            "gcode_ms": round(timing.gcode_ms, 2),
            "svg_ms": round(timing.svg_ms, 2),
            "total_ms": round(timing.total_ms, 2),
        },
        "constraint_audit": constraint_summary,
        "complexity": {
            "total_moves": total_moves,
            "rapid_moves": total_rapid_moves,
            "cut_moves": total_cut_moves,
            "rapid_ratio": round(total_rapid_moves / total_moves, 3) if total_moves > 0 else 0,
        },
        "fidelity": {
            "tool_changes": len(passes),
            "passes": [
                {
                    "name": p.op,
                    "tool_diameter_mm": p.setup.tool.diameter,
                    "move_count": len(p.moves),
                }
                for p in passes
            ],
        },
        "output_size": {
            "total_bytes": total_gcode_size,
            "total_lines": total_gcode_lines,
            "files": {
                name: {
                    "bytes": len(gcode),
                    "lines": gcode.count("\n"),
                }
                for name, gcode in gcode_dict.items()
            },
        },
    }

    return PipelineResult(
        ast=ast,
        intents=intents,
        passes=passes,
        gcode=gcode_dict,
        svg=svg_string,
        svg_back=svg_back_string,
        metrics=metrics,
        errors=errors,
        warnings=warnings,
        gcode_files=gcode_files,
    )


def _strip_non_deterministic(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _strip_non_deterministic(v) for k, v in value.items() if k not in NON_DETERMINISTIC_METRICS}
    if isinstance(value, list):
        return [_strip_non_deterministic(v) for v in value]
    return value


def run_sheets(
    asts: Sequence[LayoutAST],
    *,
    source: str,
    job_stem: str,
    **pipeline_kwargs: Any,
) -> list[SheetRun]:
    multi_sheet = len(asts) > 1
    runs: list[SheetRun] = []
    for sheet_index, ast in enumerate(asts, start=1):
        result = run_pipeline(ast, **pipeline_kwargs)
        job_name = job_stem
        if multi_sheet:
            prefix = f"sheet_{sheet_index}."
            result = replace(
                result,
                gcode={f"{prefix}{name}": gcode for name, gcode in result.gcode.items()},
                gcode_files={f"{prefix}{name}": gcode_file for name, gcode_file in result.gcode_files.items()},
            )
            job_name = f"{job_stem}_sheet_{sheet_index}"
        runs.append(SheetRun(source=source, sheet_index=sheet_index, job_name=job_name, result=result))
    return runs


def _sheet_label(run: SheetRun, multi_source: bool) -> str:
    return f"{run.source} sheet {run.sheet_index}" if multi_source else f"sheet {run.sheet_index}"


def build_run_metrics(runs: Sequence[SheetRun], build_params: dict[str, Any] | None = None) -> dict[str, Any]:
    sources = list(dict.fromkeys(run.source for run in runs))
    build = dict(build_params or {})
    if len(sources) == 1:
        build["source"] = sources[0]
    else:
        build["sources"] = sources

    metrics: dict[str, Any]
    if len(runs) == 1:
        result = runs[0].result
        metrics = {
            **_strip_non_deterministic(result.metrics),
            "errors": list(result.errors),
            "warnings": list(result.warnings),
        }
    else:
        multi_source = len(sources) > 1
        metrics = {
            "total_sheets": len(runs),
            "sheets": [
                {
                    "source": run.source,
                    "sheet_index": run.sheet_index,
                    "job_name": run.job_name,
                    **_strip_non_deterministic(run.result.metrics),
                    "errors": list(run.result.errors),
                    "warnings": list(run.result.warnings),
                }
                for run in runs
            ],
            "errors": [f"{_sheet_label(run, multi_source)}: {e}" for run in runs for e in run.result.errors],
            "warnings": [f"{_sheet_label(run, multi_source)}: {w}" for run in runs for w in run.result.warnings],
        }
    metrics["build"] = build
    metrics["provenance"] = build_provenance()
    return metrics


def _feature_counts(intents: Sequence[RemovalIntent]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for intent in intents:
        if not intent.hint_type:
            continue
        is_waste = intent.hint_type == "profile" and intent.region_id.startswith("profile_waste_")
        key = "waste_cut" if is_waste else intent.hint_type
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def _sheet_machining_summary(result: PipelineResult) -> dict[str, Any]:
    sheet = result.ast.sheet
    files = [
        summarise_gcode_file(
            f"{name}.nc",
            gcode_file.passes,
            profile_intents=[
                intent
                for intent in result.intents
                if intent.face == gcode_file.face and intent.hint_type == "profile"
            ],
            cut_through_mm=PROFILE_CUT_THROUGH_MM,
        )
        for name, gcode_file in result.gcode_files.items()
    ]
    return {
        "stock": {
            "width_mm": sheet.width_mm,
            "height_mm": sheet.height_mm,
            "thickness_mm": sheet.thickness_mm,
            "material": sheet.material,
        },
        "files": files,
        "total_runtime_min": round(sum(entry["estimated_runtime_min"] for entry in files), 1),
        "feature_counts": _feature_counts(result.intents),
        "safe_z_mm": result.passes[0].setup.safe_z if result.passes else None,
    }


def build_machining_summary(runs: Sequence[SheetRun], kerf_mm: float | None = None) -> dict[str, Any]:
    if len(runs) == 1:
        return {**_sheet_machining_summary(runs[0].result), "kerf_mm": kerf_mm}
    sheets = [
        {
            "source": run.source,
            "sheet_index": run.sheet_index,
            "job_name": run.job_name,
            **_sheet_machining_summary(run.result),
        }
        for run in runs
    ]
    return {
        "total_sheets": len(runs),
        "sheets": sheets,
        "total_runtime_min": round(sum(sheet["total_runtime_min"] for sheet in sheets), 1),
        "kerf_mm": kerf_mm,
    }


def _write_sheet_artifacts(run: SheetRun, output_dir: Path) -> dict[str, Path]:
    outputs: dict[str, Path] = {}
    result = run.result

    for pass_name, gcode in result.gcode.items():
        gcode_path = output_dir / f"{pass_name}.nc"
        gcode_path.write_text(gcode)
        outputs[f"gcode_{pass_name}"] = gcode_path

    if result.svg is not None:
        svg_path = output_dir / f"{run.job_name}.svg"
        svg_path.write_text(result.svg, encoding="utf-8")
        outputs[f"svg_{run.job_name}"] = svg_path

    if result.svg_back is not None:
        svg_back_path = output_dir / f"{run.job_name}{BACK_SVG_SUFFIX}"
        svg_back_path.write_text(result.svg_back, encoding="utf-8")
        outputs[f"svg_back_{run.job_name}"] = svg_back_path

    return outputs


def write_run_outputs(
    runs: Sequence[SheetRun],
    output_dir: Path,
    *,
    clean_output_dir: bool = True,
    build_params: dict[str, Any] | None = None,
) -> dict[str, Path]:
    if clean_output_dir and output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    outputs: dict[str, Path] = {}
    for run in runs:
        outputs.update(_write_sheet_artifacts(run, output_dir))

    metrics_path = output_dir / "metrics.json"
    metrics_path.write_text(json.dumps(build_run_metrics(runs, build_params), indent=2))
    outputs["metrics"] = metrics_path

    summary_path = output_dir / "machining_summary.json"
    kerf_mm = (build_params or {}).get("kerf_mm")
    summary_path.write_text(json.dumps(build_machining_summary(runs, kerf_mm), indent=2))
    outputs["machining_summary"] = summary_path

    return outputs
