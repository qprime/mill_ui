# path: skills/mill_ui/apps/compose_cam.py
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
from typing import Dict, Any, List, Tuple

from skills.mill_ui.compositions import resolve_templates  # auto-registers templates
from skills.mill_ui.cam.model.hints import build_cam_hints
from skills.mill_ui.cam.planner.pipeline import hints_to_moves
from skills.mill_ui.cam.post.gcode import write_gcode
from skills.mill_ui.cam.tools.adapter import load_tool_db, select_tools_for_job

from skills.mill_ui.cam.model.material import Material
from skills.mill_ui.cam.model.machine import Machine
from skills.mill_ui.cam.model.stock import Stock

def _size_of_item(it: Dict[str, Any]) -> Tuple[float, float]:
    k = it.get("kind")
    if k == "shape":
        t = (it.get("type") or "").lower()
        g = it.get("geometry") or {}
        if t == "rect":
            return float(g.get("w_mm", 0.0)), float(g.get("h_mm", 0.0))
        if t == "circle":
            d = float(g.get("diameter_mm", 0.0))
            return d, d
        if t == "polyline":
            pts = g.get("points") or []
            xs = [float(p[0]) for p in pts if isinstance(p, (list, tuple)) and len(p) == 2]
            ys = [float(p[1]) for p in pts if isinstance(p, (list, tuple)) and len(p) == 2]
            if not xs or not ys:
                return 0.0, 0.0
            return (max(xs) - min(xs), max(ys) - min(ys))
        return 0.0, 0.0
    if k == "template":
        t = (it.get("type") or "").lower()
        p = it.get("params") or {}
        if t == "shaker":
            return float(p.get("outer_w", 0.0)), float(p.get("outer_h", 0.0))
        if t == "circlemount":
            disk = p.get("disk") or {}
            if "diameter_mm" in disk:
                d = float(disk.get("diameter_mm", 0.0))
                return d, d
            port = p.get("port") or {}
            d = float(port.get("diameter_mm", port.get("diameter", 0.0)))
            return d, d
    return 0.0, 0.0

def _apply_grid_layout(panel_w: float, panel_h: float, layout: Dict[str, Any], items: List[Dict[str, Any]]) -> None:
    cols = int(layout.get("cols", 1))
    rows = int(layout.get("rows", 1))
    gap_x = float(layout.get("gap_x_mm", 0.0))
    gap_y = float(layout.get("gap_y_mm", 0.0))
    border = float(layout.get("border_mm", 0.0))
    fit = str(layout.get("fit", "tight")).lower()

    avail_w = panel_w - 2 * border - (cols - 1) * gap_x
    avail_h = panel_h - 2 * border - (rows - 1) * gap_y
    if avail_w <= 0 or avail_h <= 0:
        raise ValueError("Grid + borders/gaps leave no interior area")

    sizes = [_size_of_item(it) for it in items]
    if fit == "tight":
        max_w = max((w for (w, _) in sizes), default=0.0)
        max_h = max((h for (_, h) in sizes), default=0.0)
        cell_w, cell_h = max_w, max_h
        block_w = cols * cell_w + (cols - 1) * gap_x
        block_h = rows * cell_h + (rows - 1) * gap_y
        if block_w > avail_w + 1e-6 or block_h > avail_h + 1e-6:
            raise ValueError("Tight pack does not fit grid interior")
    else:
        cell_w = avail_w / cols
        cell_h = avail_h / rows

    idx = 0
    for r in range(rows):
        for c in range(cols):
            if idx >= len(items):
                return
            cx = border + c * (cell_w + gap_x) + cell_w * 0.5
            cy = border + r * (cell_h + gap_y) + cell_h * 0.5
            items[idx].setdefault("placement", {})["center_xy_mm"] = (cx, cy)
            idx += 1

def _load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)

def _save_text(path: Path, s: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(s, encoding="utf-8")

def _save_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")

def _default_tool_db() -> List[Dict[str, Any]]:
    return [
        {"name": "SmallFlat", "diameter": 3.175, "kind": "flat", "rpm": 14000, "feed_xy": 900, "feed_z": 300},
        {"name": "BigFlat",   "diameter": 6.35,  "kind": "flat", "rpm": 12000, "feed_xy": 800, "feed_z": 280},
    ]

def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(prog="compose_cam", description="Resolve compositions, plan CAM, write G-code.")
    ap.add_argument("--input", required=True, help="Input JSON (sheet/layout/items/templates).")
    ap.add_argument("--outdir", required=True, help="Output directory for artifacts.")
    ap.add_argument("--tool-db", default="", help="Path to rich tool_db.json.")
    ap.add_argument("--material", default="MDF", help="Material key in tool_db.json feeds_speeds.")
    ap.add_argument("--safe-z", type=float, default=6.0)
    ap.add_argument("--prime-spindle", action="store_true", help="Insert M3 S0 via set_rpm=0 at job start.")
    ap.add_argument("--auto-select", action="store_true", help="Select job tools via tool_selection_rules.")
    args = ap.parse_args(argv)

    in_path = Path(args.input)
    outdir = Path(args.outdir)

    data = _load_json(in_path)

    sheet = data.get("sheet") or {}
    panel_w = float(sheet.get("width_mm", 0.0))
    panel_h = float(sheet.get("height_mm", 0.0))
    panel_t = float(sheet.get("thickness_mm", 0.0))

    items = list(data.get("items") or [])

    layout = data.get("layout")
    if isinstance(layout, dict):
        _apply_grid_layout(panel_w, panel_h, layout, items)

    # 1) resolve templates → concrete shapes (centered; then offset by placement if provided)
    items_resolved = resolve_templates(items, sheet_thickness_mm=panel_t)

    # 2) build hints
    hints = build_cam_hints(
        items_resolved=items_resolved,
        sheet_thickness=panel_t,
        kerf_width_mm=float(data.get("kerf_width_mm", 0.0))
    )

    # 3) tool database
    if args.tool_db:
        tools = (select_tools_for_job(args.tool_db, material=args.material)
                 if args.auto_select else load_tool_db(args.tool_db, material=args.material))
    else:
        tools = _default_tool_db()

    # 4) plan + post
    material = Material(name=args.material)
    machine = Machine(name="default_grbl")
    stock = Stock(width=panel_w, height=panel_h, thickness=panel_t)

    moves = hints_to_moves(hints, tool_db=tools, material=material, machine=machine, stock=stock, safe_z=float(args.safe_z))

    if args.prime_spindle:
        # prepend set_rpm=0 to generate 'M3 S0' in header per Claude's suggestion (optional)
        moves = [{"kind": "set_rpm", "rpm": 0}] + moves

    gcode = write_gcode(moves, safe_z=float(args.safe_z))

    # 5) write artifacts
    job = in_path.stem
    _save_json(outdir / f"{job}_items_resolved.json", items_resolved)
    _save_json(outdir / f"{job}_hints.json", hints)
    _save_text(outdir / f"{job}.nc", gcode)

    print(str(outdir / f"{job}.nc"))
    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
