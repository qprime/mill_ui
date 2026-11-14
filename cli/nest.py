#!/usr/bin/env python3

from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

from cam.compilation import CompilationContext, compilation_context, default_machine_name
from cli.project import (
    DEFAULT_MARGIN_MM,
    add_project_arg,
    get_project_dir,
    parse_sheet_dimensions,
    resolve_input_path,
    resolve_output_dir,
)
from config.machine_loader import Endmill, FeedsEntry, MachineConfig
from layout_ast.layout import MachiningClearance
from nesting import nest_and_generate
from pml.nest_parser import NestJob, nest_job_to_api_params
from pml.revision_header import format_pml_header
from pml.yaml_parser import NestParseError, parse_nest_yaml


def generate_nest_scaffold(
    sheet_width: float,
    sheet_height: float,
    thickness: float,
    margin: float,
    kerf: float | None,
) -> str:
    working_width = sheet_width - 2 * margin
    working_height = sheet_height - 2 * margin

    header = format_pml_header()
    header += f"# Physical sheet: {sheet_width:.0f}x{sheet_height:.0f}mm\n"
    header += f"# Working area: {working_width:.0f}x{working_height:.0f}mm\n"
    header += "#\n"
    header += "# Nesting auto-places parts within the working area.\n"
    header += "# Part sizes are bounding boxes - do NOT add kerf offsets.\n"
    header += "# The nesting algorithm accounts for kerf spacing automatically.\n"
    header += "\n"

    kerf_line = f"  kerf: {kerf}mm\n" if kerf is not None else ""
    nest = f"""{header}Nest:
  algorithm: maxrects

  Sheet:
    width: {sheet_width:.0f}mm
    height: {sheet_height:.0f}mm
    thickness: {thickness:.1f}mm

{kerf_line}  margin: {margin:.0f}mm

  parts:
    - name: TODO
      width: TODO
      height: TODO
      quantity: 1
"""
    return nest


def init_project(args) -> None:
    if not args.sheet:
        print("Error: --sheet is required with --init_project", file=sys.stderr)
        sys.exit(1)
    if args.thickness is None:
        print("Error: --thickness is required with --init_project", file=sys.stderr)
        sys.exit(1)

    try:
        sheet_width, sheet_height = parse_sheet_dimensions(args.sheet)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    margin = args.margin if args.margin is not None else DEFAULT_MARGIN_MM
    kerf = args.kerf

    if args.project:
        project_dir = get_project_dir(args.project)
        output_path = project_dir / "job.nest.yml"
    else:
        output_path = Path("job.nest.yml")

    if output_path.exists():
        print(f"Error: {output_path} already exists. Delete it first to regenerate.", file=sys.stderr)
        sys.exit(1)

    nest_content = generate_nest_scaffold(
        sheet_width=sheet_width,
        sheet_height=sheet_height,
        thickness=args.thickness,
        margin=margin,
        kerf=kerf,
    )

    if args.project:
        project_dir.mkdir(parents=True, exist_ok=True)

    output_path.write_text(nest_content, encoding="utf-8")
    print(f"Created {output_path}", file=sys.stderr)

    print(f"  Physical sheet: {sheet_width:.0f}x{sheet_height:.0f}mm", file=sys.stderr)
    print(f"  Margin: {margin:.0f}mm", file=sys.stderr)
    print(f"  Profile cutter: {str(kerf) + 'mm' if kerf is not None else 'machine preset'}", file=sys.stderr)


def nest_job(job: NestJob, *, machining_clearance: MachiningClearance | None = None) -> dict[str, Any]:
    api_params = nest_job_to_api_params(job)
    api_params["output_format"] = "ast"
    if machining_clearance is not None:
        api_params["machining_clearance"] = machining_clearance
    return nest_and_generate(**api_params)


