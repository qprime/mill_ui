from __future__ import annotations
import argparse, sys
from pathlib import Path
import skills.mill_ui_cq.paths as P
from skills.mill_ui_cq.build import build_from_layout

def main():
    ap = argparse.ArgumentParser(description="Shapes-first Layout → STEP")
    ap.add_argument(
        "--project",
        required=True,
        help="Project folder under memories/cam_projects/sheet_layouts (e.g., '4x4' or 'vent_plate_a')"
    )
    ap.add_argument(
        "--input",
        default=None,
        help="Optional explicit path to layout JSON; overrides --project"
    )
    args = ap.parse_args()

    P.set_project(args.project)
    input_path = Path(args.input) if args.input else (P.INPUT_DIR / "layout.json")

    outdir = build_from_layout(input_path)
    print(str(outdir))

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[mill_ui_cq] ERROR: {e}", file=sys.stderr)
        sys.exit(1)
