"""Compose CAM outputs for a sheet layout with configurable inputs."""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import random
import sys
import textwrap
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple
import copy

from skills.mill_ui.core import Config, get_capabilities, load_config
from skills.mill_ui.core.version import get_build_version, git_sha
from skills.mill_ui.cad.ingest.sanitize import canonicalize_items
from skills.mill_ui.cad.export.svg_dims import render_svg_with_dims
from skills.mill_ui.cad.export.step import SheetSpec, export_step, export_stl
from skills.mill_ui.cad.export.panel_stl import write_panel_stl
from skills.mill_ui.cam.model.hints import build_cam_hints
from skills.mill_ui.cam.model.machine import Machine
from skills.mill_ui.cam.model.material import Material
from skills.mill_ui.cam.model.stock import Stock
from skills.mill_ui.cam.planner.passes import plan_passes
from skills.mill_ui.cam.post.gcode import write_gcode
from skills.mill_ui.cam.tools.adapter import load_tool_db
from skills.mill_ui.compositions import resolve_templates

os.environ.setdefault("PYTHONHASHSEED", "0")
random.seed(0)
try:  # numpy is optional in this environment
    import numpy as np

    np.random.seed(0)
except Exception:  # pragma: no cover - optional dependency
    pass

LOGGER = logging.getLogger("compose_cam")
PACKAGE_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = PACKAGE_ROOT.parent


def _load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _save_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _save_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _hash_file(path: Path) -> str | None:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(8192), b""):
                if not chunk:
                    break
                digest.update(chunk)
    except OSError:
        return None
    return digest.hexdigest()


def _artifact_entry(path: Path) -> Optional[Dict[str, Any]]:
    try:
        stats = path.stat()
    except OSError:
        return None
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(8192), b""):
                if not chunk:
                    break
                digest.update(chunk)
    except OSError:
        return None
    return {
        "path": str(path),
        "name": path.name,
        "bytes": int(stats.st_size),
        "sha256": digest.hexdigest(),
    }


def _default_config_search_paths() -> List[Path]:
    return [Path.cwd(), PACKAGE_ROOT, REPO_ROOT]


def _resolve_path(path: Optional[Path], bases: Sequence[Path]) -> Optional[Path]:
    if path is None:
        return None
    candidates: List[Path] = []
    if path.is_absolute():
        candidates.append(path)
    else:
        for base in bases:
            candidates.append((base / path).expanduser())
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved.exists():
            return resolved
    return candidates[0].resolve()


def _resolve_layout_paths(target: str, config: Config) -> Tuple[Path, Path, str]:
    raw = Path(target)
    project_root = _resolve_path(config.project_root, [Path.cwd(), REPO_ROOT])

    def _candidate_files() -> List[Path]:
        bases: List[Path] = []
        if raw.is_absolute():
            bases.append(raw)
        else:
            bases.extend([(Path.cwd() / raw), raw])
            if project_root is not None:
                bases.append(project_root / raw)
        return bases

    layout_path: Optional[Path] = None
    for candidate in _candidate_files():
        candidate = candidate.expanduser()
        if candidate.is_file():
            layout_path = candidate
            break
        if candidate.is_dir():
            candidate_layout = candidate / "input" / "layout.json"
            if candidate_layout.exists():
                layout_path = candidate_layout
                break
        if candidate.suffix.lower() == ".json":
            potential = candidate if candidate.is_absolute() else (Path.cwd() / candidate)
            if potential.exists():
                layout_path = potential
                break
    if layout_path is None:
        base = raw if raw.is_absolute() else (project_root / raw if project_root else Path.cwd() / raw)
        layout_path = (base / "input" / "layout.json").expanduser()

    layout_path = layout_path.resolve()
    if not layout_path.exists():
        raise FileNotFoundError(f"Layout file not found: {layout_path}")

    if layout_path.parent.name.lower() == "input":
        base_dir = layout_path.parent.parent
    else:
        base_dir = layout_path.parent
    outdir = base_dir / "CAM"
    project_name = base_dir.name or layout_path.stem
    return layout_path, outdir, project_name


def _append_note(notes: List[str], message: str) -> None:
    if message not in notes:
        notes.append(message)


