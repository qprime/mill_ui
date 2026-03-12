from __future__ import annotations

import shutil
import time
from dataclasses import dataclass, replace
from datetime import UTC
from pathlib import Path
from typing import Any

from adapters.ast_to_removal import ast_to_removal_intents
from adapters.removal_to_planner import removal_intents_to_planner_input
from cam.config import Config
from cam.model.machine import Machine
from cam.model.material import Material
from cam.model.stock import Stock
from cam.moves import CutMove, RapidMove
from cam.planner.capabilities import audit_constraints
from cam.planner.passes import PassRecord, plan_passes
from cam.planner.passes.tools import normalize_tool_entries
from cam.post.gcode import write_gcode
from config.machine_loader import Endmill, FeedsEntry, MachineConfig, build_tool_db
from ir.removal_intent import Bounds2D, RemovalIntent
from layout_ast.layout import LayoutAST
from validation.removal_checks import (
    check_depth_feasibility,
    check_edge_feature,
    check_overlap,
    check_toolpath_clearance,
    check_working_area_bounds,
)
from validation.toolpath_checks import verify_passes_avoid_keepouts

DEFAULT_TOOL_DB = [
    {
        "name": "1_8_endmill",
        "diameter": 3.175,
        "kind": "flat",
        "rpm": 14000,
        "feed_xy": 900,
        "feed_z": 300,
    },
    {
        "name": "1_4_endmill",
        "diameter": 6.35,
        "kind": "flat",
        "rpm": 12000,
        "feed_xy": 800,
        "feed_z": 280,
    },
    {
        "name": "3_8_endmill",
        "diameter": 9.525,
        "kind": "flat",
        "rpm": 10000,
        "feed_xy": 700,
        "feed_z": 250,
    },
    {
        "name": "90_degree_vbit",
        "diameter": 12.7,
        "kind": "v",
        "rpm": 16000,
        "feed_xy": 1200,
        "feed_z": 400,
        "v_angle_deg": 90,
    },
    {
        "name": "6mm_roundover",
        "diameter": 25.4,
        "kind": "roundover",
        "rpm": 16000,
        "feed_xy": 1500,
        "feed_z": 500,
        "roundover_radius_mm": 6.0,
    },
]


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


@dataclass(frozen=True)
class PipelineTiming:
    ir_ms: float = 0.0
    hints_ms: float = 0.0
    plan_ms: float = 0.0
    gcode_ms: float = 0.0
    svg_ms: float = 0.0
    total_ms: float = 0.0


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


