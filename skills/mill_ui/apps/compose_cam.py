# path: skills/mill_ui/apps/compose_cam.py
from __future__ import annotations
import sys, json
from pathlib import Path
from typing import Dict, Any, List, Tuple

# Compositions auto-register templates
from skills.mill_ui.compositions import resolve_templates

# CAM pipeline pieces
from skills.mill_ui.cam.model.hints import build_cam_hints
from skills.mill_ui.cam.planner.passes import plan_passes
from skills.mill_ui.cam.post.gcode import write_gcode
from skills.mill_ui.cam.tools.adapter import load_tool_db

from skills.mill_ui.cam.model.material import Material
from skills.mill_ui.cam.model.machine import Machine
from skills.mill_ui.cam.model.stock import Stock

from skills.mill_ui.cad.export.svg_dims import render_svg_with_dims

# --------------------
# HARD-CODED DEFAULTS
# --------------------
# !!! UPDATE THIS PATH to your real DB if needed:
TOOL_DB_PATH = Path("skills/mill_ui/cam/tools/tool_db.json")   # <-- set to your tool_db.json
MATERIAL_NAME = "MDF"       # feeds/speeds profile to use from the DB
SAFE_Z_MM = 6.0             # clearance height (mm) above TOP
PROJECTS_ROOT = Path("memories/cam_projects/sheet_layouts")

# Match your legacy Z convention:
#   stock BOTTOM = Z 0, stock TOP = Z thickness.
Z_REFERENCE = "top"

# --------------------
# IO helpers
# --------------------
def _load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)

