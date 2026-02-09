from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from pml.yaml_parser import parse_pml_yaml, PMLParseError as ParseError
from pml.revision_header import update_file_header, format_pml_header
from resolution.layout_resolver import resolve_layout
from layout_ast.layout import LayoutAST
from cam.pipeline import run_pipeline, write_pipeline_outputs, DEFAULT_TOOL_DB
from cli.project import add_project_arg, resolve_input_path, resolve_output_dir, get_project_dir

RECIPE_DEFAULTS = {
    "kerf": 3.175,
    "theme": "dark",
}

DEFAULT_MARGIN_MM = 10.0
DEFAULT_KERF_MM = 6.35


def parse_sheet_dimensions(sheet_str: str) -> tuple[float, float]:
    match = re.match(r"^(\d+(?:\.\d+)?)[xX](\d+(?:\.\d+)?)$", sheet_str)
    if not match:
        raise ValueError(f"Invalid sheet format: {sheet_str}. Expected WxH (e.g., 1220x1220)")
    return float(match.group(1)), float(match.group(2))


def generate_layout_scaffold(
    sheet_width: float,
    sheet_height: float,
    thickness: float,
    margin: float,
    kerf: float,
    project_name: str | None = None,
) -> str:
    working_width = sheet_width - 2 * margin
    working_height = sheet_height - 2 * margin

    header = format_pml_header()
    header += f"# Working area: {working_width:.0f}x{working_height:.0f}mm\n"
    header += f"# Valid X: 0 to {working_width:.0f}mm, Valid Y: 0 to {working_height:.0f}mm\n"
    header += "#\n"
    header += "# Place parts using center coordinates (x, y) and size (width, height).\n"
    header += "# Use simple round numbers. Do NOT calculate offsets.\n"
    header += "\n"

    project_line = f"project: {project_name}\n" if project_name else ""

    pml = f"""{header}{project_line}Sheet:
  working_width: {working_width:.0f}mm
  working_height: {working_height:.0f}mm
  thickness: {thickness:.1f}mm
  margin: {margin:.0f}mm

children:
  []


"""
    return pml


def generate_assembly_scaffold(
    sheet_width: float,
    sheet_height: float,
    thickness: float,
    margin: float,
    kerf: float,
    project_name: str | None = None,
) -> str:
    working_width = sheet_width - 2 * margin
    working_height = sheet_height - 2 * margin

    header = format_pml_header()
    header += f"# Physical sheet: {sheet_width:.0f}x{sheet_height:.0f}mm\n"
    header += f"# Working area: {working_width:.0f}x{working_height:.0f}mm\n"
    header += "#\n"
    header += "# Assembly projects auto-layout parts within the working area.\n"
    header += "# Do NOT add kerf/tool offsets - CAM handles tool compensation.\n"
    header += "\n"

    project_line = f"project: {project_name}\n" if project_name else ""

    pml = f"""{header}{project_line}Sheet:
  width: {sheet_width:.0f}mm
  height: {sheet_height:.0f}mm
  thickness: {thickness:.1f}mm
  margin: {margin:.0f}mm

kerf: {kerf}mm

children:
  - Assembly:
      topology: box
      width: TODO
      depth: TODO
      height: TODO
      thickness: {thickness:.1f}mm
      joinery: finger
      finger_width: 12mm
      clearance: 0.15mm
      show_labels: true
"""
    return pml