def nest_machining_job(
    job: NestJob,
    *,
    endmills: list[Endmill] | None = None,
    feeds: list[FeedsEntry] | None = None,
    machine_config: MachineConfig | None = None,
    preset_path: Path | None = None,
) -> tuple[dict[str, Any], CompilationContext]:
    from cam.compilation import profile_machining_spec, profile_required_reach
    from nesting.template_expander import placement_to_items
    from nesting.types import NestedPart, PartSpec

    preview_items = []
    for part in job.parts:
        spec = PartSpec(
            name=part.name,
            width_mm=part.width_mm,
            height_mm=part.height_mm,
            quantity=1,
            template=part.template,
            template_params=part.template_params,
            shape=part.shape,
            shape_params=part.shape_params,
        )
        preview_items.extend(
            placement_to_items(NestedPart(part_spec=spec, x_mm=0, y_mm=0, rotated=False), job.sheet_thickness_mm)
        )
    machining = profile_machining_spec(job.machining, tuple(preview_items))
    context = compilation_context(
        job.material,
        job.kerf_mm if job.kerf_explicit else None,
        endmills=endmills,
        feeds=feeds,
        machine_config=machine_config,
        machining=machining,
        preset_path=preset_path,
        profile_reach_mm=profile_required_reach(tuple(preview_items), job.sheet_thickness_mm, packing=True),
    )
    job = replace(job, kerf_mm=context.clearance().profile_diameter_mm)
    result = nest_job(job, machining_clearance=context.clearance())
    if result["nesting_result"].unplaced_parts:
        names = [part.name for part in result["nesting_result"].unplaced_parts]
        raise ValueError(f"Nesting: parts do not fit the selected sheet: {names}")
    result["output"] = [
        replace(ast, sheet=replace(ast.sheet, material=job.material), machining=machining, machining_context=context)
        for ast in result["output"]
    ]
    return result, context


def main() -> None:
    from cam.pipeline import write_run_outputs
    from cli.mill import _compile, _load_machine, _load_tool_library, _report_outputs, _report_runs

    parser = argparse.ArgumentParser(description="Pack and machine authored .nest.yml in one source build")
    add_project_arg(parser)
    parser.add_argument("input", nargs="?")
    parser.add_argument("-o", "--output", default=None)
    parser.add_argument("--prefix", default=None)
    parser.add_argument("--machine", default=None)
    parser.add_argument("--preset", default=None)
    parser.add_argument("--endmills", default=None)
    parser.add_argument("--feeds", default=None)
    parser.add_argument("--kerf", type=float, default=None)
    parser.add_argument("--theme", default="dark")
    parser.add_argument("--no-svg", action="store_true")
    parser.add_argument("--export-svg", action="store_true")
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("--init_project", action="store_true")
    parser.add_argument("--sheet", default=None)
    parser.add_argument("--thickness", type=float, default=None)
    parser.add_argument("--margin", type=float, default=None)
    args = parser.parse_args()
    if args.init_project:
        init_project(args)
        return
    if not args.input:
        parser.error("supply the original .nest.yml source")
    source = resolve_input_path(args.project, args.input)
    try:
        job = parse_nest_yaml(source.read_text(encoding="utf-8"))
        if args.kerf is not None:
            job = replace(job, kerf_mm=args.kerf, kerf_explicit=True)
        machine = _load_machine(args.machine or default_machine_name())
        endmills, feeds = _load_tool_library(args)
        result, _ = nest_machining_job(
            job,
            machine_config=machine,
            endmills=endmills,
            feeds=feeds,
            preset_path=Path(args.preset) if args.preset else None,
        )
        runs = _compile(
            result["output"],
            source,
            args.prefix or source.name.removesuffix(".nest.yml"),
            kerf_mm=args.kerf,
            theme=args.theme,
            y_origin="back",
            generate_svg=not args.no_svg,
            machine_config=machine,
        )
        outputs = write_run_outputs(runs, resolve_output_dir(args.project, args.output))
        _report_runs(runs)
        _report_outputs(runs, outputs)
    except (ValueError, NestParseError) as exc:
        parser.exit(1, f"Error: {exc}\n")


if __name__ == "__main__":
    main()
