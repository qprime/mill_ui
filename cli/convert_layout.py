"""CLI tool for converting between layout formats: PML ↔ JSON.

Usage:
    python -m skills.mill_ui.cli.convert_layout --from pml --to json input.pml output.json
    python -m skills.mill_ui.cli.convert_layout --from json --to pml input.json output.pml
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from skills.mill_ui.pml import parse_pml, format_pml, PMLParseError
from skills.mill_ui.layout_ast.layout import LayoutAST


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Convert between layout formats (PML ↔ JSON)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Convert PML to JSON
  python -m skills.mill_ui.cli.convert_layout --from pml --to json input.pml output.json

  # Convert JSON to PML
  python -m skills.mill_ui.cli.convert_layout --from json --to pml input.json output.pml

  # Read from stdin, write to stdout
  python -m skills.mill_ui.cli.convert_layout --from pml --to json < input.pml > output.json
        """,
    )

    parser.add_argument(
        "--from",
        dest="input_format",
        required=True,
        choices=["pml", "json"],
        help="Input format",
    )
    parser.add_argument(
        "--to",
        dest="output_format",
        required=True,
        choices=["pml", "json"],
        help="Output format",
    )
    parser.add_argument(
        "input_file",
        nargs="?",
        help="Input file path (or stdin if omitted)",
    )
    parser.add_argument(
        "output_file",
        nargs="?",
        help="Output file path (or stdout if omitted)",
    )

    args = parser.parse_args()

    try:
        # Read input
        if args.input_file:
            input_path = Path(args.input_file)
            if not input_path.exists():
                print(f"Error: Input file not found: {args.input_file}", file=sys.stderr)
                sys.exit(1)
            input_text = input_path.read_text()
        else:
            input_text = sys.stdin.read()

        # Parse to AST
        if args.input_format == "pml":
            ast = parse_pml(input_text)
        elif args.input_format == "json":
            # For JSON input, we need a file path (LayoutAST.from_json expects path)
            if not args.input_file:
                print("Error: JSON input requires a file path (stdin not supported for JSON)", file=sys.stderr)
                sys.exit(1)
            ast = LayoutAST.from_json(args.input_file)
        else:
            print(f"Error: Unknown input format: {args.input_format}", file=sys.stderr)
            sys.exit(1)

        # Convert to output format
        if args.output_format == "json":
            output_text = ast.to_json()
        elif args.output_format == "pml":
            output_text = format_pml(ast)
        else:
            print(f"Error: Unknown output format: {args.output_format}", file=sys.stderr)
            sys.exit(1)

        # Write output
        if args.output_file:
            output_path = Path(args.output_file)
            output_path.write_text(output_text)
            print(f"Converted {args.input_format} → {args.output_format}: {args.output_file}", file=sys.stderr)
        else:
            print(output_text, end="")

    except PMLParseError as e:
        print(f"PML Parse Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