def init_project(args) -> None:
    project_type = args.init_project

    if not args.sheet:
        print("Error: --sheet is required with --init_project", file=sys.stderr)
        sys.exit(1)
    if args.thickness is None:
        print("Error: --thickness is required with --init_project", file=sys.stderr)
        sys.exit(1)

    try:
        sheet_width, sheet_height = parse_sheet_dimensions(args.sheet)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    margin = args.margin if args.margin is not None else DEFAULT_MARGIN_MM
    kerf = args.kerf if args.kerf != DEFAULT_KERF_MM else DEFAULT_KERF_MM

    if args.project:
        project_dir = get_project_dir(args.project)
        output_path = project_dir / "layout.pml.yml"
    else:
        output_path = Path("layout.pml.yml")

    if output_path.exists():
        print(f"Error: {output_path} already exists. Delete it first to regenerate.", file=sys.stderr)
        sys.exit(1)

    if project_type == "layout":
        pml_content = generate_layout_scaffold(
            sheet_width=sheet_width,
            sheet_height=sheet_height,
            thickness=args.thickness,
            margin=margin,
            kerf=kerf,
            project_name=args.project,
        )
    elif project_type == "assembly":
        pml_content = generate_assembly_scaffold(
            sheet_width=sheet_width,
            sheet_height=sheet_height,
            thickness=args.thickness,
            margin=margin,
            kerf=kerf,
            project_name=args.project,
        )
    else:
        print(f"Error: Unknown project type: {project_type}", file=sys.stderr)
        sys.exit(1)

    if args.project:
        project_dir.mkdir(parents=True, exist_ok=True)

    output_path.write_text(pml_content, encoding="utf-8")
    print(f"Created {output_path}", file=sys.stderr)

    print(f"  Type: {project_type}", file=sys.stderr)
    print(f"  Physical sheet: {sheet_width:.0f}x{sheet_height:.0f}mm", file=sys.stderr)
    if project_type == "layout":
        working_width = sheet_width - 2 * margin
        working_height = sheet_height - 2 * margin
        print(f"  Working area: {working_width:.0f}x{working_height:.0f}mm", file=sys.stderr)
    print(f"  Margin: {margin:.0f}mm", file=sys.stderr)
    print(f"  Kerf: {kerf}mm", file=sys.stderr)


def find_recipe_source(recipe_dir: Path) -> Path | None:
    for candidate in ["example.pml.yml", "source.pml.yml"]:
        source = recipe_dir / candidate
        if source.exists():
            return source
    return None


