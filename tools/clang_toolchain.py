#!/usr/bin/env python3
"""Shared clang binary discovery and version pinning for the native wrappers.

The formatting and static-analysis gates are pinned to one clang major
version: formatter output and check behaviour both differ across majors, so a
contributor on a different version sees failures on conforming code. Resolving
the binary here keeps run_clang_format.py and run_clang_tidy.py agreeing on
which clang they mean.

Version-suffixed binaries (clang-format-18) are preferred over the unsuffixed
name, so the gate still resolves on a machine whose default clang is newer.
"""

from __future__ import annotations

import re
import shutil
import subprocess

REQUIRED_MAJOR = 18

_VERSION_PATTERN = re.compile(r"version\s+(\d+)\.")


def _detect_major(binary: str) -> int | None:
    try:
        proc = subprocess.run([binary, "--version"], capture_output=True, text=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        return None

    match = _VERSION_PATTERN.search(proc.stdout)
    return int(match.group(1)) if match else None


def resolve(tool: str) -> tuple[str | None, str | None]:
    """Return (path, error) for a version-pinned clang tool."""
    candidates = [f"{tool}-{REQUIRED_MAJOR}", tool]

    found: list[tuple[str, int | None]] = []
    for name in candidates:
        path = shutil.which(name)
        if path is None:
            continue
        major = _detect_major(path)
        if major == REQUIRED_MAJOR:
            return path, None
        found.append((path, major))

    if not found:
        return None, (
            f"{tool} not found. This gate is pinned to clang {REQUIRED_MAJOR};"
            f" install it with:\n"
            f"    sudo apt-get install -y {tool}-{REQUIRED_MAJOR}"
        )

    path, major = found[0]
    reported = f"{major}" if major is not None else "unknown"
    return None, (
        f"{path} reports version {reported}, but this gate is pinned to clang"
        f" {REQUIRED_MAJOR}.\n"
        f"Output differs across major versions, so a mismatched binary reports"
        f" failures on conforming code.\n"
        f"Install the pinned version with:\n"
        f"    sudo apt-get install -y {tool}-{REQUIRED_MAJOR}"
    )
