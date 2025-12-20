"""Shared configuration helper utilities for the CAM pipeline."""
from __future__ import annotations

from dataclasses import dataclass, fields, replace
from pathlib import Path
from typing import Any, Mapping, Sequence, Literal
import json
import math
import os


_PACKAGE_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_TOOL_DB_PATH = (_PACKAGE_ROOT / "cam" / "tools" / "tool_db.json").resolve()
_REPO_ROOT = _PACKAGE_ROOT.parent.parent
_DEFAULT_PROJECT_ROOT = (_REPO_ROOT / "memories" / "cam_projects" / "sheet_layouts").resolve()


@dataclass(frozen=True)
class Config:
    """Unified configuration for CLI, environment variables, and defaults."""

    tool_db_path: Path | None = _DEFAULT_TOOL_DB_PATH
    project_root: Path | None = _DEFAULT_PROJECT_ROOT
    material_name: str | None = "MDF"
    safe_z_mm: float = 6.0
    z_reference: Literal["top", "bottom"] = "top"
    merge_epsilon_mm: float = 0.10
    colinear_epsilon_deg: float = 1.0
    min_overlap_ratio: float = 0.55
    min_overlap_mm: float = 1.0
    cleanup_offset_mm: float = 0.25
    pocket_finish_perimeter: bool = True

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable representation of this config."""

        return {
            "tool_db_path": str(self.tool_db_path) if self.tool_db_path else None,
            "project_root": str(self.project_root) if self.project_root else None,
            "material_name": self.material_name,
            "safe_z_mm": float(self.safe_z_mm),
            "z_reference": self.z_reference,
            "merge_epsilon_mm": float(self.merge_epsilon_mm),
            "colinear_epsilon_deg": float(self.colinear_epsilon_deg),
            "min_overlap_ratio": float(self.min_overlap_ratio),
            "min_overlap_mm": float(self.min_overlap_mm),
            "cleanup_offset_mm": float(self.cleanup_offset_mm),
            "pocket_finish_perimeter": bool(self.pocket_finish_perimeter),
        }

    def with_overrides(self, overrides: Mapping[str, Any]) -> Config:
        """Return a copy with ``overrides`` applied after validation."""

        if not overrides:
            return self

        updates: dict[str, Any] = {}
        for key, raw_value in overrides.items():
            if key not in _CONFIG_FIELD_NAMES:
                continue
            if raw_value is None:
                if key in _OPTIONAL_FIELDS:
                    updates[key] = None
                continue
            if isinstance(raw_value, str) and key in _OPTIONAL_FIELDS and raw_value.strip() == "":
                updates[key] = None
                continue
            normaliser = _NORMALISERS[key]
            try:
                updates[key] = normaliser(raw_value)
            except ValueError as exc:  # pragma: no cover - defensive validation path
                raise ValueError(f"Invalid value for {key}: {raw_value!r}") from exc
        if not updates:
            return self
        return replace(self, **updates)

    @classmethod
    def from_env(
        cls,
        *,
        prefix: str = "CAM_",
        environ: Mapping[str, str] | None = None,
        base: Config | None = None,
    ) -> Config:
        """Create a config by overlaying recognised environment variables."""

        env = environ or os.environ
        overrides = {
            field: env.get(f"{prefix}{suffix}")
            for field, suffix in _ENV_SUFFIXES.items()
            if f"{prefix}{suffix}" in env
        }
        return (base or cls()).with_overrides(overrides)

    @classmethod
    def from_cli(
        cls,
        args: Mapping[str, Any] | object,
        *,
        base: Config | None = None,
    ) -> Config:
        """Create a config by overlaying parsed CLI arguments."""

        data = _namespace_to_mapping(args)
        overrides = {key: data[key] for key in _CONFIG_FIELD_NAMES if key in data and data[key] is not None}
        return (base or cls()).with_overrides(overrides)


_CONFIG_FIELD_NAMES = tuple(field.name for field in fields(Config))
_OPTIONAL_FIELDS = {"tool_db_path", "project_root", "material_name"}
_TOLERANCE_FIELDS = {
    "merge_epsilon_mm",
    "colinear_epsilon_deg",
    "min_overlap_ratio",
    "min_overlap_mm",
    "cleanup_offset_mm",
}
_ENV_SUFFIXES = {
    "tool_db_path": "TOOL_DB",
    "project_root": "PROJECT_ROOT",
    "material_name": "MATERIAL",
    "safe_z_mm": "SAFE_Z",
    "z_reference": "Z_REF",
    "merge_epsilon_mm": "MERGE_EPS",
    "colinear_epsilon_deg": "COLINEAR_EPS",
    "min_overlap_ratio": "MIN_OVERLAP_RATIO",
    "min_overlap_mm": "MIN_OVERLAP_MM",
    "cleanup_offset_mm": "CLEANUP_OFFSET_MM",
    "pocket_finish_perimeter": "POCKET_FINISH_PERIMETER",
}


def _namespace_to_mapping(args: Mapping[str, Any] | object | None) -> Mapping[str, Any]:
    if args is None:
        return {}
    if isinstance(args, Mapping):
        return args
    try:
        return dict(vars(args))
    except TypeError:  # pragma: no cover - not expected, defensive fallback
        return {}


def _normalise_path(value: Any) -> Path:
    if isinstance(value, Path):
        return value.expanduser()
    text = str(value).strip()
    if not text:
        raise ValueError("Path value cannot be empty")
    return Path(text).expanduser()


def _normalise_material(value: Any) -> str | None:
    text = str(value).strip()
    if not text:
        return None
    return text


def _finite_float(value: Any) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("Value must be a finite float")
    return number


def _non_negative_float(value: Any) -> float:
    number = _finite_float(value)
    if number < 0.0:
        raise ValueError("Value must be non-negative")
    return number


def _ratio_float(value: Any) -> float:
    number = _finite_float(value)
    if number < 0.0:
        raise ValueError("Ratio must be non-negative")
    return number


def _z_reference(value: Any) -> Literal["top", "bottom"]:
    text = str(value).strip().lower()
    if text not in {"top", "bottom"}:
        raise ValueError("z_reference must be 'top' or 'bottom'")
    return "top" if text == "top" else "bottom"


def _normalise_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"true", "1", "yes", "on"}:
        return True
    if text in {"false", "0", "no", "off"}:
        return False
    raise ValueError(f"Cannot convert {value!r} to boolean")


_NORMALISERS = {
    "tool_db_path": _normalise_path,
    "project_root": _normalise_path,
    "material_name": _normalise_material,
    "safe_z_mm": _non_negative_float,
    "z_reference": _z_reference,
    "merge_epsilon_mm": _non_negative_float,
    "colinear_epsilon_deg": _non_negative_float,
    "min_overlap_ratio": _ratio_float,
    "min_overlap_mm": _non_negative_float,
    "cleanup_offset_mm": _non_negative_float,
    "pocket_finish_perimeter": _normalise_bool,
}


def _extract_overrides(data: Mapping[str, Any]) -> dict[str, Any]:
    overrides: dict[str, Any] = {}
    for key in _CONFIG_FIELD_NAMES:
        if key in data:
            overrides[key] = data[key]
    tolerances = data.get("tolerances")
    if isinstance(tolerances, Mapping):
        for key in _TOLERANCE_FIELDS:
            if key in tolerances:
                overrides[key] = tolerances[key]
    return overrides


def find_config_file(search_paths: Sequence[Path | str] | None = None) -> Path | None:
    """Return the first existing config.json in ``search_paths`` if present."""

    roots: list[Path] = []
    if search_paths:
        for item in search_paths:
            roots.append(Path(item).expanduser())
    else:
        roots.extend([Path.cwd(), _REPO_ROOT, _PACKAGE_ROOT])

    seen: set[Path] = set()
    for root in roots:
        candidate = (root / "config.json").resolve()
        if candidate in seen:
            continue
        seen.add(candidate)
        if candidate.exists():
            return candidate
    return None


def _load_config_file(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, Mapping):
        raise ValueError("Config file must contain an object at the top level")
    return _extract_overrides(data)


def load_config(
    *,
    cli_args: Mapping[str, Any] | object | None = None,
    env: Mapping[str, str] | None = None,
    config_path: Path | str | None = None,
    search_paths: Sequence[Path | str] | None = None,
    prefix: str = "CAM_",
) -> Config:
    """Load the ``Config`` using precedence: CLI > env > file > defaults."""

    base = Config()

    config_file: Path | None
    if config_path is not None:
        config_file = Path(config_path).expanduser().resolve()
        if not config_file.exists():
            raise FileNotFoundError(f"Config file not found: {config_file}")
    else:
        config_file = find_config_file(search_paths)

    if config_file is not None:
        file_overrides = _load_config_file(config_file)
        base = base.with_overrides(file_overrides)

    base = Config.from_env(prefix=prefix, environ=env, base=base)

    if cli_args is not None:
        base = Config.from_cli(cli_args, base=base)

    return base


__all__ = ["Config", "find_config_file", "load_config"]
