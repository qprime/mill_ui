
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pml.compositional_parser import parse_compositional_pml, ParseError
from pml.compositional_formatter import format_compositional_pml
from pml import format_pml


def main():
    parser = argparse.ArgumentParser(
        description="Parse and validate compositional PML files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:

  python -m cli.parse_compositional_pml input.pml


  python -m cli.parse_compositional_pml input.pml --output output.pml


  python -m cli.parse_compositional_pml input.pml --resolve --format pml


  python -m cli.parse_compositional_pml input.pml --resolve --format json


  python -m cli.parse_compositional_pml --format pml < input.pml > output.pml
        """,
    )

    parser.add_argument(
        "input_file",
        nargs="?",
        help="Input compositional PML file (or stdin if omitted)",
    )
    parser.add_argument(
        "--output",
        "-o",
        dest="output_file",
        help="Output file path (or stdout if omitted)",
    )
    parser.add_argument(
        "--resolve",
        action="store_true",
        help="Resolve compositional layout to flat LayoutAST (requires --format)",
    )
    parser.add_argument(
        "--format",
        "-f",
        dest="output_format",
        choices=["pml", "json", "compositional"],
        default="compositional",
        help="Output format (default: compositional). Use 'compositional' for canonical compositional PML, 'pml' for flat PML (requires --resolve), 'json' for flat JSON (requires --resolve)",
    )

    args = parser.parse_args()


    if args.output_format in ("pml", "json") and not args.resolve:
        print(f"Error: --format {args.output_format} requires --resolve", file=sys.stderr)
        sys.exit(1)

    try:

        if args.input_file:
            input_path = Path(args.input_file)
            if not input_path.exists():
                print(f"Error: Input file not found: {args.input_file}", file=sys.stderr)
                sys.exit(1)
            input_text = input_path.read_text()
            print(f"Parsing compositional PML: {args.input_file}", file=sys.stderr)
        else:
            input_text = sys.stdin.read()
            print("Parsing compositional PML from stdin...", file=sys.stderr)


        comp_ast = parse_compositional_pml(input_text)
        print(f"✓ Parse successful", file=sys.stderr)


        if args.resolve:
            from resolution.layout_resolver import resolve_layout

            print("Resolving compositional layout...", file=sys.stderr)
            flat_ast = resolve_layout(comp_ast)
            print(f"✓ Resolved to {len(flat_ast.items)} flat items", file=sys.stderr)


        if args.output_format == "compositional":

            output_text = format_compositional_pml(comp_ast)
            output_desc = "canonical compositional PML"
        elif args.output_format == "pml":

            output_text = format_pml(flat_ast)
            output_desc = "flat PML"
        elif args.output_format == "json":

            output_text = flat_ast.to_json()
            output_desc = "flat JSON"
        else:
            print(f"Error: Unknown output format: {args.output_format}", file=sys.stderr)
            sys.exit(1)


        if args.output_file:
            output_path = Path(args.output_file)
            output_path.write_text(output_text)
            print(f"✓ Written {output_desc} to: {args.output_file}", file=sys.stderr)
        else:
            print(output_text, end="")

    except ParseError as e:
        print(f"✗ Parse Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"✗ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
