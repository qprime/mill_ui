"""CLI tool for exporting STL models for visual validation.

Usage:
    python -m cli.export_cad --input door.pml --out out/
    python -m cli.export_cad --input door.json --kerf 3.175 --out out/
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
        description="Export STL models for visual validation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic export
  python -m cli.export_cad --input door.pml --out out/

  # With kerf compensation
  python -m cli.export_cad --input door.pml --kerf 3.175 --out out/

  # High quality mesh (more circle segments)
  python -m cli.export_cad --input door.pml --quality high --out out/

Output file naming:
  STL: {basename}.stl (plus {basename}_part_N.stl for floating parts)

Note: STEP export is not currently implemented. STL files can be opened in
FreeCAD, MeshLab, Windows 3D Viewer, or online viewers for validation.
        """,
    )

    parser.add_argument(
        "--input",
        "-i",
        required=True,
        help="Input file path (PML or JSON)",
    )
    parser.add_argument(
        "--quality",
        "-q",
        default="medium",
        choices=["low", "medium", "high"],
        help="Mesh quality for circles - low=16, medium=32, high=64 segments (default: medium)",
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
        help="Exclude floating parts (cutouts) from export",
    )
    parser.add_argument(
        "--compositional",
        "-c",
        action="store_true",
        help="Parse as compositional PML (frame/inset/grid syntax)",
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

        # Prepare output directory and basename
        output_dir = Path(args.out)
        output_dir.mkdir(parents=True, exist_ok=True)
        basename = input_path.stem

        # NOTE: STL export implementation will be added here using trimesh
        # For now, display what would be exported
        print(f"✗ STL export not yet implemented", file=sys.stderr)
        print(f"", file=sys.stderr)
        print(f"Parsed layout:", file=sys.stderr)
        print(f"  Sheet: {ast.sheet.width_mm}x{ast.sheet.height_mm}x{ast.sheet.thickness_mm}mm", file=sys.stderr)
        print(f"  Shapes: {len(shapes)}", file=sys.stderr)
        for i, shape in enumerate(shapes):
            print(f"    [{i}] {shape['type']} - {shape['feature']['type']}", file=sys.stderr)
        print(f"", file=sys.stderr)
        print(f"Would export to: {output_dir / basename}.stl", file=sys.stderr)
        print(f"Implementation pending: F003 (trimesh-based STL export)", file=sys.stderr)
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
