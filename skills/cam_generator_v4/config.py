# path: skills/cam_generator_v4/config.py
# desc: Load job/passes and expose normalized run config including STL options
# api: load_config

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping

import yaml

__all__ = ["load_config"]


@dataclass(frozen=True)
class _Paths:
    base: Path
    input_image: Path
    passes_yaml: Path
    job_yaml: Path
    output_dir: Path
    reports_dir: Path


def _paths(base: Path) -> _Paths:
    return _Paths(
        base=base,
        input_image=base / "input" / "image.png",
        passes_yaml=base / "config" / "passes.yaml",
        job_yaml=base / "config" / "job_config.yaml",
        output_dir=base / "CAM_output",
        reports_dir=base / "CAM_output" / "reports",
    )


def _load_yaml(p: Path) -> Dict[str, Any]:
    with open(p, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"YAML root must be a mapping: {p}")
    return data


def _merge_passes(run_list: List[str], lib: Mapping[str, Any], overrides: Mapping[str, Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for name in run_list:
        base = lib.get(name)
        if not isinstance(base, Mapping):
            raise ValueError(f"Pass '{name}' not found in passes.yaml")
        merged = dict(base)
        ov = overrides.get(name, {})
        if not isinstance(ov, Mapping):
            ov = {}
        merged.update(ov)
        merged["name"] = name
        out.append(merged)
    return out


def _validate(cfg: Dict[str, Any], paths: _Paths) -> Dict[str, Any]:
    if not paths.input_image.exists():
        raise FileNotFoundError(str(paths.input_image))
    if not paths.passes_yaml.exists():
        raise FileNotFoundError(str(paths.passes_yaml))
    if not paths.job_yaml.exists():
        raise FileNotFoundError(str(paths.job_yaml))
    if "passes" not in cfg or not isinstance(cfg["passes"], dict):
        raise ValueError("passes.yaml must contain a 'passes' mapping")
    if "passes" not in cfg["job"] or not isinstance(cfg["job"]["passes"], list):
        raise ValueError("job_config.yaml must contain a 'passes' list")
    return cfg


def load_config(project_dir: Path) -> Dict[str, Any]:
    paths = _paths(project_dir)
    passes_yaml = _load_yaml(paths.passes_yaml)
    job_yaml = _load_yaml(paths.job_yaml)

    cfg = {
        "paths": {
            "base": str(paths.base),
            "image": str(paths.input_image),
            "passes_yaml": str(paths.passes_yaml),
            "job_yaml": str(paths.job_yaml),
            "output_dir": str(paths.output_dir),
            "reports_dir": str(paths.reports_dir),
        },
        "passes": passes_yaml,
        "job": job_yaml,
    }
    _ = _validate(cfg, paths)

    run_passes = _merge_passes(
        cfg["job"]["passes"],
        cfg["passes"]["passes"],
        cfg["job"].get("overrides", {}),
    )

    out_ext = cfg["job"].get("output", {}).get("extension", "nc")

    hm_job = cfg["job"]["heightmap"]
    heightmap_cfg: Dict[str, Any] = {
        "image_path": str(paths.input_image),
        "pixel_pitch_mm": float(hm_job.get("pixel_pitch_mm", 0.0) or 0.0),
        "target_size_mm": dict(hm_job.get("target_size_mm", {})),
        "max_depth_mm": float(hm_job["max_depth_mm"]),
        "carve_threshold_mm": float(hm_job.get("carve_threshold_mm", 0.0)),
        "white_is_high": bool(hm_job.get("white_is_high", True)),
        "floor_gray": float(hm_job.get("floor_gray", 0.0)),
        "gamma": float(hm_job.get("gamma", 1.0)),
    }

    stock_cfg = {
        "top_z_mm": float(cfg["job"]["stock"]["top_z_mm"]),
        "safe_z_mm": float(cfg["job"]["stock"]["safe_z_mm"]),
    }
    machine_cfg = {
        "units": cfg["job"]["machine"].get("units", "mm"),
        "gcode_dialect": cfg["job"]["machine"].get("gcode_dialect", "grbl"),
        "origin": cfg["job"]["machine"].get("origin", "lower_left"),
        "work_offset_mm": dict(cfg["job"]["machine"].get("work_offset_mm", {"x": 0.0, "y": 0.0, "z": 0.0})),
    }

    # STL options: CAM + PROOF
    stl_cfg = dict(cfg["job"].get("stl", {}))
    # CAM controls
    stl_cfg.setdefault("enable", True)
    stl_cfg.setdefault("per_band", True)            # CAM bands
    stl_cfg.setdefault("add_skirt", True)           # CAM skirts (base+walls)
    stl_cfg.setdefault("z_exaggeration", 1.0)       # CAM z-exag (usually 1.0)
    stl_cfg.setdefault("base_mm_last", 0.0)         # extra base on final CAM band
    stl_cfg.setdefault("max_triangles", 0)          # 0 = unlimited (full res)
    stl_cfg.setdefault("crop_changed", True)        # crop band meshes to changed bbox
    stl_cfg.setdefault("crop_eps_mm", 0.01)         # 'changed' threshold
    stl_cfg.setdefault("crop_margin_px", 4)         # bbox padding (pixels)

    # PROOF controls
    proof_cfg = dict(stl_cfg.get("proof", {}))
    proof_cfg.setdefault("enable", True)
    # target size can be set as {width,height} or target_width_mm/target_height_mm
    proof_cfg.setdefault("target_size_mm", {"width": 200.0})  # 200 mm wide sample by default
    proof_cfg.setdefault("add_skirt", True)
    proof_cfg.setdefault("z_exaggeration", 1.25)
    proof_cfg.setdefault("base_mm", 6.0)
    proof_cfg.setdefault("per_band", False)
    proof_cfg.setdefault("max_triangles", 2_000_000)  # cap triangles by downsampling

    stl_cfg["proof"] = proof_cfg

    return {
        "project_name": cfg["job"].get("project_name", paths.base.name),
        "paths": cfg["paths"],
        "heightmap": heightmap_cfg,
        "stock": stock_cfg,
        "machine": machine_cfg,
        "output": {"extension": out_ext},
        "passes": run_passes,
        "stl": stl_cfg,
    }
