from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pml import parse_pml, PMLParseError
from pml.compositional_parser import parse_compositional_pml
from resolution.layout_resolver import resolve_layout
from layout_ast.layout import LayoutAST
from cam.pipeline import run_pipeline, write_pipeline_outputs, DEFAULT_TOOL_DB
from cli.project import add_project_arg, resolve_input_path, resolve_output_dir


def main():
    parser = argparse.ArgumentParser(
        description="Compile PML to G-code, SVG blueprint, and STL",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:

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
        required=True,
        help="Input file path (PML or JSON)",
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
        "--compositional",
        "-c",
        action="store_true",
        help="Parse as compositional PML (frame/inset/grid syntax)",
    )
    parser.add_argument(
        "--no-clean",
        action="store_true",
        help="Don't clean output directory before writing",
    )

    args = parser.parse_args()

    try:
        input_path = resolve_input_path(args.project, args.input)
        if not input_path.exists():
            print(f"Error: Input file not found: {input_path}", file=sys.stderr)
            sys.exit(1)
        if not input_path.is_file():
            print(f"Error: Input path is not a file: {input_path}", file=sys.stderr)
            sys.exit(1)

        input_suffix = input_path.suffix.lower()
        if input_suffix == ".json":
            ast = LayoutAST.from_json(str(input_path))
        elif input_suffix in (".pml", ".txt"):
            input_text = input_path.read_text(encoding="utf-8")
            if args.compositional:
                comp_ast = parse_compositional_pml(input_text)
                ast = resolve_layout(comp_ast)
            else:
                try:
                    ast = parse_pml(input_text)
                except PMLParseError as e:
                    if any(keyword in input_text for keyword in ["component", "frame", "inset", "grid", "split"]):
                        print(f"Hint: This looks like compositional PML. Try adding --compositional flag", file=sys.stderr)
                    raise
        else:
            print(f"Error: Unsupported input format: {input_suffix}", file=sys.stderr)
            print("Supported formats: .pml, .txt, .json", file=sys.stderr)
            sys.exit(1)

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
        )

        if result.errors:
            print(f"\nErrors:", file=sys.stderr)
            for error in result.errors:
                print(f"  - {error}", file=sys.stderr)

        if result.warnings:
            print(f"\nWarnings:", file=sys.stderr)
            for warning in result.warnings:
                print(f"  - {warning}", file=sys.stderr)

        output_dir = resolve_output_dir(args.project, args.out)
        job_name = input_path.stem

        outputs = write_pipeline_outputs(
            result,
            output_dir,
            job_name,
            write_stl=not args.no_stl,
            stl_quality=args.quality,
            kerf_mm=args.kerf,
            include_floating_parts=not args.no_floating_parts,
            clean_output_dir=not args.no_clean,
        )

        print(f"\nOutputs written to: {output_dir}", file=sys.stderr)
        for key, path in outputs.items():
            print(f"  {path.name}", file=sys.stderr)

        print(f"\nPipeline: {result.metrics['timing']['total_ms']:.1f}ms", file=sys.stderr)
        print(f"  Passes: {len(result.passes)}", file=sys.stderr)
        print(f"  Moves: {result.metrics['complexity']['total_moves']}", file=sys.stderr)

    except PMLParseError as e:
        print(f"PML Parse Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        if e.__class__.__name__ == "ParseError" and "compositional_parser" in str(type(e).__module__):
            print(f"Compositional PML Parse Error: {e}", file=sys.stderr)
            sys.exit(1)
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