def _positive_float(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return number if number > 0.0 else 0.0


def _positive_int(value: Any) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return 0
    return number if number > 0 else 0


def _profile_options_from_sources(
    profile_cfg: Optional[Mapping[str, Any]],
    args: argparse.Namespace,
) -> Tuple[Dict[str, Any], Optional[str]]:
    opts: Dict[str, Any] = {}

    if isinstance(profile_cfg, Mapping):
        onion_layout = _positive_float(profile_cfg.get("onion_skin_mm"))
        if onion_layout > 0.0:
            opts["onion_skin_mm"] = onion_layout
        tabs_cfg = profile_cfg.get("tabs")
        if isinstance(tabs_cfg, Mapping):
            count_layout = _positive_int(tabs_cfg.get("count"))
            if count_layout > 0:
                tabs_entry: Dict[str, Any] = {"count": count_layout}
                height_layout = _positive_float(tabs_cfg.get("height_mm")) or 3.0
                tabs_entry["height_mm"] = height_layout
                width_layout = _positive_float(tabs_cfg.get("width_mm"))
                if width_layout > 0.0:
                    tabs_entry["width_mm"] = width_layout
                opts["tabs"] = tabs_entry
        cut_layout = _positive_float(profile_cfg.get("cut_through_mm"))
        if cut_layout > 0.0:
            opts["cut_through_mm"] = cut_layout

    if args.profile_onion_skin_mm is not None:
        onion_cli = _positive_float(args.profile_onion_skin_mm)
        if onion_cli > 0.0:
            opts["onion_skin_mm"] = onion_cli
        else:
            opts.pop("onion_skin_mm", None)

    if args.tabs_count is not None:
        count_cli = _positive_int(args.tabs_count)
        if count_cli > 0:
            tabs_entry = dict(opts.get("tabs", {}))
            tabs_entry["count"] = count_cli
            opts["tabs"] = tabs_entry
        else:
            opts.pop("tabs", None)

    if args.tabs_height_mm is not None and "tabs" in opts:
        height_cli = _positive_float(args.tabs_height_mm)
        if height_cli > 0.0:
            opts.setdefault("tabs", {})["height_mm"] = height_cli

    if args.profile_cut_through_mm is not None:
        cut_cli = _positive_float(args.profile_cut_through_mm)
        if cut_cli > 0.0:
            opts["cut_through_mm"] = cut_cli
        else:
            opts.pop("cut_through_mm", None)

    if "tabs" in opts:
        tabs_entry = dict(opts["tabs"])
        count_val = _positive_int(tabs_entry.get("count"))
        if count_val <= 0:
            opts.pop("tabs", None)
        else:
            tabs_entry["count"] = count_val
            tabs_entry.setdefault("height_mm", 3.0)
            opts["tabs"] = tabs_entry

    onion_positive = _positive_float(opts.get("onion_skin_mm")) > 0.0
    tabs_positive = "tabs" in opts and _positive_int(opts["tabs"].get("count")) > 0
    if onion_positive and tabs_positive:
        return opts, "Cannot combine onion-skin and tabs options yet."

    return opts, None


def _remap_z_for_bottom(move: Mapping[str, Any], thickness: float) -> Dict[str, Any]:
    updated = dict(move)
    if "z" in updated and updated["z"] is not None:
        updated["z"] = float(updated["z"]) + float(thickness)
    return updated


def _parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="compose_cam",
        description="Generate CAM outputs (G-code, reports, optional STL preview) for a sheet layout",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent(
            """
            Examples:
              compose_cam.py layout.json --tool-db ./tools.db --material MDF --safe-z 6 --z-ref top
              CAM_TOOL_DB=./tools.db CAM_SAFE_Z=8 python apps/compose_cam.py layout.json
              compose_cam.py layout.json --config ./config.json --merge-eps 0.02
            """
        ),
    )
    parser.add_argument("layout", nargs="?", help="Path to layout.json or project identifier")

    parser.add_argument("--config", dest="config_path", type=Path, help="Path to a configuration JSON file")
    parser.add_argument("--tool-db", dest="tool_db_path", type=Path, help="Override the tool database path")
    parser.add_argument("--project-root", dest="project_root", type=Path, help="Override the project root directory")
    parser.add_argument("--material", dest="material_name", help="Material name for feeds/speeds lookup")
    parser.add_argument("--safe-z", dest="safe_z_mm", type=float, help="Safe Z clearance height in mm")
    parser.add_argument("--z-ref", dest="z_reference", choices=["top", "bottom"], help="Reference plane for Z outputs")
    parser.add_argument("--merge-eps", dest="merge_epsilon_mm", type=float, help="Tolerance (mm) for shared-edge detection")
    parser.add_argument("--min-overlap-mm", dest="min_overlap_mm", type=float, help="Minimum overlap length (mm) for seam merging")
    parser.add_argument("--min-overlap-ratio", dest="min_overlap_ratio", type=float, help="Minimum overlap ratio for seam merging")
    parser.add_argument("--cleanup-offset-mm", dest="cleanup_offset_mm", type=float, help="Pocket cleanup offset (mm)")
    parser.add_argument("--colinear-eps", dest="colinear_epsilon_deg", type=float, help="Angular tolerance (degrees) for colinearity checks")

    parser.add_argument("--stl", action="store_true", help="Emit STL meshes using the native CAD exporter when available")
    parser.add_argument("--stl-resolution-mm", type=float, default=0.3, help="Chordal tolerance (mm) for STL meshing")
    parser.add_argument("--step", action="store_true", help="Emit a STEP preview using the native CAD exporter")
    parser.add_argument("--step-filename", type=str, default="panel_preview.step", help="Filename for the STEP preview")

    parser.add_argument("--profile-onion-skin-mm", type=float, help="Leave this thickness (mm) for a final skin pass on profiles")
    parser.add_argument("--tabs-count", type=int, help="Add evenly spaced tabs (count) on profile passes")
    parser.add_argument("--tabs-height-mm", type=float, help="Tab height in mm when tabs are enabled")
    parser.add_argument("--profile-cut-through-mm", type=float, help="Extra depth (mm) for profile passes to guarantee cut-through")

    parser.add_argument("--version", action="store_true", help="Print version information and exit")
    args = parser.parse_args(argv)
    if not args.version and not args.layout:
        parser.error("layout argument is required unless --version is used")
    return args


