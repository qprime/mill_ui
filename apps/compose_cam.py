# path: skills/mill_ui/apps/compose_cam.py
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
from typing import Dict, Any, List, Tuple

from skills.mill_ui.compositions import resolve_templates  # auto-register templates
from skills.mill_ui.cam.model.hints import build_cam_hints
from skills.mill_ui.cam.planner.passes import plan_passes
from skills.mill_ui.cam.post.gcode import write_gcode
from skills.mill_ui.cam.tools.adapter import load_tool_db, select_tools_for_job

from skills.mill_ui.cam.model.material import Material
from skills.mill_ui.cam.model.machine import Machine
from skills.mill_ui.cam.model.stock import Stock

# ---------- IO helpers ----------
def _load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)

def _save_text(path: Path, s: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(s, encoding="utf-8")

def _save_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")

# ---------- CLI ----------
def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(prog="compose_cam", description="Resolve compositions, plan grouped passes, write per-pass G-code + summary.")
    ap.add_argument("--project", help="Project name under memories/cam_projects/sheet_layouts/<project>.")
    ap.add_argument("--input", help="Optional explicit input layout.json path.")
    ap.add_argument("--outdir", help="Optional explicit output dir (defaults to project CAM folder).")
    ap.add_argument("--tool-db", help="Rich tool_db.json path.")
    ap.add_argument("--material", default="MDF", help="Material key in tool_db feeds_speeds.")
    ap.add_argument("--safe-z", type=float, default=6.0)
    ap.add_argument("--prime-spindle", action="store_true", help="Insert initial M3 S0 (via set_rpm=0) in each pass.")
    ap.add_argument("--auto-select", action="store_true", help="Pick a minimal tool set from tool_selection_rules.")
    args = ap.parse_args(argv)

    # Resolve paths from project name if provided
    if args.project and not args.input:
        base = Path("memories/cam_projects/sheet_layouts") / args.project
        in_path = base / "input" / "layout.json"
        outdir = base / "CAM"
    else:
        if not args.input:
            print("Error: --input or --project is required", file=sys.stderr)
            return 2
        in_path = Path(args.input)
        outdir = Path(args.outdir) if args.outdir else in_path.parent.parent / "CAM"

    data = _load_json(in_path)

    sheet = data.get("sheet") or {}
    panel_w = float(sheet.get("width_mm", 0.0))
    panel_h = float(sheet.get("height_mm", 0.0))
    panel_t = float(sheet.get("thickness_mm", 0.0))

    # items may include kind:"template" entries
    items = list(data.get("items") or [])

    # If the input JSON already contains explicit placements or a layout block, keep them.
    # (Your existing layout.jsons already place items or include layout handling earlier in pipeline.)
    # Here we simply resolve templates; placement is respected if present.
    items_resolved = resolve_templates(items, sheet_thickness_mm=panel_t)

    # Build hints (clean separation of geometry vs ops)
    hints = build_cam_hints(
        items_resolved=items_resolved,
        sheet_thickness=panel_t,
        kerf_width_mm=float(data.get("kerf_width_mm", 0.0))
    )

    # Tool DB (rich → planner format)
    if not args.tool_db:
        print("Warning: --tool-db not provided, using two default tools.", file=sys.stderr)
        tools = [
            {"name": "SmallFlat", "diameter": 3.175, "kind": "flat", "rpm": 14000, "feed_xy": 900, "feed_z": 300},
            {"name": "BigFlat",   "diameter": 6.35,  "kind": "flat", "rpm": 12000, "feed_xy": 800, "feed_z": 280},
        ]
    else:
        tools = (select_tools_for_job(args.tool_db, material=args.material)
                 if args.auto_select else load_tool_db(args.tool_db, material=args.material))

    # Plan grouped passes
    material = Material(name=args.material)
    machine = Machine(name="default_grbl")
    stock = Stock(width=panel_w, height=panel_h, thickness=panel_t)

    passes, job_summary = plan_passes(
        hints,
        tool_db=tools,
        material=material,
        machine=machine,
        stock=stock,
        safe_z=float(args.safe_z),
        prime_spindle=bool(args.prime_spindle),
    )

    # Write each pass as a separate G-code file with required naming
    outdir.mkdir(parents=True, exist_ok=True)
    made_files: List[str] = []
    for p in passes:
        gcode = write_gcode(p["moves"], safe_z=float(args.safe_z))
        fpath = outdir / p["filename"]
        _save_text(fpath, gcode)
        made_files.append(str(fpath))

    # Summary JSON (human/app readable)
    # Attach top-level context: sheet, tool_db brief, project name if any
    job_summary.update({
        "project": args.project or in_path.parent.parent.name,
        "sheet": {"width_mm": panel_w, "height_mm": panel_h, "thickness_mm": panel_t},
        "output_dir": str(outdir),
        "files": [Path(f).name for f in made_files],
    })
    _save_json(outdir / "summary.json", job_summary)

    for f in made_files:
        print(f)
    print(outdir / "summary.json")
    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
