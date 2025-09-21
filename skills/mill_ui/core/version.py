"""Repository-aware version helpers for deterministic builds."""
from __future__ import annotations

import os
import subprocess
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Optional


_REPO_ROOT = Path(__file__).resolve().parents[3]
_GIT_TIMEOUT = 0.2  # seconds


def _run_git_command(*args: str) -> Optional[str]:
    """Execute a git command relative to the repository root."""

    try:
        completed = subprocess.check_output(
            ["git", *args],
            cwd=_REPO_ROOT,
            stderr=subprocess.DEVNULL,
            timeout=_GIT_TIMEOUT,
        )
    except Exception:
        return None
    output = completed.decode("utf-8", errors="ignore").strip()
    return output or None


@lru_cache(maxsize=1)
def git_sha(*, short: bool = True) -> Optional[str]:
    """Return the current HEAD SHA (optionally shortened)."""

    args = ["rev-parse", "HEAD"]
    if short:
        args.insert(1, "--short=12")
    return _run_git_command(*args)


@lru_cache(maxsize=1)
def _compute_version() -> tuple[str, str]:
    env_val = (os.environ.get("BUILD_VERSION") or "").strip()
    if env_val:
        return env_val, "env"

    described = _run_git_command("describe", "--tags", "--dirty", "--always")
    if described:
        return described, "git"

    sha = git_sha(short=True)
    if sha:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
        return f"{sha}-{stamp}", "sha"

    return "unknown", "fallback"


def get_build_version() -> str:
    """Return the best available identifier for this build."""

    return _compute_version()[0]


def version_info() -> dict[str, str]:
    """Return a mapping describing the current build version and source."""

    version, source = _compute_version()
    return {"version": version, "source": source}


__all__ = ["get_build_version", "git_sha", "version_info"]

