from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from pathlib import Path

from cam.compilation import load_pml_asts
from cli.project import add_project_arg, get_project_dir, resolve_input_path
from layout_ast.layout import LayoutAST
from pml import PMLParseError, format_pml, parse_pml_yaml
from resolution.layout_resolver import requires_machining_clearance, resolve_layout


def resolve_conversion_pml(input_text: str, input_path: Path | None, args) -> LayoutAST:
    if args.for_machining:
        from config.machine_loader import get_machines_dir, load_endmills, load_feeds

        if input_path is None:
            raise ValueError("Machining conversion requires a source file")
        endmills = load_endmills(args.endmills or get_machines_dir() / "endmills.yml")
        feeds = load_feeds(args.feeds or get_machines_dir() / "feeds.yml")
        asts = load_pml_asts(input_path, kerf_mm=args.kerf, endmills=endmills, feeds=feeds)
        if len(asts) != 1:
            raise ValueError(
                f"Source resolves to {len(asts)} sheets; one layout JSON cannot represent a multi-sheet job"
            )
        return asts[0]
    parsed = parse_pml_yaml(input_text)
    ast = resolve_layout(parsed)
    if requires_machining_clearance(parsed.root):
        ast = replace(ast, config={**ast.config, "requires_machining_clearance": True})
    return ast


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

    parser.add_argument(
        "--for-machining",
        action="store_true",
        help="Resolve PML with actual profile tooling and preserve its build context in JSON",
    )
    parser.add_argument("--kerf", type=float, default=None, help="Requested profile diameter for --for-machining")
    parser.add_argument("--endmills", default=None, help="Tool library for --for-machining")
    parser.add_argument("--feeds", default=None, help="Feeds library for --for-machining")
    args = parser.parse_args()
    if args.for_machining and (args.input_format != "pml" or args.output_format != "json" or not args.input_file):
        parser.error("--for-machining requires a PML input file and JSON output")
    if not args.for_machining and any(value is not None for value in (args.kerf, args.endmills, args.feeds)):
        parser.error("tool options require --for-machining")

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
            ast = resolve_conversion_pml(input_text, input_path if args.input_file else None, args)
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
