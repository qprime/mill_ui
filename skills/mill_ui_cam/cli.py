#!/usr/bin/env python3
"""Command line interface for generic CAM processor (thin wrapper around API)."""

import argparse
import sys
from pathlib import Path
from skills.mill_ui_cam.gcode_generator import GCodeGenerator, PROJECTS_ROOT


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate G-code from mill_ui_cam operations")
    parser.add_argument("project", help="Project name (folder under PROJECTS_ROOT)")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    args = parser.parse_args()

    # Validate project exists using the single-source root from the generator
    project_dir = PROJECTS_ROOT / args.project
    if not project_dir.exists():
        print(f"Error: Project directory not found: {project_dir}", file=sys.stderr)
        print(f"(PROJECTS_ROOT = {PROJECTS_ROOT})", file=sys.stderr)
        return 1

    # Check for required files (still useful UX)
    cam_dir = project_dir / "CAM"
    ops_file = cam_dir / f"{args.project}_operations.json"
    if not ops_file.exists():
        print(f"Error: Operations file not found: {ops_file}", file=sys.stderr)
        print("Run tool selection to generate CAM/<project_name>_operations.json", file=sys.stderr)
        return 1

    try:
        generator = GCodeGenerator()
        out_paths = generator.process_project(args.project)

        print(f"Successfully generated {len(out_paths)} G-code file(s):")
        for p in out_paths:
            print(f"  {p.name}")
            if args.verbose:
                print(f"    Full path: {p}")
                print(f"    Size: {p.stat().st_size} bytes")

        print(f"\nG-code files saved to: {cam_dir}")
        return 0

    except Exception as e:
        print(f"Error generating G-code: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