def collect_input_files(project: str | None, input_arg: str | None) -> list[Path]:
    if input_arg:
        input_path = resolve_input_path(project, input_arg)
        if input_path.is_file():
            return [input_path]
        if input_path.is_dir():
            return sorted(input_path.glob("*.pml.yml"))
        print(f"Error: Input not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    if project:
        project_dir = get_project_dir(project)
        pml_files = sorted(project_dir.glob("*.pml.yml"))
        if pml_files:
            return pml_files
        print(f"Error: No .pml.yml files found in {project_dir}", file=sys.stderr)
        sys.exit(1)

    print("Error: --input or --project required", file=sys.stderr)
    sys.exit(1)


def _run_and_write(
    ast: LayoutAST,
    output_dir: Path,
    job_name: str,
    source_path: Path,
    *,
    kerf_mm: float,
    theme: str,
    y_origin: str,
    generate_svg: bool,
    update_header: bool = True,
) -> None:
    result = run_pipeline(
        ast,
        kerf_mm=kerf_mm,
        tool_db=DEFAULT_TOOL_DB,
        generate_svg=generate_svg,
        svg_theme=theme,
        y_origin=y_origin,
    )

    if result.errors:
        print(f"\nErrors:", file=sys.stderr)
        for error in result.errors:
            print(f"  - {error}", file=sys.stderr)

    if result.warnings:
        print(f"\nWarnings:", file=sys.stderr)
        for warning in result.warnings:
            print(f"  - {warning}", file=sys.stderr)

    build_params = {
        "source": source_path.name,
        "kerf_mm": kerf_mm,
        "theme": theme,
        "y_origin": y_origin,
    }

    outputs = write_pipeline_outputs(
        result,
        output_dir,
        job_name,
        clean_output_dir=False,
        build_params=build_params,
    )

    print(f"  Outputs:", file=sys.stderr)
    for key, path in outputs.items():
        print(f"    {path.name}", file=sys.stderr)

    print(f"  Pipeline: {result.metrics['timing']['total_ms']:.1f}ms", file=sys.stderr)

    if update_header and result.gcode:
        update_file_header(source_path)


def process_file(input_path: Path, output_dir: Path, args) -> None:
    input_name = input_path.name.lower()
    if input_name.endswith(".json"):
        ast = LayoutAST.from_json(str(input_path))
    elif input_name.endswith(".pml.yml") or input_name.endswith(".pml") or input_name.endswith(".txt"):
        input_text = input_path.read_text(encoding="utf-8")
        comp_ast = parse_pml_yaml(input_text)
        ast = resolve_layout(comp_ast)
    else:
        print(f"Error: Unsupported input format: {input_name}", file=sys.stderr)
        return

    print(f"Compiling: {input_path.name}", file=sys.stderr)
    print(f"  Sheet: {ast.sheet.width_mm}x{ast.sheet.height_mm}x{ast.sheet.thickness_mm}mm", file=sys.stderr)
    print(f"  Items: {len(ast.items)}", file=sys.stderr)

    is_pml = input_name.endswith(".pml.yml") or input_name.endswith(".pml") or input_name.endswith(".txt")
    _run_and_write(
        ast, output_dir, input_path.stem, input_path,
        kerf_mm=args.kerf, theme=args.theme,
        y_origin=args.y_origin, generate_svg=not args.no_svg,
        update_header=is_pml,
    )


def process_recipe(recipe_dir: Path, args) -> None:
    source = find_recipe_source(recipe_dir)
    if not source:
        print(f"Error: No example.pml.yml or source.pml.yml in {recipe_dir}", file=sys.stderr)
        sys.exit(1)

    output_dir = recipe_dir / "output"

    kerf = args.kerf if args.kerf != 6.35 else RECIPE_DEFAULTS["kerf"]
    theme = args.theme if args.theme != "dark" else RECIPE_DEFAULTS["theme"]

    input_text = source.read_text(encoding="utf-8")
    comp_ast = parse_pml_yaml(input_text)
    ast = resolve_layout(comp_ast)

    print(f"Recipe: {recipe_dir.name}", file=sys.stderr)
    print(f"  Source: {source.name}", file=sys.stderr)
    print(f"  Sheet: {ast.sheet.width_mm}x{ast.sheet.height_mm}x{ast.sheet.thickness_mm}mm", file=sys.stderr)
    print(f"  Items: {len(ast.items)}", file=sys.stderr)

    import shutil
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    _run_and_write(
        ast, output_dir, recipe_dir.name, source,
        kerf_mm=kerf, theme=theme,
        y_origin=args.y_origin, generate_svg=not args.no_svg,
    )


def main():
    parser = argparse.ArgumentParser(
        description="Compile PML to G-code and SVG blueprint",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:

  python -m cli.mill --project my_table

  python -m cli.mill --project my_table --input door.pml.yml

  python -m cli.mill --input /path/to/layout.pml.yml --out output/

  python -m cli.mill --project cabinet --input panel.pml.yml --kerf 3.175

  python -m cli.mill --recipe docs/recipes/01_simple_profile

  python -m cli.mill --init_project layout --sheet 1220x1220 --thickness 19

  python -m cli.mill --init_project assembly --sheet 800x600 --thickness 6

  python -m cli.mill --project my_table --init_project layout --sheet 1220x1220 --thickness 19

Output files:
  {basename}.{op}-{tool_diameter}mm.nc   G-code per pass
  {basename}.svg              Blueprint drawing
  metrics.json                Pipeline metrics
        """,
    )

    add_project_arg(parser)
    parser.add_argument(
        "--recipe",
        "-r",
        default=None,
        help="Recipe directory (e.g., docs/recipes/01_simple_profile)",
    )
    parser.add_argument(
        "--input",
        "-i",
        default=None,
        help="Input file or directory (default: project dir, processes all .pml.yml files)",
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
        "--no-svg",
        action="store_true",
        help="Skip SVG blueprint generation",
    )
    parser.add_argument(
        "--no-clean",
        action="store_true",
        help="Don't clean output directory before writing",
    )
    parser.add_argument(
        "--y-origin",
        default="back",
        choices=["front", "back"],
        help="Y=0 reference: back (lower-left origin) or front (default: back)",
    )

    init_group = parser.add_argument_group("project initialization")
    init_group.add_argument(
        "--init_project",
        choices=["layout", "assembly"],
        metavar="TYPE",
        help="Generate a starter PML file (TYPE: layout, assembly)",
    )
    init_group.add_argument(
        "--sheet",
        default=None,
        help="Physical sheet dimensions as WxH in mm (e.g., 1220x1220)",
    )
    init_group.add_argument(
        "--thickness",
        type=float,
        default=None,
        help="Material thickness in mm",
    )
    init_group.add_argument(
        "--margin",
        type=float,
        default=None,
        help=f"Margin/clamp zone in mm (default: {DEFAULT_MARGIN_MM})",
    )

    args = parser.parse_args()

    try:
        if args.init_project:
            init_project(args)
            return

        if args.recipe:
            recipe_dir = Path(args.recipe)
            if not recipe_dir.is_dir():
                print(f"Error: Recipe directory not found: {recipe_dir}", file=sys.stderr)
                sys.exit(1)
            process_recipe(recipe_dir, args)
            return

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
