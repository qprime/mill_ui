# path: skills/mill_ui/apps/compose_cam.py
from __future__ import annotations
import sys, json, argparse
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
from skills.mill_ui.cad.export.panel_stl import write_panel_stl

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
def _parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="compose_cam",
        description="Generate CAM outputs (G-code, reports, optional STL preview) for a sheet layout",
    )
    parser.add_argument("project", help="Project folder under memories/cam_projects/sheet_layouts")
    parser.add_argument(
        "--setup",
        action="store_true",
        help="Ensure project structure exists and layout.json is present/valid, then exit",
    )
    parser.add_argument(
        "--stl",
        action="store_true",
        help="Emit STL meshes (prefers precise CAD export; falls back to raster preview)",
    )
    parser.add_argument(
        "--stl-resolution-mm",
        type=float,
        default=0.3,
        help="Chordal tolerance (mm) for STL meshing when using CAD export",
    )
    parser.add_argument(
        "--profile-onion-skin-mm",
        type=float,
        help="Leave this thickness (mm) for a final skin pass on profiles",
    )
    parser.add_argument(
        "--tabs-count",
        type=int,
        help="Add evenly spaced tabs (count) on profile passes",
    )
    parser.add_argument(
        "--tabs-height-mm",
        type=float,
        help="Tab height in mm when tabs are enabled",
    )
    parser.add_argument(
        "--profile-cut-through-mm",
        type=float,
        help="Extra depth (mm) for profile passes to guarantee cut-through",
    )
    parser.add_argument(
        "--step",
        action="store_true",
        help="Emit a STEP preview (requires cadquery)",
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="Update input/layout.json from a STEP file in the project's input folder, then exit",
    )
    parser.add_argument(
        "--step-filename",
        type=str,
        default="panel_preview.step",
        help="Filename for the STEP preview (default: panel_preview.step)",
    )
    return parser.parse_args(argv)


