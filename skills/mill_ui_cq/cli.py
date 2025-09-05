from __future__ import annotations
import json, argparse, sys
from pathlib import Path
import cadquery as cq  # ensure installed in your venv

from skills.mill_ui_cq.paths import INPUT_DIR, OUTPUT_DIR, DOORS_DIR, ensure_dirs
from skills.mill_ui_cq.components import ShakerSpec, build_shaker
from skills.mill_ui_cq.layout import SheetSpec, build_sheet, grid_positions, place_parts, export_doors, export_sheet_layout, write_design_intent, rect_bbox


def load_json(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))

def build_from_layout(layout_path: Path) -> Path:
    ensure_dirs()
    cfg = load_json(layout_path)

    # Sheet
    s = cfg["sheet"]
    sheet = SheetSpec(width=float(s["width_mm"]), height=float(s["height_mm"]), thickness=float(s["thickness_mm"]))
    sheet_wp = build_sheet(sheet)

    # Component (v0 supports ShakerDoor)
    comp = cfg["component"]
    if comp["type"] != "ShakerDoor":
        raise ValueError(f"Unsupported component type: {comp['type']}")
    p = comp["props"]

    # PASS anchor_recess through to the spec (this was missing before)
    spec = ShakerSpec(
        outer_w=float(p["outer_w"]), outer_h=float(p["outer_h"]),
        thickness=float(p.get("thickness", s["thickness_mm"])),
        stile_w=float(p["stile_w"]), rail_h=float(p["rail_h"]),
        panel_recess=float(p.get("panel_recess", 0)),
        anchor_recess=p.get("anchor_recess")  # <-- NEW
    )

    base = build_shaker(spec)

    # Arrangement
    arr = cfg.get("arrangement", {"type":"grid","cols":2,"rows":2})
    if arr["type"] != "grid":
        raise ValueError("Only 'grid' arrangement supported in v0")
    cols = int(arr["cols"]); rows = int(arr["rows"])
    margin = float(cfg.get("margin_mm", 20.0))
    gap = float(cfg.get("gap_mm", 10.0))

    positions = list(grid_positions(cols, rows, spec.outer_w, spec.outer_h, (margin, margin), gap, gap))
    total_w = cols*spec.outer_w + (cols-1)*gap + 2*margin
    total_h = rows*spec.outer_h + (rows-1)*gap + 2*margin
    if total_w > sheet.width or total_h > sheet.height:
        raise ValueError("Layout does not fit the sheet—adjust sizes or margins/gaps")

    # Build parts and place
    doors = [base.translate((0,0,0)) for _ in positions]
    placed = place_parts(doors, positions)

    # Exports
    export_doors(placed, DOORS_DIR)

    # CNC tool parameters
    cnc_params = cfg.get("cnc", {})
    tool_diameter = float(cnc_params.get("tool_diameter_mm", 6.35))  # Default 1/4" bit
    kerf_viz_depth = cnc_params.get("kerf_visualization_depth_mm")  # None = auto
    if kerf_viz_depth is not None:
        kerf_viz_depth = float(kerf_viz_depth)

    export_sheet_layout(sheet_wp, placed, OUTPUT_DIR / "sheet_layout.step",
                        tool_diameter=tool_diameter,
                        kerf_visualization_depth=kerf_viz_depth)

    # Minimal design intent
    bboxes = [rect_bbox(d) for d in placed]
    write_design_intent(bboxes, cfg, OUTPUT_DIR / "design_intent.json")

    return OUTPUT_DIR

def main():
    ap = argparse.ArgumentParser(description="CADQuery Layout Builder")
    ap.add_argument("--input", default=str(INPUT_DIR / "layout.json"), help="Path to layout.json")
    args = ap.parse_args()

    outdir = build_from_layout(Path(args.input))
    print(str(outdir))  # <-- prints the output directory

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # Ensure run.py surfaces errors
        print(f"[mill_ui_cq] ERROR: {e}", file=sys.stderr)
        sys.exit(1)
