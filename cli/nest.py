#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from pml.yaml_parser import parse_nest_yaml, NestParseError
from pml.nest_parser import nest_job_to_api_params
from pml.formatter import format_pml
from pml.revision_header import format_pml_header
from nesting import nest_and_generate, nest_parts
from cli.project import (
    add_project_arg, resolve_input_path, resolve_output_dir, get_project_dir,
    parse_sheet_dimensions, DEFAULT_MARGIN_MM, DEFAULT_KERF_MM,
)


def generate_nest_scaffold(
    sheet_width: float,
    sheet_height: float,
    thickness: float,
    margin: float,
    kerf: float,
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

    nest = f"""{header}Nest:
  algorithm: maxrects

  Sheet:
    width: {sheet_width:.0f}mm
    height: {sheet_height:.0f}mm
    thickness: {thickness:.1f}mm

  kerf: {kerf}mm
  margin: {margin:.0f}mm

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
    kerf = args.kerf if args.kerf is not None else DEFAULT_KERF_MM

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
    print(f"  Kerf: {kerf}mm", file=sys.stderr)


def run_export_svg(pml_path: Path, output_dir: Path, theme: str) -> Path:
    from pml import parse_pml
    from adapters.ast_to_removal import ast_to_removal_intents
    from export.blueprint_svg import render_blueprint_svg

    pml_text = pml_path.read_text(encoding="utf-8")
    ast = parse_pml(pml_text)
    removal_intents = ast_to_removal_intents(ast)

    svg_string = render_blueprint_svg(ast, removal_intents=removal_intents, theme=theme)

    svg_path = output_dir / f"{pml_path.stem}.blueprint.{theme}.svg"
    svg_path.write_text(svg_string, encoding="utf-8")
    return svg_path


def main():
    parser = argparse.ArgumentParser(
        description="Run nesting from .nest.yml file and output PML layouts",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:

  python -m cli.nest --project my_table job.nest.yml

  python -m cli.nest job.nest.yml -o output/ --export-svg

  python -m cli.nest job.nest.yml -o output/ --export-svg --theme print

  python -m cli.nest --init_project --sheet 1220x2440 --thickness 19

  python -m cli.nest --project cabinet --init_project --sheet 1220x1220 --thickness 19

Output files:
  PML:  {prefix}_{N}.pml.yml (one per sheet)
  SVG:  {prefix}_{N}.blueprint.{theme}.svg (if --export-svg)
  JSON: manifest.json (nesting summary)
        """,
    )
    add_project_arg(parser)
    parser.add_argument("input", nargs="?", default=None, help="Input .nest.yml file")
    parser.add_argument(
        "-o", "--output",
        default=None,
        help="Output directory (default: project/output or current directory)"
    )
    parser.add_argument(
        "--prefix",
        default="sheet",
        help="Prefix for output files (default: sheet)"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose output"
    )

    export_group = parser.add_argument_group("export options")
    export_group.add_argument(
        "--export-svg",
        action="store_true",
        help="Export SVG blueprints for each sheet"
    )
    export_group.add_argument(
        "--theme",
        "-t",
        default="dark",
        choices=["dark", "light", "print"],
        help="SVG blueprint theme (default: dark)"
    )

    init_group = parser.add_argument_group("project initialization")
    init_group.add_argument(
        "--init_project",
        action="store_true",
        help="Generate a starter .nest.yml file",
    )
    init_group.add_argument(
        "--sheet",
        default=None,
        help="Physical sheet dimensions as WxH in mm (e.g., 1220x2440)",
    )
    init_group.add_argument(
        "--thickness",
        type=float,
        default=None,
        help="Material thickness in mm",
    )
    init_group.add_argument(
        "--margin",
        type=float,
        default=None,
        help=f"Margin/clamp zone in mm (default: {DEFAULT_MARGIN_MM})",
    )
    init_group.add_argument(
        "--kerf",
        type=float,
        default=None,
        help=f"Tool kerf in mm (default: {DEFAULT_KERF_MM})",
    )

    args = parser.parse_args()

    if args.init_project:
        init_project(args)
        return

    if not args.input:
        print("Error: input file required (or use --init_project)", file=sys.stderr)
        sys.exit(1)

    input_path = resolve_input_path(args.project, args.input)
    output_dir = resolve_output_dir(args.project, args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.verbose:
        print(f"Reading {input_path}...")

    try:
        source = input_path.read_text()
        job = parse_nest_yaml(source)
    except NestParseError as e:
        print(f"Parse error: {e}", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError:
        print(f"File not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    if args.verbose:
        print(f"Algorithm: {job.algorithm}")
        print(f"Sheet: {job.sheet_width_mm}mm x {job.sheet_height_mm}mm x {job.sheet_thickness_mm}mm")
        print(f"Kerf: {job.kerf_mm}mm, Margin: {job.margin_mm}mm")
        print(f"Parts: {len(job.parts)}")
        for part in job.parts:
            template_info = f" (template: {part.template})" if part.template else ""
            print(f"  - {part.quantity}x {part.name}: {part.width_mm}mm x {part.height_mm}mm{template_info}")

    if args.verbose:
        print("\nRunning nesting...")

    start_time = time.perf_counter()

    api_params = nest_job_to_api_params(job)
    api_params["output_format"] = "ast"

    result = nest_and_generate(**api_params)

    nest_time = time.perf_counter() - start_time

    if args.verbose:
        print(f"  Total sheets: {result['total_sheets']}")
        print(f"  Utilization: {result['utilization'] * 100:.1f}%")
        print(f"  Nesting time: {nest_time * 1000:.1f}ms")

    validation_params = nest_job_to_api_params(job)
    validation_params["validate"] = True
    validation_result = nest_parts(**validation_params)

    validation = validation_result["validation"]
    if not validation["is_valid"]:
        print("\nValidation FAILED:", file=sys.stderr)
        for error in validation["errors"]:
            print(f"  ERROR: {error['message']}", file=sys.stderr)
        sys.exit(1)

    if validation["warnings"]:
        for warning in validation["warnings"]:
            print(f"  WARNING: {warning['message']}")

    if args.verbose:
        print("\nWriting output files...")

    asts = result["output"]
    output_files = []
    svg_files = []

    for sheet_idx, ast in enumerate(asts):
        sheet_name = f"{args.prefix}_{sheet_idx + 1}"
        pml_path = output_dir / f"{sheet_name}.pml.yml"

        pml_content = format_pml(ast)

        header = format_pml_header()
        header += f"# {sheet_name}.pml.yml\n"
        header += f"# Generated from {input_path.name}\n"
        header += f"# Algorithm: {job.algorithm}\n"
        header += f"# Items: {len(ast.items)}\n"
        header += "\n"

        pml_path.write_text(header + pml_content)
        output_files.append(sheet_name)

        if args.verbose:
            print(f"  {pml_path.name}: {len(ast.items)} items")

        if args.export_svg:
            svg_path = run_export_svg(pml_path, output_dir, args.theme)
            svg_files.append(svg_path.name)
            if args.verbose:
                print(f"  {svg_path.name}")

    manifest = {
        "source": input_path.name,
        "algorithm": job.algorithm,
        "sheet": {
            "width_mm": job.sheet_width_mm,
            "height_mm": job.sheet_height_mm,
            "thickness_mm": job.sheet_thickness_mm,
        },
        "kerf_mm": job.kerf_mm,
        "margin_mm": job.margin_mm,
        "nesting": {
            "total_sheets": result["total_sheets"],
            "utilization": result["utilization"],
            "utilization_percent": f"{result['utilization'] * 100:.1f}%",
            "nesting_time_ms": round(nest_time * 1000, 2),
        },
        "output_files": {
            "pml": [f"{name}.pml.yml" for name in output_files],
        },
    }

    if svg_files:
        manifest["output_files"]["svg"] = svg_files

    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))

    if args.verbose:
        print(f"  {manifest_path.name}")

    print(f"\nGenerated {len(output_files)} PML.yml files in {output_dir}/")
    if svg_files:
        print(f"Generated {len(svg_files)} SVG blueprints")
    print(f"Utilization: {result['utilization'] * 100:.1f}%")


if __name__ == "__main__":
    main()
