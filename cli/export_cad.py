"""CLI tool for exporting CAD models (STL/STEP).

Usage:
    python -m cli.export_cad --input door.pml --format stl --out out/
    python -m cli.export_cad --input door.json --format step --out out/
    python -m cli.export_cad --input door.pml --format both --out out/
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pml import parse_pml, PMLParseError
from pml.compositional_parser import parse_compositional_pml
from resolution.layout_resolver import resolve_layout
from layout_ast.layout import LayoutAST
from adapters.ast_to_cad import items_to_shape_dicts


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Export CAD models (STL/STEP)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Export STL
  python -m cli.export_cad --input door.pml --format stl --out out/

  # Export STEP
  python -m cli.export_cad --input door.json --format step --out out/

  # Export both STL and STEP
  python -m cli.export_cad --input door.pml --format both --out out/

  # With kerf compensation
  python -m cli.export_cad --input door.pml --format stl --kerf 3.175 --out out/

Output file naming:
  STL: {basename}.stl (plus {basename}_part_N.stl for floating parts)
  STEP: {basename}.step
        """,
    )

    parser.add_argument(
        "--input",
        "-i",
        required=True,
        help="Input file path (PML or JSON)",
    )
    parser.add_argument(
        "--format",
        "-f",
        default="stl",
        choices=["stl", "step", "both"],
        help="Output format (default: stl)",
    )
    parser.add_argument(
        "--out",
        "-o",
        default=".",
        help="Output directory (default: current directory)",
    )
    parser.add_argument(
        "--kerf",
        "-k",
        type=float,
        default=None,
        help="Kerf compensation in mm (default: none)",
    )
    parser.add_argument(
        "--no-floating-parts",
        action="store_true",
        help="Exclude floating parts from STL export",
    )
    parser.add_argument(
        "--include-sheet",
        action="store_true",
        help="Include full sheet in STL export (default: parts only)",
    )
    parser.add_argument(
        "--compositional",
        "-c",
        action="store_true",
        help="Parse as compositional PML (frame/inset/grid syntax)",
    )
    parser.add_argument(
        "--mesh-tolerance",
        type=float,
        default=0.3,
        help="STL mesh tolerance in mm (default: 0.3)",
    )
    parser.add_argument(
        "--angular-tolerance",
        type=float,
        default=5.0,
        help="STL angular tolerance in degrees (default: 5.0)",
    )

    args = parser.parse_args()

    try:
        # Validate input file exists
        input_path = Path(args.input)
        if not input_path.exists():
            print(f"Error: Input file not found: {args.input}", file=sys.stderr)
            sys.exit(1)
        if not input_path.is_file():
            print(f"Error: Input path is not a file: {args.input}", file=sys.stderr)
            sys.exit(1)

        # Parse input to LayoutAST
        input_suffix = input_path.suffix.lower()
        if input_suffix == ".json":
            ast = LayoutAST.from_json(str(input_path))
        elif input_suffix == ".pml" or input_suffix == ".txt":
            input_text = input_path.read_text(encoding="utf-8")
            if args.compositional:
                comp_ast = parse_compositional_pml(input_text)
                ast = resolve_layout(comp_ast)
            else:
                # Try flat PML first, then compositional if it fails
                try:
                    ast = parse_pml(input_text)
                except PMLParseError as e:
                    # Check if it might be compositional PML
                    if any(keyword in input_text for keyword in ["component", "frame", "inset", "grid", "split"]):
                        print(f"Hint: This looks like compositional PML. Try adding --compositional flag", file=sys.stderr)
                    raise
        else:
            print(f"Error: Unsupported input format: {input_suffix}", file=sys.stderr)
            print("Supported formats: .pml, .txt, .json", file=sys.stderr)
            sys.exit(1)

        # Convert to shape dicts
        shapes = items_to_shape_dicts(ast.items)

        # Import CAD export functions (deferred to avoid import error when backend unavailable)
        try:
            from cad.export.step import SheetSpec, export_stl, export_step
        except ImportError as e:
            print(f"✗ CAD export failed: {e}", file=sys.stderr)
            print("Native CAD backend not available. See README for setup instructions.", file=sys.stderr)
            sys.exit(1)

        # Create sheet spec
        sheet = SheetSpec(
            width_mm=ast.sheet.width_mm,
            height_mm=ast.sheet.height_mm,
            thickness_mm=ast.sheet.thickness_mm,
        )

        # Prepare output directory and basename
        output_dir = Path(args.out)
        output_dir.mkdir(parents=True, exist_ok=True)
        basename = input_path.stem

        # Export STL
        if args.format in ("stl", "both"):
            stl_path = output_dir / f"{basename}.stl"
            try:
                stl_files = export_stl(
                    sheet,
                    shapes,
                    stl_path,
                    kerf_mm=args.kerf,
                    include_sheet=args.include_sheet,
                    include_floating_parts=not args.no_floating_parts,
                    mesh_tolerance_mm=args.mesh_tolerance,
                    angular_tolerance_deg=args.angular_tolerance,
                )
                print(f"✓ STL exported: {len(stl_files)} file(s)")
                for stl_file in stl_files:
                    print(f"  - {stl_file}")
            except ImportError as e:
                print(f"✗ STL export failed: {e}", file=sys.stderr)
                print("Native CAD backend not available. See README for setup instructions.", file=sys.stderr)
                if args.format == "stl":
                    sys.exit(1)

        # Export STEP
        if args.format in ("step", "both"):
            step_path = output_dir / f"{basename}.step"
            try:
                export_step(
                    sheet,
                    shapes,
                    step_path,
                    kerf_mm=args.kerf,
                    include_floating_parts=not args.no_floating_parts,
                )
                print(f"✓ STEP exported: {step_path}")
            except ImportError as e:
                print(f"✗ STEP export failed: {e}", file=sys.stderr)
                print("Native CAD backend not available. See README for setup instructions.", file=sys.stderr)
                if args.format == "step":
                    sys.exit(1)

    except PMLParseError as e:
        print(f"PML Parse Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        # Check if it's a compositional parse error
        if e.__class__.__name__ == "ParseError" and "compositional_parser" in str(type(e).__module__):
            print(f"Compositional PML Parse Error: {e}", file=sys.stderr)
            sys.exit(1)
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
