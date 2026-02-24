from __future__ import annotations

import argparse
import sys
from pathlib import Path

from cli.project import add_project_arg, get_project_dir, resolve_input_path
from layout_ast.layout import LayoutAST
from pml import PMLParseError, format_pml, parse_pml


def main():
    parser = argparse.ArgumentParser(
        description="Convert between layout formats (PML ↔ JSON)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:

  python -m cli.convert_layout --project my_table --from pml --to json input.pml output.json


  python -m cli.convert_layout --from json --to pml input.json output.pml


  python -m cli.convert_layout --from pml --to json < input.pml > output.json
        """,
    )

    add_project_arg(parser)
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
        if args.input_file:
            input_path = resolve_input_path(args.project, args.input_file)
            if not input_path.exists():
                print(f"Error: Input file not found: {input_path}", file=sys.stderr)
                sys.exit(1)
            input_text = input_path.read_text()
        else:
            input_text = sys.stdin.read()

        if args.input_format == "pml":
            ast = parse_pml(input_text)
        elif args.input_format == "json":
            if not args.input_file:
                print("Error: JSON input requires a file path (stdin not supported for JSON)", file=sys.stderr)
                sys.exit(1)
            ast = LayoutAST.from_json(str(input_path))
        else:
            print(f"Error: Unknown input format: {args.input_format}", file=sys.stderr)
            sys.exit(1)

        if args.output_format == "json":
            output_text = ast.to_json()
        elif args.output_format == "pml":
            output_text = format_pml(ast)
        else:
            print(f"Error: Unknown output format: {args.output_format}", file=sys.stderr)
            sys.exit(1)

        if args.output_file:
            if args.project and not Path(args.output_file).is_absolute():
                output_path = get_project_dir(args.project) / args.output_file
            else:
                output_path = Path(args.output_file)
            output_path.write_text(output_text)
            print(f"Converted {args.input_format} → {args.output_format}: {output_path}", file=sys.stderr)
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
