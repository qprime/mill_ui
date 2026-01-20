#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from pml.nest_parser import parse_nest_pml, nest_job_to_api_params, NestParseError
from pml.formatter import format_pml
from nesting import nest_and_generate, nest_parts
from cli.project import add_project_arg, resolve_input_path, resolve_output_dir


def run_export_stl(pml_path: Path, output_dir: Path, kerf_mm: float, quality: str) -> Path:
    from pml import parse_pml
    from layout_ast.layout import LayoutAST
    from adapters.ast_to_cad import items_to_shape_dicts
    from cad.export.stl import export_stl

    pml_text = pml_path.read_text(encoding="utf-8")
    ast = parse_pml(pml_text)
    shapes = items_to_shape_dicts(ast.items)

    stl_path = output_dir / f"{pml_path.stem}.stl"
    export_stl(
        shapes=shapes,
        sheet_thickness_mm=ast.sheet.thickness_mm,
        output_path=stl_path,
        kerf_mm=kerf_mm,
        quality=quality,
        include_floating_parts=True,
    )
    return stl_path


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
        description="Run nesting from .nest file and output PML layouts",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:

  python -m cli.nest --project my_table job.nest


  python -m cli.nest job.nest -o output/ --export-stl --export-svg


  python -m cli.nest --project my_table job.nest --export-stl --kerf 6.35


  python -m cli.nest job.nest -o output/ --export-svg --theme print

Output files:
  PML:  {prefix}_{N}.pml (one per sheet)
  STL:  {prefix}_{N}.stl (if --export-stl)
  SVG:  {prefix}_{N}.blueprint.{theme}.svg (if --export-svg)
  JSON: manifest.json (nesting summary)
        """,
    )
    add_project_arg(parser)
    parser.add_argument("input", help="Input .nest file")
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
        "--export-stl",
        action="store_true",
        help="Export STL models for each sheet"
    )
    export_group.add_argument(
        "--export-svg",
        action="store_true",
        help="Export SVG blueprints for each sheet"
    )
    export_group.add_argument(
        "--kerf",
        "-k",
        type=float,
        default=0.0,
        help="Kerf compensation in mm for STL export (default: 0)"
    )
    export_group.add_argument(
        "--quality",
        "-q",
        default="medium",
        choices=["low", "medium", "high"],
        help="STL mesh quality - low=16, medium=32, high=64 segments (default: medium)"
    )
    export_group.add_argument(
        "--theme",
        "-t",
        default="dark",
        choices=["dark", "light", "print"],
        help="SVG blueprint theme (default: dark)"
    )

    args = parser.parse_args()

    input_path = resolve_input_path(args.project, args.input)
    output_dir = resolve_output_dir(args.project, args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.verbose:
        print(f"Reading {input_path}...")

    try:
        source = input_path.read_text()
        job = parse_nest_pml(source)
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
    stl_files = []
    svg_files = []

    for sheet_idx, ast in enumerate(asts):
        sheet_name = f"{args.prefix}_{sheet_idx + 1}"
        pml_path = output_dir / f"{sheet_name}.pml"

        pml_content = format_pml(ast)

        header = f"# {sheet_name}.pml\n"
        header += f"# Generated from {input_path.name}\n"
        header += f"# Algorithm: {job.algorithm}\n"
        header += f"# Items: {len(ast.items)}\n"
        header += "\n"

        pml_path.write_text(header + pml_content)
        output_files.append(sheet_name)

        if args.verbose:
            print(f"  {pml_path.name}: {len(ast.items)} items")

        if args.export_stl:
            stl_path = run_export_stl(pml_path, output_dir, args.kerf, args.quality)
            stl_files.append(stl_path.name)
            if args.verbose:
                print(f"  {stl_path.name}")

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
            "pml": [f"{name}.pml" for name in output_files],
        },
    }

    if stl_files:
        manifest["output_files"]["stl"] = stl_files
    if svg_files:
        manifest["output_files"]["svg"] = svg_files

    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))

    if args.verbose:
        print(f"  {manifest_path.name}")

    print(f"\nGenerated {len(output_files)} PML files in {output_dir}/")
    if stl_files:
        print(f"Generated {len(stl_files)} STL files")
    if svg_files:
        print(f"Generated {len(svg_files)} SVG blueprints")
    print(f"Utilization: {result['utilization'] * 100:.1f}%")


if __name__ == "__main__":
    main()