def main(argv: Sequence[str]) -> int:
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
    args = _parse_args(argv)

    if args.version:
        print(f"compose_cam version: {get_build_version()}")
        return 0

    try:
        config = load_config(
            cli_args=args,
            env=os.environ,
            config_path=args.config_path,
            search_paths=_default_config_search_paths(),
        )
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    try:
        config_hash = hashlib.sha256(
            json.dumps(config.as_dict(), sort_keys=True).encode("utf-8")
        ).hexdigest()
    except Exception:
        config_hash = None

    try:
        layout_path, outdir, project_name = _resolve_layout_paths(args.layout, config)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    data = _load_json(layout_path)
    sheet = data.get("sheet") or {}
    panel_w = float(sheet.get("width_mm", 0.0))
    panel_h = float(sheet.get("height_mm", 0.0))
    panel_t = float(sheet.get("thickness_mm", 0.0))

    items_raw = list(data.get("items") or [])
    items = canonicalize_items(items_raw)

    layout = data.get("layout") if isinstance(data.get("layout"), Mapping) else None
    if layout:
        _apply_grid_layout(panel_w, panel_h, layout, items, kerf_hint=float(data.get("kerf_width_mm", 0.0)))

    items_resolved = resolve_templates(items, sheet_thickness_mm=panel_t)
    hints = build_cam_hints(
        items_resolved=items_resolved,
        sheet_thickness=panel_t,
        kerf_width_mm=float(data.get("kerf_width_mm", 0.0)),
    )

    svg_dims = render_svg_with_dims(
        panel_w,
        panel_h,
        panel_t,
        placements=[{"item": it, "center_xy_mm": (it.get("placement") or {}).get("center_xy_mm", (0.0, 0.0))} for it in items],
        hints=hints,
        tol_mm=0.25,
    )

    tool_db_path = _resolve_path(config.tool_db_path, [outdir.parent, REPO_ROOT])
    if tool_db_path is None or not tool_db_path.exists():
        message = "Tool database not found at: {}".format(tool_db_path or "<unset>")
        print(message, file=sys.stderr)
        print("Set CAM_TOOL_DB or use --tool-db to provide a valid path.", file=sys.stderr)
        return 2

    tool_db_hash = _hash_file(tool_db_path)
    try:
        tool_db_raw = _load_json(tool_db_path)
    except Exception:
        tool_db_raw = {}

    material_name = config.material_name or "MDF"
    tools = load_tool_db(str(tool_db_path), material=material_name)

    machine_profile_name = None
    if isinstance(tool_db_raw, Mapping):
        raw_profile = tool_db_raw.get("machine_profile")
        if isinstance(raw_profile, Mapping):
            name_val = raw_profile.get("name")
            if isinstance(name_val, str) and name_val.strip():
                machine_profile_name = name_val

    material = Material(name=material_name)
    machine = Machine(name="default_grbl")
    stock = Stock(width=panel_w, height=panel_h, thickness=panel_t)

    profile_cfg = data.get("cam", {}).get("profile") if isinstance(data.get("cam"), Mapping) else None
    profile_opts, profile_error = _profile_options_from_sources(profile_cfg, args)
    if profile_error:
        print(profile_error, file=sys.stderr)
        return 2

    passes, job_summary = plan_passes(
        hints,
        config=config,
        tool_db=tools,
        material=material,
        machine=machine,
        stock=stock,
        safe_z=config.safe_z_mm,
        profile_opts=profile_opts,
    )

    outdir.mkdir(parents=True, exist_ok=True)
    made_files: List[str] = []
    additional_notes: List[str] = []

    caps = get_capabilities()

    for planned in passes:
        moves = planned["moves"]
        if config.z_reference == "bottom":
            mapped_moves = [_remap_z_for_bottom(mv, panel_t) for mv in moves]
            safe_z_value = panel_t + config.safe_z_mm
        else:
            mapped_moves = moves
            safe_z_value = config.safe_z_mm
        gcode = write_gcode(mapped_moves, safe_z=safe_z_value)
        gcode_path = outdir / planned["filename"]
        _save_text(gcode_path, gcode)
        made_files.append(str(gcode_path))

    stl_outputs: List[Path] = []
    if args.stl:
        fallback_to_heightfield = False
        stl_base = outdir / "panel_preview.stl"
        if caps.native_cad:
            sheet_spec = SheetSpec(width_mm=panel_w, height_mm=panel_h, thickness_mm=panel_t)
            try:
                # Export both sheet (with pockets/recesses) and floating parts (slugs) so parts aren't missing.
                stl_outputs = export_stl(
                    sheet_spec,
                    items_resolved,
                    stl_base,
                    kerf_mm=float(hints.get("kerf_width_mm", 0.0)),
                    include_sheet=True,
                    include_floating_parts=True,
                    mesh_tolerance_mm=max(0.05, float(args.stl_resolution_mm)),
                )
            except Exception as exc:  # pragma: no cover - native exporter errors
                LOGGER.warning("Native STL export failed (%s); falling back to heightfield", exc)
                fallback_to_heightfield = True
        else:
            fallback_to_heightfield = True
            LOGGER.info("Native CAD backends unavailable: using heightfield STL fallback.")
            _append_note(additional_notes, "Native CAD backends unavailable: produced SVG/STL (heightfield) only.")

        if fallback_to_heightfield:
            write_panel_stl(
                stl_base,
                width_mm=panel_w,
                height_mm=panel_h,
                thickness_mm=panel_t,
                items=items_resolved,
                resolution_mm=max(0.25, float(args.stl_resolution_mm)),
            )
            stl_outputs = [stl_base]

        made_files.extend(str(path) for path in stl_outputs)

    if args.step:
        if caps.native_cad:
            sheet_spec = SheetSpec(width_mm=panel_w, height_mm=panel_h, thickness_mm=panel_t)
            step_path = outdir / args.step_filename
            try:
                export_step(sheet_spec, items_resolved, step_path, kerf_mm=float(hints.get("kerf_width_mm", 0.0)))
                made_files.append(str(step_path))
            except Exception as exc:  # pragma: no cover - native exporter errors
                LOGGER.warning("STEP export failed: %s", exc)
        else:
            _append_note(additional_notes, "Native CAD backends unavailable: produced SVG/STL (heightfield) only.")
            LOGGER.info("Native CAD backends unavailable: skipping STEP export.")

    summary_path = outdir / "summary.json"
    build_version = get_build_version()
    code_sha = git_sha(short=True) or git_sha(short=False)
    artifacts: List[Dict[str, Any]] = []
    for produced in made_files:
        entry = _artifact_entry(Path(produced))
        if entry:
            artifacts.append(entry)

    job_summary["schema_version"] = "1.0"
    job_summary.update(
        {
            "project": project_name,
            "sheet": {"width_mm": panel_w, "height_mm": panel_h, "thickness_mm": panel_t},
            "output_dir": str(outdir),
            "files": [Path(f).name for f in made_files],
        }
    )
    job_summary["provenance"] = {
        "code_git_sha": code_sha,
        "tool_db_hash": tool_db_hash,
        "config_hash": config_hash,
        "native_caps": {
            "cad": bool(caps.native_cad),
            "cam": bool(getattr(caps, "native_cam", False)),
        },
        "machine_profile": machine_profile_name,
        "generated_by": {
            "app": "compose_cam",
            "version": build_version,
        },
        "artifacts": artifacts,
    }
    if additional_notes:
        note = job_summary.get("notes", "")
        joined = " | ".join(additional_notes)
        job_summary["notes"] = f"{note} | {joined}" if note else joined
    _save_json(summary_path, job_summary)

    _save_text(outdir / "layout_dims.svg", svg_dims)

    for file_path in made_files:
        print(file_path)
    print(summary_path)
    return 0


