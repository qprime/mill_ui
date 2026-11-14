from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pml import format_pml_yaml, parse_pml_yaml


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate and format authored PML source")
    parser.add_argument("input_file", nargs="?")
    parser.add_argument("--output", "-o", dest="output_file")
    parser.add_argument("--format", "-f", choices=["yaml"], default="yaml")
    args = parser.parse_args()
    if args.input_file and not Path(args.input_file).is_file():
        parser.exit(1, f"Error: Input file not found: {args.input_file}\n")
    source = Path(args.input_file).read_text() if args.input_file else sys.stdin.read()
    output = format_pml_yaml(parse_pml_yaml(source))
    print("✓ Parse successful", file=sys.stderr)
    if args.output_file:
        Path(args.output_file).write_text(output)
    else:
        print(output, end="")


if __name__ == "__main__":
    main()