def run_pipeline(
    ast: LayoutAST,
    *,
    kerf_mm: float = 6.35,
    min_channel_width_mm: float = 12.0,
    tool_db: list[dict[str, Any]] | None = None,
    safe_z: float = 6.0,
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
        effective_tool_db = DEFAULT_TOOL_DB
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

        edge_result = check_edge_feature(intent, ast.sheet.thickness_mm, available_v_angles=v_angles)
        if edge_result.has_issues():
            for issue in edge_result.errors:
                errors.append(issue.message)
            for issue in edge_result.warnings:
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

    if machine_config is not None and validate_machine_bounds:
        from validation.machine_checks import check_job_fits_machine

        sheet = ast.sheet
        margin = sheet.margin_mm
        job_bounds = Bounds2D(
            x_min=margin,
            x_max=sheet.width_mm - margin,
            y_min=margin,
            y_max=sheet.height_mm - margin,
        )

        machine_result = check_job_fits_machine(job_bounds, machine_config, endmill)
        if machine_result.status.value == "fail":
            for failure in machine_result.failures:
                errors.append(f"Machine bounds: {failure}")
        elif machine_result.status.value == "warn":
            for failure in machine_result.failures:
                warnings.append(f"Machine bounds: {failure}")

    park_z_mm: float | None = None
    if machine_config is not None and safe_z == 6.0:
        safe_z = machine_config.defaults.safe_z_mm
    if machine_config is not None:
        park_z_mm = machine_config.defaults.park_z_mm

    if constraint_audit.has_errors():
        constraint_summary = {
            entry.constraint: {
                "status": entry.status.value,
                "count": entry.count,
                "safety_critical": entry.safety_critical,
            }
            for entry in constraint_audit.entries
            if entry.count > 0
        }
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

    hints_start = time.perf_counter()
    planner_input = removal_intents_to_planner_input(
        intents,
        kerf_width_mm=kerf_mm,
        min_channel_width_mm=min_channel_width_mm,
    )
    planner_input = _attach_surface_cooling(planner_input, ast)
    _hints_ms = (time.perf_counter() - hints_start) * 1000

    stock = Stock(
        width=ast.sheet.width_mm,
        height=ast.sheet.height_mm,
        thickness=ast.sheet.thickness_mm,
    )
    material = Material(name=ast.sheet.material)
    machine = Machine(name="default_grbl")

    plan_start = time.perf_counter()
    passes, _ = plan_passes(
        planner_input,
        config=Config(),
        tool_db=tools,
        material=material,
        machine=machine,
        stock=stock,
        safe_z=safe_z,
        profile_opts={"cut_through_mm": 0.2},
    )
    _plan_ms = (time.perf_counter() - plan_start) * 1000

    if planner_input.keepouts:
        keepout_dicts = [k.to_dict() for k in planner_input.keepouts]
        keepout_result = verify_passes_avoid_keepouts(passes, keepout_dicts)
        if keepout_result.has_violations():
            for error_msg in keepout_result.format_errors():
                errors.append(f"Keepout violation: {error_msg}")

    gcode_start = time.perf_counter()
    gcode_dict: dict[str, str] = {}
    total_moves = 0
    total_rapid_moves = 0
    total_cut_moves = 0

    margin_mm = ast.sheet.margin_mm
    gcode_output = ast.sheet.gcode_output

    if gcode_output == "per-tool":
        tool_groups: dict[float, list[PassRecord]] = {}
        for p in passes:
            d = p.setup.tool.diameter
            tool_groups.setdefault(d, []).append(p)

        for diameter, group in tool_groups.items():
            merged_moves: list = []
            for p in group:
                merged_moves.extend(p.moves)
            setup = group[0].setup
            gcode = write_gcode(
                merged_moves,
                safe_z=setup.safe_z,
                machine=machine,
                sheet_height=ast.sheet.height_mm,
                y_origin=y_origin,
                margin_mm=margin_mm,
                park_z_mm=park_z_mm,
            )
            pass_name = f"{diameter:.2f}mm"
            gcode_dict[pass_name] = gcode

            for move in merged_moves:
                total_moves += 1
                if isinstance(move, RapidMove):
                    total_rapid_moves += 1
                elif isinstance(move, CutMove):
                    total_cut_moves += 1
    else:
        for p in passes:
            gcode = write_gcode(
                p.moves,
                safe_z=p.setup.safe_z,
                machine=machine,
                sheet_height=ast.sheet.height_mm,
                y_origin=y_origin,
                margin_mm=margin_mm,
                park_z_mm=park_z_mm,
            )

            tool_diameter = p.setup.tool.diameter
            pass_name = f"{p.op}-{tool_diameter:.2f}mm"
            gcode_dict[pass_name] = gcode

            total_moves += len(p.moves)
            for move in p.moves:
                if isinstance(move, RapidMove):
                    total_rapid_moves += 1
                elif isinstance(move, CutMove):
                    total_cut_moves += 1

    _gcode_ms = (time.perf_counter() - gcode_start) * 1000

    svg_string: str | None = None
    _svg_ms = 0.0
    if generate_svg:
        svg_start = time.perf_counter()
        try:
            from export.blueprint_svg import render_blueprint_svg

            ast_with_kerf = replace(ast, kerf_width_mm=float(kerf_mm))
            svg_string = render_blueprint_svg(ast_with_kerf, intents, theme=svg_theme, y_origin=y_origin)
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

    constraint_summary = {
        entry.constraint: {
            "status": entry.status.value,
            "count": entry.count,
            "safety_critical": entry.safety_critical,
        }
        for entry in constraint_audit.entries
        if entry.count > 0
    }

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
        metrics=metrics,
        errors=errors,
        warnings=warnings,
    )


def write_pipeline_outputs(
    result: PipelineResult,
    output_dir: Path,
    job_name: str,
    *,
    clean_output_dir: bool = True,
    build_params: dict[str, Any] | None = None,
) -> dict[str, Path]:
    if clean_output_dir and output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    outputs: dict[str, Path] = {}

    for pass_name, gcode in result.gcode.items():
        gcode_path = output_dir / f"{job_name}.{pass_name}.nc"
        gcode_path.write_text(gcode)
        outputs[f"gcode_{pass_name}"] = gcode_path

    if result.svg is not None:
        svg_path = output_dir / f"{job_name}.svg"
        svg_path.write_text(result.svg, encoding="utf-8")
        outputs["svg"] = svg_path

    import json
    from datetime import datetime

    metrics_with_build = dict(result.metrics)
    if build_params:
        metrics_with_build["build"] = build_params
    metrics_with_build["timestamp"] = datetime.now(UTC).isoformat()

    metrics_path = output_dir / "metrics.json"
    metrics_path.write_text(json.dumps(metrics_with_build, indent=2))
    outputs["metrics"] = metrics_path

    return outputs