def main(argv: List[str]) -> int:
    args = _parse_args(argv)

    project = args.project
    base = PROJECTS_ROOT / project
    in_path = base / "input" / "layout.json"
    outdir = base / "CAM"

    # --- Setup mode: ensure structure + validate layout.json ---
    if args.setup:
        from skills.mill_ui.io.layout_utils import (
            ensure_project_structure,
            skeleton_layout,
            write_layout,
            load_layout,
            validate_layout_json,
        )

        ensure_project_structure(base)
        created = False
        if not in_path.exists():
            write_layout(in_path, skeleton_layout())
            created = True

        # Validate JSON
        try:
            data = load_layout(in_path)
        except Exception as exc:
            print(f"Invalid JSON in {in_path}: {exc}", file=sys.stderr)
            return 2

        ok, msg = validate_layout_json(data)
        if not ok:
            print(f"Layout validation failed: {msg}", file=sys.stderr)
            return 2

        # Ensure CAM exists
        outdir.mkdir(parents=True, exist_ok=True)

        if created:
            print(f"Initialized project at {base} (created skeleton layout.json)")
        else:
            print(f"Project OK at {base}: layout.json valid and folders present")
        return 0

    # --- Update mode: read STEP from input/, update sheet dims in layout.json (do NOT write items) ---
    if args.update:
        from skills.mill_ui.io.layout_utils import (
            ensure_project_structure,
            skeleton_layout,
            write_layout,
            load_layout,
            validate_layout_json,
        )
        try:
            from skills.mill_ui.cad.importers.step_to_items import infer_layout_from_step
        except Exception as exc:
            print(f"Cannot update from STEP: {exc}", file=sys.stderr)
            return 2

        ensure_project_structure(base)

        # Find STEP file(s) in input folder
        input_dir = base / "input"
        step_candidates = []
        for pat in ("*.step", "*.stp", "*.STEP", "*.STP"):
            step_candidates.extend(sorted(input_dir.glob(pat)))
        step_candidates = sorted(set(step_candidates))
        if not step_candidates:
            print(f"No STEP files found in {input_dir} (expected .step or .stp)", file=sys.stderr)
            return 2
        step_path = step_candidates[0]
        if len(step_candidates) > 1:
            others = ", ".join(p.name for p in step_candidates[1:])
            print(f"[update] Using {step_path.name}; ignoring: {others}")

        # Load or create base layout
        if in_path.exists():
            try:
                base_layout = load_layout(in_path)
            except Exception as exc:
                print(f"Invalid JSON in {in_path}: {exc}", file=sys.stderr)
                return 2
        else:
            base_layout = skeleton_layout()

        # Build optional sheet overrides from base layout if it looks set
        sheet = base_layout.get("sheet") or {}
        sheet_overrides = {}
        try:
            w = float(sheet.get("width_mm", 0.0))
            h = float(sheet.get("height_mm", 0.0))
            t = float(sheet.get("thickness_mm", 0.0))
        except Exception:
            w = h = t = 0.0
        if w > 0: sheet_overrides["width_mm"] = w
        if h > 0: sheet_overrides["height_mm"] = h
        if t > 0: sheet_overrides["thickness_mm"] = t
        if not sheet_overrides:
            sheet_overrides = None

        # Infer from STEP (assume units mm; margin 5mm)
        try:
            inferred = infer_layout_from_step(step_path, units="mm", margin_mm=5.0, sheet_overrides=sheet_overrides)
        except Exception as exc:
            print(f"Failed to import STEP: {exc}", file=sys.stderr)
            return 2

        # Merge: keep items as-is; adopt sheet from inferred unless base already had nonzero dims
        merged = dict(base_layout)
        if not (w > 0 and h > 0 and t > 0):
            merged["sheet"] = inferred.get("sheet", merged.get("sheet", {}))

        ok, msg = validate_layout_json(merged)
        if not ok:
            print(f"Updated layout failed validation: {msg}", file=sys.stderr)
            return 2

        write_layout(in_path, merged)
        items_ct = len(merged.get("items", []))
        s = merged.get("sheet", {})
        print(f"Updated {in_path} (sheet from {step_path.name} when missing): items={items_ct}, sheet={s.get('width_mm')}×{s.get('height_mm')}×{s.get('thickness_mm')} mm")
        return 0

    if not in_path.exists():
        print(f"input not found: {in_path} (use --setup to create skeleton)", file=sys.stderr)
        return 2

    # 1) load layout
    data = _load_json(in_path)
    sheet = data.get("sheet") or {}
    panel_w = float(sheet.get("width_mm", 0.0))
    panel_h = float(sheet.get("height_mm", 0.0))
    panel_t = float(sheet.get("thickness_mm", 0.0))

    items = list(data.get("items") or [])

    # If no items are provided, try to import geometry directly from a STEP file in input/
    if not items:
        input_dir = base / "input"
        step_candidates = []
        for pat in ("*.step", "*.stp", "*.STEP", "*.STP"):
            step_candidates.extend(sorted(input_dir.glob(pat)))
        if step_candidates:
            try:
                from skills.mill_ui.cad.importers.step_to_items import infer_layout_from_step
            except Exception as exc:
                print(f"[compose_cam] STEP present but importer unavailable: {exc}", file=sys.stderr)
            else:
                step_path = sorted(set(step_candidates))[0]
                # Build sheet overrides from current sheet if provided
                sheet_overrides = None
                if panel_w > 0 and panel_h > 0 and panel_t > 0:
                    sheet_overrides = {"width_mm": panel_w, "height_mm": panel_h, "thickness_mm": panel_t}
                try:
                    inferred = infer_layout_from_step(step_path, units="mm", margin_mm=5.0, sheet_overrides=sheet_overrides)
                except Exception as exc:
                    print(f"[compose_cam] Failed to read STEP {step_path.name}: {exc}", file=sys.stderr)
                else:
                    if panel_w <= 0 or panel_h <= 0 or panel_t <= 0:
                        s = inferred.get("sheet", {})
                        panel_w = float(s.get("width_mm", panel_w))
                        panel_h = float(s.get("height_mm", panel_h))
                        panel_t = float(s.get("thickness_mm", panel_t))
                    items = list(inferred.get("items", []))
                    print(f"[compose_cam] Using STEP geometry from {step_path.name} (items={len(items)})")

    cam_cfg = data.get("cam") if isinstance(data.get("cam"), dict) else {}
    profile_cfg = cam_cfg.get("profile") if isinstance(cam_cfg.get("profile"), dict) else {}

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

    kerf_value = float(hints.get("kerf_width_mm", 0.0) or 0.0)

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

    profile_opts: Dict[str, Any] = {}

    # Layout defaults
    if isinstance(profile_cfg, dict):
        if "onion_skin_mm" in profile_cfg:
            try:
                val = float(profile_cfg.get("onion_skin_mm", 0.0))
                if val > 0.0:
                    profile_opts["onion_skin_mm"] = val
            except Exception:
                pass
        tabs_cfg_layout = profile_cfg.get("tabs") if isinstance(profile_cfg.get("tabs"), dict) else None
        if tabs_cfg_layout:
            try:
                cnt = int(tabs_cfg_layout.get("count", 0) or 0)
            except Exception:
                cnt = 0
            if cnt > 0:
                try:
                    height = float(tabs_cfg_layout.get("height_mm", 3.0))
                except Exception:
                    height = 3.0
                tabs_entry = {"count": cnt, "height_mm": height}
                if "width_mm" in tabs_cfg_layout:
                    try:
                        tabs_entry["width_mm"] = float(tabs_cfg_layout["width_mm"])
                    except Exception:
                        pass
                profile_opts["tabs"] = tabs_entry
        if "cut_through_mm" in profile_cfg:
            try:
                val = float(profile_cfg.get("cut_through_mm", 0.0))
                if val > 0.0:
                    profile_opts["cut_through_mm"] = val
            except Exception:
                pass

    # CLI overrides
    onion_cli_positive = False
    if args.profile_onion_skin_mm is not None:
        try:
            val = float(args.profile_onion_skin_mm)
        except Exception:
            val = 0.0
        if val > 0.0:
            profile_opts["onion_skin_mm"] = val
            onion_cli_positive = True
        else:
            profile_opts.pop("onion_skin_mm", None)

    tabs_from_cli = None
    tabs_cli_positive = False
    if args.tabs_count is not None:
        try:
            count_override = int(args.tabs_count)
        except Exception:
            count_override = 0
        if count_override > 0:
            tabs_from_cli = {"count": count_override}
            tabs_cli_positive = True
        else:
            profile_opts.pop("tabs", None)
    if (tabs_from_cli or "tabs" in profile_opts) and args.tabs_height_mm is not None:
        try:
            height_override = float(args.tabs_height_mm)
        except Exception:
            height_override = 3.0
        if tabs_from_cli:
            tabs_from_cli["height_mm"] = height_override
        else:
            profile_opts.setdefault("tabs", {})["height_mm"] = height_override
    if tabs_from_cli and "width_mm" in profile_opts.get("tabs", {}):
        tabs_from_cli.setdefault("width_mm", profile_opts["tabs"]["width_mm"])
    if tabs_from_cli:
        profile_opts["tabs"] = tabs_from_cli

    if args.profile_cut_through_mm is not None:
        try:
            val = float(args.profile_cut_through_mm)
        except Exception:
            val = 0.0
        if val > 0.0:
            profile_opts["cut_through_mm"] = val
        else:
            profile_opts.pop("cut_through_mm", None)

    if "tabs" in profile_opts:
        try:
            if profile_opts["tabs"].get("count", 0) <= 0:
                profile_opts.pop("tabs", None)
        except Exception:
            profile_opts.pop("tabs", None)

    if "onion_skin_mm" in profile_opts and "tabs" in profile_opts:
        if onion_cli_positive and not tabs_cli_positive:
            profile_opts.pop("tabs", None)
        elif tabs_cli_positive and not onion_cli_positive:
            profile_opts.pop("onion_skin_mm", None)
        else:
            print("Cannot combine onion-skin and tabs options yet.", file=sys.stderr)
            return 2

    passes, job_summary = plan_passes(
        hints,
        tool_db=tools,
        material=material,
        machine=machine,
        stock=stock,
        safe_z=float(SAFE_Z_MM),
        prime_spindle=False,
        profile_opts=profile_opts,
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

    has_polylines = any(str(it.get("type") or "").lower() == "polyline" for it in items_resolved)

    if args.stl:
        stl_base_path = outdir / "panel_preview.stl"
        mesh_tol = max(0.05, float(args.stl_resolution_mm))
        stl_outputs: List[Path] = []

        try:
            from skills.mill_ui.cad.step_export import SheetSpec, export_stl
        except ImportError:
            export_error = "cadquery is required for CAD-derived STL; falling back to raster heightfield"
            print(export_error, file=sys.stderr)
        else:
            if has_polylines:
                print("[panel_stl] Skipping CadQuery STL due to polyline engraves; using heightfield fallback", file=sys.stderr)
                export_stl = None  # type: ignore[assignment]
            else:
                sheet_spec = SheetSpec(width_mm=panel_w, height_mm=panel_h, thickness_mm=panel_t)
                try:
                    stl_outputs = export_stl(
                        sheet_spec,
                        items_resolved,
                        stl_base_path,
                        kerf_mm=kerf_value,
                        include_sheet=False,
                        include_floating_parts=True,
                        mesh_tolerance_mm=mesh_tol,
                        angular_tolerance_deg=5.0,
                    )
                except Exception as exc:  # pragma: no cover - cadquery backend
                    print(f"[!] STL export via CadQuery failed: {exc}; falling back to raster heightfield",
                          file=sys.stderr)
                    stl_outputs = []

        if not stl_outputs:
            stl_path = stl_base_path
            write_panel_stl(
                stl_path,
                width_mm=panel_w,
                height_mm=panel_h,
                thickness_mm=panel_t,
                items=items_resolved,
                resolution_mm=max(0.25, float(args.stl_resolution_mm)),
            )
            stl_outputs = [stl_path]

        made_files.extend(str(path) for path in stl_outputs)

    if args.step:
        try:
            from skills.mill_ui.cad.step_export import SheetSpec, export_step
        except ImportError as exc:
            print("cadquery is required for STEP export; install cadquery to enable --step", file=sys.stderr)
        else:
            if has_polylines:
                print("[STEP] Skipping output because polyline engraves would overwhelm CadQuery", file=sys.stderr)
            else:
                step_path = outdir / args.step_filename
                sheet_spec = SheetSpec(width_mm=panel_w, height_mm=panel_h, thickness_mm=panel_t)
                try:
                    export_step(sheet_spec, items_resolved, step_path, kerf_mm=kerf_value)
                    made_files.append(str(step_path))
                except Exception as exc:  # pragma: no cover - dependent on cadquery backend
                    print(f"[!] STEP export failed: {exc}", file=sys.stderr)

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
