# path: cliff_ai/skills/cabinet_door_cam/write_run_artifacts.py
# desc: Create output folder, write G-code files, merged config JSON, and a human summary.
# api: write_run_artifacts(cfg: MergedConfig, geo: Geometry, jobs: dict[str, JobPlan], fingerprint: dict) -> dict[str, str]
# tags: io, artifacts, hashing, summary

from __future__ import annotations
from typing import Dict, Any
from pathlib import Path
from dataclasses import asdict, is_dataclass
import json
from skills.cabinet_door_cam.types import MergedConfig, Geometry, JobPlan
from skills.cabinet_door_cam.util import stable_hash, dump_canonical
from skills.cabinet_door_cam.post_grbl_gcode import post_grbl_gcode

def _dataclass_to_dict(o: Any) -> Any:
    if is_dataclass(o):
        return asdict(o)
    if isinstance(o, dict):
        return {k: _dataclass_to_dict(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_dataclass_to_dict(v) for v in o]
    return o

def _compute_hash_blob(cfg: MergedConfig, geo: Geometry, fp: dict) -> dict:
    # Keep the blob minimal but deterministic.
    return {
        "version": 1,
        "grbl_header": cfg.grbl_header,
        "machine": _dataclass_to_dict(cfg.machine),
        "material": _dataclass_to_dict(cfg.material),
        "style": _dataclass_to_dict(cfg.style),
        "tools": _dataclass_to_dict(cfg.tools),
        "order": _dataclass_to_dict(cfg.order),
        "geometry": _dataclass_to_dict(geo),
        "fingerprint_extra": fp,  # caller may add app-version or build-info
    }

def _output_root(cfg: MergedConfig) -> Path:
    return Path(cfg.output_root)

def _make_out_dir(cfg: MergedConfig, geo: Geometry, blob: dict) -> Path:
    style = cfg.style.style_id
    ver = cfg.style.version
    w = int(round(cfg.order.width_mm))
    h = int(round(cfg.order.height_mm))
    t = int(round(cfg.order.thickness_mm))
    hsh = stable_hash(blob)
    base = _output_root(cfg) / f"{style}.v{ver}" / f"W{w}_H{h}_T{t}" / f"hash_{hsh}"
    base.mkdir(parents=True, exist_ok=True)
    return base

def _write_text(p: Path, text: str) -> None:
    p.write_text(text, encoding="utf-8")

def _write_json(p: Path, obj: dict) -> None:
    # Canonical/minified to stabilize diffs
    p.write_text(dump_canonical(obj), encoding="utf-8")

def _summarize(cfg: MergedConfig, geo: Geometry, out_dir: Path, written: Dict[str, str]) -> str:
    o = cfg.order
    s = cfg.style
    lines = [
        "CAM SUMMARY",
        "-----------",
        f"style: {s.style_id}.v{s.version}",
        f"size: {o.width_mm} x {o.height_mm} x {o.thickness_mm} mm",
        f"panel depth: {geo.panel_depth_mm} mm",
        f"hinges: {'yes' if o.hinge_bores else 'no'} (side: {o.hinge_side}, offsets: {o.hinge_offsets_mm})",
        f"anchors: {'yes' if o.anchors_enabled else 'no'} (face: {o.anchors_face}, mode: {o.anchors_mode})",
        f"safe_z: {o.safe_z_override_mm or cfg.machine.safe_z_mm} mm",
        "",
        "Artifacts:",
    ]
    for k, v in sorted(written.items()):
        lines.append(f"- {k}: {v}")
    return "\n".join(lines) + "\n"

def write_run_artifacts(
    cfg: MergedConfig,
    geo: Geometry,
    jobs: Dict[str, JobPlan],
    fingerprint: Dict[str, Any] | None = None,
) -> Dict[str, str]:
    """Write gcode + json into a deterministic folder. Return map of artifact names to paths (str)."""
    blob = _compute_hash_blob(cfg, geo, fingerprint or {"app": "cabinet_door_cam", "v": 1})
    out_dir = _make_out_dir(cfg, geo, blob)

    # Write merged.json (inputs portion of blob)
    merged_obj = {
        "machine": _dataclass_to_dict(cfg.machine),
        "material": _dataclass_to_dict(cfg.material),
        "style": _dataclass_to_dict(cfg.style),
        "tools": _dataclass_to_dict(cfg.tools),
        "order": _dataclass_to_dict(cfg.order),
        "grbl_header": cfg.grbl_header,
    }
    _write_json(out_dir / "merged.json", merged_obj)

    # Emit gcode files
    written: Dict[str, str] = {}
    for name, job in jobs.items():
        # Skip empty jobs
        if not job.moves:
            continue
        gcode = post_grbl_gcode(cfg, job)
        fname = f"{name}.gcode"
        _write_text(out_dir / fname, gcode)
        written[name] = str((out_dir / fname).resolve())

    # Summary
    summary = _summarize(cfg, geo, out_dir, written)
    _write_text(out_dir / "summary.txt", summary)
    written["merged_json"] = str((out_dir / "merged.json").resolve())
    written["summary_txt"] = str((out_dir / "summary.txt").resolve())
    written["out_dir"] = str(out_dir.resolve())
    return written