def _apply_grid_layout(
    panel_w: float,
    panel_h: float,
    layout: Mapping[str, Any],
    items: List[Dict[str, Any]],
    *,
    kerf_hint: float = 0.0,
) -> None:
    gap_mode = str(layout.get("gap_mode", "explicit")).lower()
    kerf_mm = float(layout.get("kerf_width_mm", kerf_hint or 0.0))

    if "seam_clearance_mm" in layout:
        gap_x = gap_y = float(layout.get("seam_clearance_mm", 0.0))
    else:
        if gap_mode == "zero":
            gap_x = gap_y = 0.0
        elif gap_mode == "kerf":
            clearance = float(layout.get("gap_clearance_mm", 0.10))
            gap_x = gap_y = float(kerf_mm) + clearance
        else:
            gap_x = float(layout.get("gap_x_mm", 0.0))
            gap_y = float(layout.get("gap_y_mm", 0.0))

    cols = max(1, int(layout.get("cols", 1)))
    rows = max(1, int(layout.get("rows", 1)))
    border = float(layout.get("border_mm", 0.0))
    fit = str(layout.get("fit", "tight")).lower()
    origin = str(layout.get("origin", "center")).lower()
    anchor = str(layout.get("anchor", "center")).lower()
    pattern_cfg = layout.get("pattern")
    repeat_pattern = False
    if isinstance(pattern_cfg, Mapping):
        repeat_pattern = bool(pattern_cfg.get("repeat", True))
    elif isinstance(pattern_cfg, bool):
        repeat_pattern = pattern_cfg
    elif isinstance(pattern_cfg, str):
        repeat_pattern = pattern_cfg.strip().lower() in {"repeat", "true", "yes"}
    else:
        repeat_pattern = bool(layout.get("repeat"))

    inner_w = panel_w - 2.0 * border
    inner_h = panel_h - 2.0 * border
    if inner_w <= 0.0 or inner_h <= 0.0:
        raise ValueError("Grid + borders leave no interior area")

    def _size_of_item(it: Mapping[str, Any]) -> Tuple[float, float]:
        kind = str(it.get("kind", "shape")).lower()
        if kind == "shape":
            geom = it.get("geometry") or {}
            shape_type = str(it.get("type", "")).lower()
            if shape_type == "rect":
                return float(geom.get("w_mm", 0.0)), float(geom.get("h_mm", 0.0))
            if shape_type == "circle":
                diameter = float(geom.get("diameter_mm", 0.0))
                return diameter, diameter
            if shape_type == "polyline":
                pts = geom.get("points") or []
                xs = [float(pt[0]) for pt in pts if isinstance(pt, (list, tuple)) and len(pt) == 2]
                ys = [float(pt[1]) for pt in pts if isinstance(pt, (list, tuple)) and len(pt) == 2]
                if xs and ys:
                    return max(xs) - min(xs), max(ys) - min(ys)
        if kind == "template":
            template_type = str(it.get("type", "")).lower()
            params = it.get("params") or {}
            if template_type == "shaker":
                ow = float(params.get("outer_w", 0.0))
                oh = float(params.get("outer_h", 0.0))
                if ow <= 0.0 or oh <= 0.0:
                    iw = float(params.get("inner_w", 0.0))
                    ih = float(params.get("inner_h", 0.0))
                    stile = float(params.get("stile_w", 0.0))
                    rail = float(params.get("rail_h", 0.0))
                    if iw > 0.0:
                        ow = max(ow, iw + 2.0 * max(stile, 0.0))
                    if ih > 0.0:
                        oh = max(oh, ih + 2.0 * max(rail, 0.0))
                return ow, oh
            if template_type == "insetframe":
                ow = float(params.get("outer_w_mm", 0.0))
                oh = float(params.get("outer_h_mm", 0.0))
                if ow <= 0.0 or oh <= 0.0:
                    lip = float(params.get("lip_inset_mm", 3.0))
                    recess = float(params.get("recess_extra_inset_mm", 3.0))
                    aw = float(params.get("aperture_w_mm", 0.0))
                    ah = float(params.get("aperture_h_mm", 0.0))
                if aw > 0.0:
                    ow = max(ow, aw + 2.0 * (lip + recess))
                if ah > 0.0:
                    oh = max(oh, ah + 2.0 * (lip + recess))
                return ow, oh
            if template_type == "clampbar":
                length = float(params.get("length_mm", params.get("length", 0.0)))
                height_a = float(params.get("height_a_mm", params.get("height_a", 0.0)))
                height_b = float(params.get("height_b_mm", params.get("height_b", 0.0)))
                gap = float(params.get("gap_mm", params.get("gap", 0.0)))
                include_a = bool(params.get("include_bar_a", True)) and height_a > 0.0
                include_b = bool(params.get("include_bar_b", True)) and height_b > 0.0
                total_height = 0.0
                if include_a:
                    total_height += max(0.0, height_a)
                if include_b:
                    total_height += max(0.0, height_b)
                if include_a and include_b:
                    total_height += max(0.0, gap)
                return max(0.0, length), max(0.0, total_height)
            if template_type == "circlemount":
                disk = params.get("disk") or {}
                if "diameter_mm" in disk:
                    diameter = float(disk.get("diameter_mm", 0.0))
                    return diameter, diameter
                port = params.get("port") or {}
                diameter = float(port.get("diameter_mm", port.get("diameter", 0.0)))
                return diameter, diameter
        return 0.0, 0.0

    if fit == "tight":
        max_w = max((_size_of_item(it)[0] for it in items), default=0.0)
        max_h = max((_size_of_item(it)[1] for it in items), default=0.0)
        cell_w, cell_h = max_w, max_h
        block_w = cols * cell_w + (cols - 1) * gap_x
        block_h = rows * cell_h + (rows - 1) * gap_y
        if block_w > inner_w + 1e-6 or block_h > inner_h + 1e-6:
            raise ValueError("Tight pack does not fit grid interior")
    else:
        cell_w = (inner_w - (cols - 1) * gap_x) / cols
        cell_h = (inner_h - (rows - 1) * gap_y) / rows
        if cell_w <= 0.0 or cell_h <= 0.0:
            raise ValueError("Grid + borders/gaps leave no interior area")
        block_w = cols * cell_w + (cols - 1) * gap_x
        block_h = rows * cell_h + (rows - 1) * gap_y

    def _origin_offset(origin_name: str) -> Tuple[float, float]:
        name = origin_name.replace("-", "_").strip()
        horiz, vert = "center", "center"
        if name in {"center", "middle", ""}:
            pass
        else:
            parts = name.split("_")
            for part in parts:
                part = part.strip()
                if part in {"left", "right", "center", "middle"}:
                    horiz = "left" if part == "left" else "right" if part == "right" else "center"
                if part in {"bottom", "lower", "top", "upper", "center", "middle"}:
                    if part in {"bottom", "lower"}:
                        vert = "bottom"
                    elif part in {"top", "upper"}:
                        vert = "top"
                    elif part in {"center", "middle"}:
                        vert = "center"

        inner_w_span = inner_w
        inner_h_span = inner_h
        if horiz == "left":
            offset_x = border
        elif horiz == "right":
            offset_x = panel_w - border - block_w
        else:  # center
            offset_x = border + 0.5 * (inner_w_span - block_w)

        if vert == "bottom":
            offset_y = border
        elif vert == "top":
            offset_y = panel_h - border - block_h
        else:
            offset_y = border + 0.5 * (inner_h_span - block_h)

        return float(offset_x), float(offset_y)

    base_x, base_y = _origin_offset(origin)

    def _anchor_components(anchor_name: str) -> Tuple[str, str]:
        name = anchor_name.replace("-", "_").strip()
        horiz = "center"
        vert = "center"
        if name not in {"", "center", "middle"}:
            parts = name.split("_")
            for part in parts:
                part = part.strip()
                if part in {"left", "right", "center", "middle"}:
                    if part == "left":
                        horiz = "left"
                    elif part == "right":
                        horiz = "right"
                    else:
                        horiz = "center"
                if part in {"bottom", "lower", "top", "upper", "center", "middle"}:
                    if part in {"bottom", "lower"}:
                        vert = "bottom"
                    elif part in {"top", "upper"}:
                        vert = "top"
                    else:
                        vert = "center"
        return horiz, vert

    anchor_h, anchor_v = _anchor_components(anchor)

    total_cells = cols * rows
    if repeat_pattern:
        base_pattern = [copy.deepcopy(it) for it in items]
        if base_pattern:
            repeated: List[Dict[str, Any]] = []
            while len(repeated) < total_cells:
                for base in base_pattern:
                    clone = copy.deepcopy(base)
                    orig_id = clone.get("id")
                    if orig_id:
                        clone["id"] = f"{str(orig_id)}_{len(repeated) + 1}"
                    repeated.append(clone)
                    if len(repeated) >= total_cells:
                        break
            items[:] = repeated
    idx = 0
    for r in range(rows):
        for c in range(cols):
            if idx >= len(items):
                return
            cell_left = base_x + c * (cell_w + gap_x)
            cell_bottom = base_y + r * (cell_h + gap_y)
            cell_right = cell_left + cell_w
            cell_top = cell_bottom + cell_h

            item_w, item_h = _size_of_item(items[idx])
            item_w = float(item_w) if item_w > 0.0 else 0.0
            item_h = float(item_h) if item_h > 0.0 else 0.0

            if anchor_h == "left" and item_w > 0.0 and item_w <= cell_w:
                cx = cell_left + 0.5 * item_w
            elif anchor_h == "right" and item_w > 0.0 and item_w <= cell_w:
                cx = cell_right - 0.5 * item_w
            else:
                cx = cell_left + 0.5 * cell_w

            if anchor_v == "bottom" and item_h > 0.0 and item_h <= cell_h:
                cy = cell_bottom + 0.5 * item_h
            elif anchor_v == "top" and item_h > 0.0 and item_h <= cell_h:
                cy = cell_top - 0.5 * item_h
            else:
                cy = cell_bottom + 0.5 * cell_h

            placement = items[idx].setdefault("placement", {})
            placement["center_xy_mm"] = (cx, cy)
            idx += 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
# Ensure deterministic behaviour when randomised libraries are present.
os.environ.setdefault("PYTHONHASHSEED", "0")
random.seed(0)
try:  # numpy is optional in this environment
    import numpy as np

    np.random.seed(0)
except Exception:  # pragma: no cover - optional dependency
    pass