def _save_text(path: Path, s: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(s, encoding="utf-8")

def _save_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")

# --------------------
# Layout helpers (grid before resolve)
# --------------------
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

def _apply_grid_layout(panel_w: float, panel_h: float, layout: Dict[str, Any],
                       items: List[Dict[str, Any]], *, kerf_hint: float = 0.0) -> None:
    """
    Place items into a rows×cols grid on a panel, honoring gap semantics:

      - gap_mode: "zero"    -> gap_x = gap_y = 0.00 (shared seams => one cut)
      - gap_mode: "kerf"    -> gap_x = gap_y = kerf + gap_clearance_mm (default 0.10)
      - gap_mode: "explicit" (default) -> use gap_x_mm / gap_y_mm as provided
      - seam_clearance_mm (optional) overrides both gaps directly (explicit)

    Only perimeter profiles that physically touch in design space will be eligible
    for common-line cutting downstream. Internal items (pockets/holes) are independent.

    kerf_hint: top-level kerf_width_mm passed in by the caller.
    """
    # --- gaps from mode ---
    gap_mode = str(layout.get("gap_mode", "explicit")).lower()   # "explicit" | "kerf" | "zero"
    kerf_mm = float(layout.get("kerf_width_mm", kerf_hint or 0.0))

    if "seam_clearance_mm" in layout:
        gap_x = gap_y = float(layout.get("seam_clearance_mm", 0.0))
    else:
        if gap_mode == "zero":
            gap_x = gap_y = 0.0
        elif gap_mode == "kerf":
            clearance = float(layout.get("gap_clearance_mm", 0.10))
            gap_x = gap_y = float(kerf_mm) + clearance
        else:  # "explicit" (or anything else)
            gap_x = float(layout.get("gap_x_mm", 0.0))
            gap_y = float(layout.get("gap_y_mm", 0.0))

    # --- grid dims ---
    cols = int(layout.get("cols", 1))
    rows = int(layout.get("rows", 1))
    border = float(layout.get("border_mm", 0.0))
    fit = str(layout.get("fit", "tight")).lower()  # "tight" or "even"

    # interior usable area (do NOT subtract gaps here; they belong to the block we place)
    inner_w = panel_w - 2.0 * border
    inner_h = panel_h - 2.0 * border
    if inner_w <= 0.0 or inner_h <= 0.0:
        raise ValueError("Grid + borders leave no interior area")

    # cell size
    if fit == "tight":
        # cells fit the max item size; block must fit the inner rectangle
        max_w = max((_size_of_item(it)[0] for it in items), default=0.0)
        max_h = max((_size_of_item(it)[1] for it in items), default=0.0)
        cell_w, cell_h = max_w, max_h
        block_w = cols * cell_w + (cols - 1) * gap_x
        block_h = rows * cell_h + (rows - 1) * gap_y
        if block_w > inner_w + 1e-6 or block_h > inner_h + 1e-6:
            raise ValueError("Tight pack does not fit grid interior")
    else:
        # evenly divide inner area into cells, leaving the specified gaps between them
        cell_w = (inner_w - (cols - 1) * gap_x) / cols
        cell_h = (inner_h - (rows - 1) * gap_y) / rows
        if cell_w <= 0.0 or cell_h <= 0.0:
            raise ValueError("Grid + borders/gaps leave no interior area")

    # --- placement (row-major) ---
    idx = 0
    for r in range(rows):
        for c in range(cols):
            if idx >= len(items):
                return
            cx = border + c * (cell_w + gap_x) + 0.5 * cell_w
            cy = border + r * (cell_h + gap_y) + 0.5 * cell_h
            items[idx].setdefault("placement", {})["center_xy_mm"] = (cx, cy)
            idx += 1


# --------------------
# main
# --------------------
def main(argv: List[str]) -> int:
    if len(argv) != 1:
        print("usage: compose_cam <project_name>", file=sys.stderr)
        print("  expects: memories/cam_projects/sheet_layouts/<project>/input/layout.json", file=sys.stderr)
        return 2

    project = argv[0]
    base = PROJECTS_ROOT / project
    in_path = base / "input" / "layout.json"
    outdir = base / "CAM"

    if not in_path.exists():
        print(f"input not found: {in_path}", file=sys.stderr)
        return 2

    # 1) load layout
    data = _load_json(in_path)
    sheet = data.get("sheet") or {}
    panel_w = float(sheet.get("width_mm", 0.0))
    panel_h = float(sheet.get("height_mm", 0.0))
    panel_t = float(sheet.get("thickness_mm", 0.0))

    items = list(data.get("items") or [])

    # 2) apply grid placement BEFORE resolving templates
    layout = data.get("layout")
    if isinstance(layout, dict):
        _apply_grid_layout(
            panel_w, panel_h, layout, items,
            kerf_hint=float(data.get("kerf_width_mm", 0.0))   # <— add this arg
        )  # grid BEFORE resolve

    # 3) resolve templates -> concrete shapes (centered; then offset by placement if present)
    items_resolved = resolve_templates(items, sheet_thickness_mm=panel_t)

    # 4) build hints
    hints = build_cam_hints(
        items_resolved=items_resolved,
        sheet_thickness=panel_t,
        kerf_width_mm=float(data.get("kerf_width_mm", 0.0))
    )

    # --- write dimensioned layout SVG (layout_dims.svg) ---
    svg_dims = render_svg_with_dims(
        panel_w, panel_h, panel_t,
        placements=[{"item": it, "center_xy_mm": (it.get("placement") or {}).get("center_xy_mm", (0.0, 0.0))} for it in items],
        hints=hints,
        tol_mm=0.25,
    )
    _save_text(outdir / "layout_dims.svg", svg_dims)


    # 5) load REAL tool DB (hard-coded path)
    if not TOOL_DB_PATH.exists():
        print(f"tool_db.json not found at: {TOOL_DB_PATH}\n"
              f"--> Update TOOL_DB_PATH in skills/mill_ui/apps/compose_cam.py", file=sys.stderr)
        return 2
    tools = load_tool_db(str(TOOL_DB_PATH), material=MATERIAL_NAME)

    # 6) plan grouped passes
    material = Material(name=MATERIAL_NAME)
    machine = Machine(name="default_grbl")
    stock = Stock(width=panel_w, height=panel_h, thickness=panel_t)

    passes, job_summary = plan_passes(
        hints,
        tool_db=tools,
        material=material,
        machine=machine,
        stock=stock,
        safe_z=float(SAFE_Z_MM),
        prime_spindle=False,
    )

    # 7) optional Z remap to bottom-zero coordinates (legacy convention)
    def _remap_z_for_bottom(mv: Dict[str, Any], t: float) -> Dict[str, Any]:
        if "z" in mv and mv["z"] is not None:
            mv = dict(mv); mv["z"] = t + float(mv["z"])
        return mv

    outdir.mkdir(parents=True, exist_ok=True)
    made_files: List[str] = []
    for p in passes:
        moves = p["moves"]
        if Z_REFERENCE == "bottom":
            moves = [_remap_z_for_bottom(m, panel_t) for m in moves]
            safe_z = panel_t + SAFE_Z_MM
        else:
            safe_z = SAFE_Z_MM

        gcode = write_gcode(moves, safe_z=safe_z)
        fpath = outdir / p["filename"]
        _save_text(fpath, gcode)
        made_files.append(str(fpath))

    # 8) summary.json
    job_summary.update({
        "project": project,
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
