# path: cam_generator/cli.py
# desc: Command-line interface for planning and writing CAM outputs (with error logging)
# api: run_cli
# tags: cli,io,errors

from __future__ import annotations

import argparse
import json
import traceback
from pathlib import Path
from typing import Any, Dict, List

from skills.cam_generator_v4.config import load_config
from skills.cam_generator_v4.planner import plan
from skills.cam_generator_v4.gcode_writer import write_gcode
from skills.cam_generator_v4.serialize import to_json
from skills.cam_generator_v4.depth_pass import apply_depth_passes

__all__ = ["run_cli"]

def emit_passes(plan_result: dict, cfg: dict, dirs: dict) -> None:
    """
    Writes one G-code file per planned pass.
    Applies (1) step-down layering, then (2) tiny, tool-aware Z-quantize before writing.
    """
    def quantize_moves_z(moves: list[dict], dz_mm: float) -> list[dict]:
        if dz_mm <= 0:
            return moves
        out: list[dict] = []
        inv = 1.0 / float(dz_mm)
        for m in moves:
            if "z" in m:
                mm = dict(m)
                mm["z"] = round(float(mm["z"]) * inv) / inv
                out.append(mm)
            else:
                out.append(m)
        return out

    passes = plan_result.get("passes", [])
    for p in passes:
        # 1) pass config and tool data
        pass_cfg = next((pp for pp in cfg["passes"] if pp.get("name") == p.get("name")), {})
        stepdown = float(pass_cfg.get("stepdown_mm", 0.0)) if isinstance(pass_cfg, dict) else 0.0
        tool = p.get("tool", {}) or {}
        dia_mm = float(tool.get("diameter_mm", 0.0))

        # 2) depth-pass expansion (if requested)
        if stepdown > 0.0:
            moves = apply_depth_passes(
                p["moves"],
                cfg["stock"]["top_z_mm"],
                cfg["stock"]["safe_z_mm"],
                stepdown,
            )
        else:
            moves = p["moves"]

        # 3) tool-aware Z-quantize: finer for micro-tools
        dz = 0.005 if dia_mm and dia_mm <= 1.0 else 0.01
        moves = quantize_moves_z(moves, dz_mm=dz)

        # 4) write
        out_path = dirs["output"] / f"{p['name']}.{cfg['output']['extension']}"
        write_gcode(
            out_path,
            moves,
            cfg["machine"],
            cfg["stock"],
            cfg["heightmap"]["pixel_pitch_mm"],
        )


def _args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate CAM toolpaths from a heightmap")
    p.add_argument("--project", required=True, help="Path to memories/CAM_projects/{project_name}")
    return p.parse_args()


def _ensure_dirs(base: Path) -> Dict[str, Path]:
    d = {
        "input": base / "input",
        "config": base / "config",
        "output": base / "CAM_output",
        "reports": base / "CAM_output" / "reports",
    }
    for v in d.values():
        v.mkdir(parents=True, exist_ok=True)
    return d

# Quantize Z to a fixed grid (e.g., 0.01 mm) to kill float chatter in output.
def quantize_moves_z(moves: list[dict], dz_mm: float = 0.01) -> list[dict]:
    if dz_mm <= 0:
        return moves
    out: list[dict] = []
    inv = 1.0 / float(dz_mm)
    for m in moves:
        if "z" in m:
            mm = dict(m)
            mm["z"] = round(float(mm["z"]) * inv) / inv
            out.append(mm)
        else:
            out.append(m)
    return out


def run_cli() -> None:
    """
    CLI entrypoint for CAM v4.

    Steps:
      1) parse --project
      2) load merged config for the project
      3) run planner to produce plan_result (passes with moves)
      4) emit per-pass G-code with:
         - optional step-down layering (apply_depth_passes)
         - tiny Z-quantize (0.01 mm)
      5) write plan.json via serialize.to_json (JSON-safe)
      6) print {"ok": true, ...} or {"ok": false, "error": "..."} to stdout
    """
    import argparse
    import json
    import traceback
    from pathlib import Path

    from skills.cam_generator_v4.config import load_config
    from skills.cam_generator_v4.planner import plan
    from skills.cam_generator_v4.serialize import to_json

    parser = argparse.ArgumentParser(description="CAM v4 planner/emit")
    parser.add_argument(
        "--project",
        required=True,
        help="Path to a project folder (contains config + input image/heightmap)",
    )
    args = parser.parse_args()

    project_dir = Path(args.project).resolve()

    output_dir = project_dir / "CAM_output"
    reports_dir = output_dir / "reports"
    output_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    try:
        # 1) Load merged config
        cfg = load_config(project_dir)

        # Ensure keys the emitter expects
        cfg.setdefault("output", {})
        cfg["output"].setdefault("extension", "nc")
        if "stock" not in cfg:
            cfg["stock"] = {}
        cfg["stock"].setdefault("top_z_mm", float(cfg.get("origin_z_mm", 0.0)))
        cfg["stock"].setdefault("safe_z_mm", float(cfg.get("safe_z_mm", 5.0)))

        # 2) Plan toolpaths
        plan_result = plan(cfg)

        # 3) Emit G-code (layering + quantize handled inside emit_passes)
        dirs = {"project": project_dir, "output": output_dir, "reports": reports_dir}
        emit_passes(plan_result, cfg, dirs)

        # 4) Write a JSON-safe plan report using the project serializer
        plan_json_path = reports_dir / "plan.json"
        plan_json = to_json(plan_result)  # <- ensures no tuple keys / np scalars
        with plan_json_path.open("w", encoding="utf-8") as f:
            json.dump(plan_json, f, indent=2)

        # 5) Print success status for calling scripts
        print(json.dumps({
            "ok": True,
            "project": str(project_dir),
            "output_dir": str(output_dir),
            "plan_report": str(plan_json_path),
        }))
    except Exception as e:
        # Log and return a compact error for automation
        err_path = reports_dir / "error.log"
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