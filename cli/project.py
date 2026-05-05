from __future__ import annotations

import os
import re
import sys
from pathlib import Path

DEFAULT_MARGIN_MM = 10.0
DEFAULT_KERF_MM = 6.35


def parse_sheet_dimensions(sheet_str: str) -> tuple[float, float]:
    match = re.match(r"^(\d+(?:\.\d+)?)[xX](\d+(?:\.\d+)?)$", sheet_str)
    if not match:
        raise ValueError(f"Invalid sheet format: {sheet_str}. Expected WxH (e.g., 1220x1220)")
    return float(match.group(1)), float(match.group(2))


PROJECTS_BASE = Path(os.environ.get("MILL_UI_PROJECTS", str(Path.home() / "mill_ui_projects")))


def get_project_dir(project: str) -> Path:
    if not project:
        print("Error: --project is required", file=sys.stderr)
        sys.exit(1)

    project_dir = PROJECTS_BASE / project
    project_dir.mkdir(parents=True, exist_ok=True)
    return project_dir


def resolve_input_path(project: str | None, input_file: str) -> Path:
    input_path = Path(input_file)

    if input_path.is_absolute():
        return input_path

    if project:
        return get_project_dir(project) / input_file

    if input_path.exists():
        return input_path

    print(f"Error: File not found: {input_file}", file=sys.stderr)
    print("Use --project to specify a project directory", file=sys.stderr)
    sys.exit(1)


def resolve_output_dir(project: str | None, output: str | None) -> Path:
    if output:
        return Path(output)

    if project:
        return get_project_dir(project) / "output"

    return Path("output")


def add_project_arg(parser):
    parser.add_argument(
        "--project",
        "-p",
        help=f"Project name (resolves to {PROJECTS_BASE}/<project>/)",
    )
