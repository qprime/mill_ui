from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pml.compositional_parser import parse_compositional_pml, ParseError
from resolution.layout_resolver import resolve_layout
from layout_ast.layout import LayoutAST
from cam.pipeline import run_pipeline, write_pipeline_outputs, DEFAULT_TOOL_DB
from cli.project import add_project_arg, resolve_input_path, resolve_output_dir, get_project_dir


def collect_input_files(project: str | None, input_arg: str | None) -> list[Path]:
    if input_arg:
        input_path = resolve_input_path(project, input_arg)
        if input_path.is_file():
            return [input_path]
        if input_path.is_dir():
            return sorted(input_path.glob("*.pml"))
        print(f"Error: Input not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    if project:
        project_dir = get_project_dir(project)
        pml_files = sorted(project_dir.glob("*.pml"))
        if pml_files:
            return pml_files
        print(f"Error: No .pml files found in {project_dir}", file=sys.stderr)
        sys.exit(1)

    print("Error: --input or --project required", file=sys.stderr)
    sys.exit(1)


def process_file(input_path: Path, output_dir: Path, args) -> None:
    input_suffix = input_path.suffix.lower()
    if input_suffix == ".json":
        ast = LayoutAST.from_json(str(input_path))
    elif input_suffix in (".pml", ".txt"):
        input_text = input_path.read_text(encoding="utf-8")
        comp_ast = parse_compositional_pml(input_text)
        ast = resolve_layout(comp_ast)
    else:
        print(f"Error: Unsupported input format: {input_suffix}", file=sys.stderr)
        return

    print(f"Compiling: {input_path.name}", file=sys.stderr)
    print(f"  Sheet: {ast.sheet.width_mm}x{ast.sheet.height_mm}x{ast.sheet.thickness_mm}mm", file=sys.stderr)
    print(f"  Items: {len(ast.items)}", file=sys.stderr)

    result = run_pipeline(
        ast,
        kerf_mm=args.kerf,
        tool_db=DEFAULT_TOOL_DB,
        generate_svg=not args.no_svg,
        svg_theme=args.theme,
        generate_stl=not args.no_stl,
        stl_quality=args.quality,
        include_floating_parts=not args.no_floating_parts,
        y_origin=args.y_origin,
    )

    if result.errors:
        print(f"\nErrors:", file=sys.stderr)
        for error in result.errors:
            print(f"  - {error}", file=sys.stderr)

    if result.warnings:
        print(f"\nWarnings:", file=sys.stderr)
        for warning in result.warnings:
            print(f"  - {warning}", file=sys.stderr)

    job_name = input_path.stem

    outputs = write_pipeline_outputs(
        result,
        output_dir,
        job_name,
        write_stl=not args.no_stl,
        stl_quality=args.quality,
        kerf_mm=args.kerf,
        include_floating_parts=not args.no_floating_parts,
        clean_output_dir=False,
    )

    print(f"  Outputs:", file=sys.stderr)
    for key, path in outputs.items():
        print(f"    {path.name}", file=sys.stderr)

    print(f"  Pipeline: {result.metrics['timing']['total_ms']:.1f}ms", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(
        description="Compile PML to G-code, SVG blueprint, and STL",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:

  python -m cli.mill --project my_table

  python -m cli.mill --project my_table --input door.pml

  python -m cli.mill --input /path/to/layout.pml --out output/

  python -m cli.mill --project cabinet --input panel.pml --kerf 3.175 --no-stl

Output files:
  {basename}.{op}-{tool_diameter}mm.nc   G-code per pass
  {basename}.svg              Blueprint drawing
  {basename}.stl              3D preview model
  metrics.json                Pipeline metrics
        """,
    )

    add_project_arg(parser)
    parser.add_argument(
        "--input",
        "-i",
        default=None,
        help="Input file or directory (default: project dir, processes all .pml files)",
    )
    parser.add_argument(
        "--out",
        "-o",
        default=None,
        help="Output directory (default: <project>/output/ or current dir)",
    )
    parser.add_argument(
        "--kerf",
        "-k",
        type=float,
        default=6.35,
        help="Tool kerf in mm (default: 6.35)",
    )
    parser.add_argument(
        "--theme",
        "-t",
        default="dark",
        choices=["dark", "light", "print"],
        help="Blueprint theme (default: dark)",
    )
    parser.add_argument(
        "--quality",
        "-q",
        default="medium",
        choices=["low", "medium", "high"],
        help="STL mesh quality (default: medium)",
    )
    parser.add_argument(
        "--no-svg",
        action="store_true",
        help="Skip SVG blueprint generation",
    )
    parser.add_argument(
        "--no-stl",
        action="store_true",
        help="Skip STL model generation",
    )
    parser.add_argument(
        "--no-floating-parts",
        action="store_true",
        help="Exclude floating parts (cutouts) from STL",
    )
    parser.add_argument(
        "--no-clean",
        action="store_true",
        help="Don't clean output directory before writing",
    )
    parser.add_argument(
        "--y-origin",
        default="front",
        choices=["front", "back"],
        help="Y=0 reference: front (operator side) or back (default: front)",
    )

    args = parser.parse_args()

    try:
        input_files = collect_input_files(args.project, args.input)
        if not input_files:
            print("Error: No input files found", file=sys.stderr)
            sys.exit(1)

        output_dir = resolve_output_dir(args.project, args.out)

        if not args.no_clean and output_dir.exists():
            resolved = output_dir.resolve()
            cwd = Path.cwd().resolve()
            dangerous = (
                resolved == cwd
                or cwd.is_relative_to(resolved)
                or resolved.name in (".", "..")
                or str(resolved) in ("/", "/home", "/tmp")
            )
            if dangerous:
                print(f"Error: Refusing to clean dangerous directory: {output_dir}", file=sys.stderr)
                sys.exit(1)
            import shutil
            shutil.rmtree(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        for input_path in input_files:
            process_file(input_path, output_dir, args)

    except ParseError as e:
        print(f"PML Parse Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
