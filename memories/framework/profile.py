from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parents[2]
STATE_DIR = PROJECT_ROOT / "memories" / "cliff_state"
PROFILE_STATE_PATH = STATE_DIR / "memory_profile.json"
PROFILES_ROOT = PROJECT_ROOT / "memories" / "_profiles"
DEFAULT_PROFILE = "main"
PROFILE_ENV = "CLIFF_MEMORIES_PROFILE"
ROOT_ENV = "CLIFF_MEMORIES_ROOT"

_SEED_DIRECTORIES = ["policies", "truth"]

_cached_profile: Optional[str] = None


def _normalize(profile: Optional[str]) -> str:
    if not profile:
        return DEFAULT_PROFILE
    lowered = profile.strip().lower()
    if lowered in {"prod", "production", "primary"}:
        return DEFAULT_PROFILE
    if lowered in {"test", "testing"}:
        return "test"
    if lowered in {"dev", "development"}:
        return "dev"
    return lowered or DEFAULT_PROFILE


def _load_persisted_profile() -> Optional[str]:
    if not PROFILE_STATE_PATH.exists():
        return None
    try:
        data = json.loads(PROFILE_STATE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    raw = data.get("active_profile")
    return _normalize(raw)


def _write_profile(profile: str) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"active_profile": profile}
    PROFILE_STATE_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _seed_profile(root: Path) -> None:
    baseline = PROJECT_ROOT / "memories"
    for rel in _SEED_DIRECTORIES:
        src = baseline / rel
        if not src.exists():
            continue
        dst = root / rel
        for path in src.rglob("*"):
            rel_path = path.relative_to(src)
            target = dst / rel_path
            if path.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                if not target.exists():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(path, target)


def clear_cache() -> None:
    global _cached_profile
    _cached_profile = None


def active_profile() -> str:
    global _cached_profile
    if _cached_profile:
        return _cached_profile
    env_profile = os.getenv(PROFILE_ENV)
    if env_profile:
        _cached_profile = _normalize(env_profile)
        return _cached_profile
    persisted = _load_persisted_profile()
    _cached_profile = persisted or DEFAULT_PROFILE
    return _cached_profile


def _profile_root(profile: str) -> Path:
    normalized = _normalize(profile)
    if normalized == DEFAULT_PROFILE:
        return PROJECT_ROOT / "memories"
    PROFILES_ROOT.mkdir(parents=True, exist_ok=True)
    return PROFILES_ROOT / normalized


def active_memories_root() -> Path:
    override = os.getenv(ROOT_ENV)
    if override:
        root_path = Path(override).expanduser()
        root_path.mkdir(parents=True, exist_ok=True)
        return root_path
    return _profile_root(active_profile())


def set_active_profile(profile: str, *, persist: bool = True, seed: bool = True) -> Path:
    normalized = _normalize(profile)
    root = _profile_root(normalized)
    root.mkdir(parents=True, exist_ok=True)
    if normalized != DEFAULT_PROFILE and seed:
        _seed_profile(root)
    if persist:
        _write_profile(normalized)
    os.environ[PROFILE_ENV] = normalized
    clear_cache()
    return root


def profile_status() -> dict[str, object]:
    root = active_memories_root()
    return {
        "profile": active_profile(),
        "root": str(root),
        "persisted": PROFILE_STATE_PATH.exists(),
    }


def is_test_profile() -> bool:
    current = active_profile()
    return current not in {DEFAULT_PROFILE, "prod", "production"}


def set_root_override(path: Path) -> Path:
    absolute = path.expanduser()
    os.environ[ROOT_ENV] = str(absolute)
    clear_cache()
    absolute.mkdir(parents=True, exist_ok=True)
    return absolute


def clear_root_override() -> None:
    if ROOT_ENV in os.environ:
        del os.environ[ROOT_ENV]
    clear_cache()
