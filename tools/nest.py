#!/usr/bin/env python3
"""Nest CLI: Run nesting from .nest.pml files and output PML layouts.

Usage:
    PYTHONPATH=. python3 tools/nest.py input.nest.pml -o output_dir/

This tool:
1. Parses the .nest.pml specification
2. Runs the nesting algorithm (maxrects or guillotine)
3. Outputs one .pml file per sheet with explicit placements
4. Outputs a manifest.json with nesting summary
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from pml.nest_parser import parse_nest_pml, nest_job_to_api_params, NestParseError
from pml.formatter import format_pml
from nesting import nest_and_generate, nest_parts
from nesting.layout_generator import sheet_layout_to_ast


def main():
    parser = argparse.ArgumentParser(
        description="Run nesting from .nest.pml and output PML layouts"
    )
    parser.add_argument("input", help="Input .nest.pml file")
    parser.add_argument(
        "-o", "--output",
        default=".",
        help="Output directory (default: current directory)"
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

    args = parser.parse_args()

    input_path = Path(args.input)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Read and parse input
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

    # Run nesting
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

    # Also run validation
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

    # Output PML files
    if args.verbose:
        print("\nWriting output files...")

    asts = result["output"]
    output_files = []

    for sheet_idx, ast in enumerate(asts):
        sheet_name = f"{args.prefix}_{sheet_idx + 1}"
        pml_path = output_dir / f"{sheet_name}.pml"

        # Format AST as PML
        pml_content = format_pml(ast)

        # Add header comment
        header = f"# {sheet_name}.pml\n"
        header += f"# Generated from {input_path.name}\n"
        header += f"# Algorithm: {job.algorithm}\n"
        header += f"# Items: {len(ast.items)}\n"
        header += "\n"

        pml_path.write_text(header + pml_content)
        output_files.append(sheet_name)

        if args.verbose:
            print(f"  {pml_path.name}: {len(ast.items)} items")

    # Write manifest
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
        "output_files": [f"{name}.pml" for name in output_files],
    }

    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))

    if args.verbose:
        print(f"  {manifest_path.name}")

    print(f"\nGenerated {len(output_files)} PML files in {output_dir}/")
    print(f"Utilization: {result['utilization'] * 100:.1f}%")


if __name__ == "__main__":
    main()
