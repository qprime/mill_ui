# path: skills/cam_engine/cli.py
# desc: Plan CAM, write G-code, and export STL meshes
# api: run_cli

from __future__ import annotations

import argparse
import json
import traceback
from pathlib import Path
from typing import Any, Dict, List

from skills.cam_engine.config import load_config
from skills.cam_engine.planner import plan
from skills.cam_engine.gcode_writer import write_gcode
from skills.cam_engine.serialize import to_json
from skills.cam_engine.depth_pass import apply_depth_passes
from skills.cam_engine.stl_export import export_stl

__all__ = ["run_cli", "main"]


def _ensure_dirs(base: Path) -> Dict[str, Path]:
    d = {
        "project": base,
        "input": base / "input",
        "config": base / "config",
        "output": base / "CAM_output",
        "reports": base / "CAM_output" / "reports",
    }
    for v in d.values():
        v.mkdir(parents=True, exist_ok=True)
    return d


def _quantize_moves_z(moves: List[Dict[str, Any]], dz_mm: float) -> List[Dict[str, Any]]:
    if dz_mm <= 0:
        return moves
    out: List[Dict[str, Any]] = []
    inv = 1.0 / float(dz_mm)
    for m in moves:
        if "z" in m:
            mm = dict(m)
            mm["z"] = round(float(mm["z"]) * inv) / inv
            out.append(mm)
        else:
            out.append(m)
    return out


def _emit_passes(plan_result: Dict[str, Any], cfg: Dict[str, Any], dirs: Dict[str, Path]) -> None:
    passes = plan_result.get("passes", [])
    for p in passes:
        pass_cfg = next((pp for pp in cfg["passes"] if pp.get("name") == p.get("name")), {})
        stepdown = float(pass_cfg.get("stepdown_mm", 0.0)) if isinstance(pass_cfg, dict) else 0.0
        tool = p.get("tool", {}) or {}
        dia_mm = float(tool.get("diameter_mm", 0.0))

        if stepdown > 0.0:
            moves = apply_depth_passes(
                p["moves"],
                cfg["stock"]["top_z_mm"],
                cfg["stock"]["safe_z_mm"],
                stepdown,
            )
        else:
            moves = p["moves"]

        dz = 0.005 if dia_mm and dia_mm <= 1.0 else 0.01
        moves = _quantize_moves_z(moves, dz_mm=dz)

        out_path = dirs["output"] / f"{p['name']}.{cfg['output']['extension']}"
        write_gcode(out_path, moves, cfg["machine"], cfg["stock"], pass_cfg=pass_cfg)


def run_cli() -> None:
    parser = argparse.ArgumentParser(description="CAM v4 planner/emit")
    parser.add_argument(
        "--project",
        required=True,
        help="Path to a project folder (contains config + input image/heightmap)",
    )
    args = parser.parse_args()
    project_dir = Path(args.project).resolve()
    dirs = _ensure_dirs(project_dir)

    try:
        cfg = load_config(project_dir)

        cfg.setdefault("output", {})
        cfg["output"].setdefault("extension", "nc")
        cfg.setdefault("stock", {})
        cfg["stock"].setdefault("top_z_mm", float(cfg.get("origin_z_mm", 0.0)))
        cfg["stock"].setdefault("safe_z_mm", float(cfg.get("safe_z_mm", 5.0)))

        plan_result = plan(cfg)

        _emit_passes(plan_result, cfg, dirs)

        mesh_info = export_stl(plan_result, cfg, dirs["output"])

        plan_json_path = dirs["reports"] / "plan.json"
        with plan_json_path.open("w", encoding="utf-8") as f:
            json.dump(to_json(plan_result), f, indent=2)

        print(json.dumps({
            "ok": True,
            "project": str(project_dir),
            "output_dir": str(dirs["output"]),
            "plan_report": str(plan_json_path),
            "stl": mesh_info,
        }))

    except Exception as e:
        err_path = dirs["reports"] / "error.log"
        with err_path.open("w", encoding="utf-8") as f:
            f.write(f"{type(e).__name__}: {e}\n")
            f.write(traceback.format_exc())

        print(json.dumps({
            "ok": False,
            "error": str(e),
            "error_log": str(err_path),
        }))


def main() -> None:
    run_cli()


if __name__ == "__main__":
    main()
