# name: config.py
# path: skills/living_truth_partner/config.py
# role: Load configuration for Living Truth Partner skill
# deps: os, pathlib, dataclasses
# inputs: environment variables
# outputs: Config dataclass

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

__all__ = ["Config"]


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
        root = Path(os.getenv("LTP_ROOT", "living_docs")).resolve()
        docs = root / "docs"
        artifacts = root / "artifacts"
        templates = root / "templates"
        whisper_url = os.getenv("LTP_WHISPER_URL", "http://localhost:8001/transcribe")
        verify_raw = (os.getenv("LTP_WHISPER_VERIFY") or "").strip()
        if not verify_raw:
            whisper_verify: bool | str | Path | None = None
        else:
            lowered = verify_raw.lower()
            if lowered in {"false", "0", "no"}:
                whisper_verify = False
            elif lowered in {"true", "1", "yes"}:
                whisper_verify = True
            else:
                whisper_verify = Path(verify_raw).expanduser().resolve()
        prose_model = os.getenv("LTP_PROSE_MODEL", "gpt-4.1")
        code_model = os.getenv("LTP_CODE_MODEL", "gpt-4.1-codex")
        return Config(root, docs, artifacts, templates, whisper_url, whisper_verify, prose_model, code_model)
