# path: skills/cam_generator/core/settings.py
# desc: Load job settings from flat job_config.yaml and passes from default_passes.yaml (strict)
# api: load_settings
# tags: cam,config,settings

from __future__ import annotations

import functools
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

import yaml


@dataclass(frozen=True)
class Settings:
    job: Dict[str, Any]
    passes: Dict[str, Dict[str, Any]]
    paths: Dict[str, Path]

    def get_pass(self, name: str) -> Dict[str, Any]:
        return self.passes[name]


def _read_yaml_map(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"missing file: {path}")
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected mapping at document root, got {type(data).__name__}")
    return data


def _validate_passes(passes: Dict[str, Any], src: Path) -> Dict[str, Dict[str, Any]]:
    if not passes:
        raise ValueError(f"{src}: no passes defined")
    out: Dict[str, Dict[str, Any]] = {}
    for k, v in passes.items():
        if not isinstance(v, dict):
            raise TypeError(f"{src}: pass '{k}' must be a mapping, got {type(v).__name__}")
        out[str(k)] = dict(v)
    return out


def _merge(a: Dict[str, Any], b: Mapping[str, Any]) -> Dict[str, Any]:
    out = dict(a)
    for k, v in b.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


@functools.lru_cache(maxsize=8)
def load_settings(job_root: str | Path, overrides: Optional[Mapping[str, Any]] = None) -> Settings:
    root = Path(job_root)
    cfg_dir = root / "config"
    defaults_path = cfg_dir / "default_passes.yaml"
    job_path = cfg_dir / "job_config.yaml"

    passes_doc = _read_yaml_map(defaults_path)            # entire file = passes map
    job_doc = _read_yaml_map(job_path)                    # entire file = job map

    job = dict(job_doc)
    if overrides:
        job = _merge(job, dict(overrides))

    passes = _validate_passes(passes_doc, defaults_path)

    paths = {
        "job_root": root,
        "config_dir": cfg_dir,
        "defaults_path": defaults_path,
        "job_path": job_path,
        "input_image": root / "input" / "image.png",
        "output_dir": root / "cam_output",
    }
    return Settings(job=job, passes=passes, paths=paths)
