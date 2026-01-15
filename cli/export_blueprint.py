
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pml import parse_pml, PMLParseError
from pml.compositional_parser import parse_compositional_pml
from resolution.layout_resolver import resolve_layout
from layout_ast.layout import LayoutAST
from adapters.ast_to_removal import ast_to_removal_intents
from export.blueprint_svg import render_blueprint_svg, THEMES


def main():
    parser = argparse.ArgumentParser(
        description="Export blueprint proof drawings (SVG/PDF)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:

  python -m cli.export_blueprint --input door.pml --theme dark --format svg --out out/


  python -m cli.export_blueprint --input door.json --theme print --format pdf --out out/


  python -m cli.export_blueprint --input door.pml --theme dark --format both --out out/

Output file naming:
  {basename}.blueprint.{theme}.{format}
  Example: door.blueprint.dark.svg, door.blueprint.print.pdf
        """,
    )

    parser.add_argument(
        "--input",
        "-i",
        required=True,
        help="Input file path (PML or JSON)",
    )
    parser.add_argument(
        "--theme",
        "-t",
        default="dark",
        choices=list(THEMES.keys()),
        help="Visual theme (default: dark)",
    )
    parser.add_argument(
        "--format",
        "-f",
        default="svg",
        choices=["svg", "pdf", "both"],
        help="Output format (default: svg)",
    )
    parser.add_argument(
        "--out",
        "-o",
        default=".",
        help="Output directory (default: current directory)",
    )
    parser.add_argument(
        "--compositional",
        "-c",
        action="store_true",
        help="Parse as compositional PML (frame/inset/grid syntax)",
    )

    args = parser.parse_args()

    try:

        input_path = Path(args.input)
        if not input_path.exists():
            print(f"Error: Input file not found: {args.input}", file=sys.stderr)
            sys.exit(1)
        if not input_path.is_file():
            print(f"Error: Input path is not a file: {args.input}", file=sys.stderr)
            sys.exit(1)


        input_suffix = input_path.suffix.lower()
        if input_suffix == ".json":
            ast = LayoutAST.from_json(str(input_path))
        elif input_suffix == ".pml" or input_suffix == ".txt":
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


        removal_intents = ast_to_removal_intents(ast)


        svg_string = render_blueprint_svg(ast, removal_intents=removal_intents, theme=args.theme)


        output_dir = Path(args.out)
        output_dir.mkdir(parents=True, exist_ok=True)
        basename = input_path.stem


        if args.format in ("svg", "both"):
            svg_path = output_dir / f"{basename}.blueprint.{args.theme}.svg"
            svg_path.write_text(svg_string, encoding="utf-8")
            print(f"✓ SVG exported: {svg_path}")


        if args.format in ("pdf", "both"):
            pdf_path = output_dir / f"{basename}.blueprint.{args.theme}.pdf"
            try:
                from export.blueprint_pdf import svg_to_pdf
                svg_to_pdf(svg_string, pdf_path)
                print(f"✓ PDF exported: {pdf_path}")
            except ImportError as e:
                print(f"✗ PDF export failed: {e}", file=sys.stderr)
                print("Install cairosvg for PDF support: pip install cairosvg", file=sys.stderr)
                if args.format == "pdf":
                    sys.exit(1)

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
