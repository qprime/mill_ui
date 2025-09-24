# name: config.py
# path: skills/living_truth_partner/config.py
# role: Load configuration for Living Truth Partner skill
# deps: os, pathlib, dataclasses, continuum.system_config
# inputs: environment variables, system config
# outputs: Config dataclass

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from continuum.system_config import load as load_system_config

__all__ = ["Config"]

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _parse_verify(raw: str | bool | Path | None) -> bool | str | Path | None:
    if raw in (None, ""):
        return None
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, Path):
        return raw
    lowered = str(raw).strip().lower()
    if lowered in {"false", "0", "no"}:
        return False
    if lowered in {"true", "1", "yes"}:
        return True
    candidate = Path(str(raw)).expanduser()
    if not candidate.is_absolute():
        candidate = (PROJECT_ROOT / candidate).resolve()
    return candidate


@dataclass(frozen=True)
class Config:
    root: Path
    docs: Path
    artifacts: Path
    templates: Path
    whisper_url: str
    whisper_verify: bool | str | Path | None
    prose_model: str
    code_model: str

    @staticmethod
    def load() -> Config:
        root = Path(os.getenv("LTP_ROOT", "skills/living_truth_partner/living_docs")).resolve()
        docs = root / "docs"
        artifacts = root / "artifacts"
        templates = root / "templates"

        sys_cfg = load_system_config()
        whisper_defaults = sys_cfg.get("ltp.whisper", {}) or {}

        whisper_url = os.getenv("LTP_WHISPER_URL") or whisper_defaults.get(
            "url", "https://skylink:8001/transcribe"
        )

        verify_raw = os.getenv("LTP_WHISPER_VERIFY")
        if verify_raw is None:
            verify_raw = whisper_defaults.get("verify")
        whisper_verify = _parse_verify(verify_raw)

        prose_model = os.getenv("LTP_PROSE_MODEL", "gpt-4.1")
        code_model = os.getenv("LTP_CODE_MODEL", "gpt-4.1-codex")

        return Config(
            root,
            docs,
            artifacts,
            templates,
            whisper_url,
            whisper_verify,
            prose_model,
            code_model,
        )
