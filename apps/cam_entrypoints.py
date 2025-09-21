"""Thin app entrypoints for CAM operations.

The functions defined here intentionally mirror the existing API in
``skills.mill_ui`` so that ``run.py`` (and other automation) can import and
invoke them without being aware of the native backend.
"""
from __future__ import annotations

from pathlib import Path


def generate_gcode_from_step(step_path: str | Path, *_, **__) -> str:  # pragma: no cover - thin placeholder
    raise NotImplementedError(
        "generate_gcode_from_step is not wired yet – integrate the new native STEP pipeline before invoking."
    )


def list_step_features(step_path: str | Path) -> dict:  # pragma: no cover - thin placeholder
    raise NotImplementedError(
        "list_step_features is a placeholder pending STEP feature detection in the native core."
    )
