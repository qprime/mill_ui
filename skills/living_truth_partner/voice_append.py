# name: voice_append.py
# path: skills/living_truth_partner/voice_append.py
# role: Capture or ingest audio and append Whisper transcript to history
# deps: dataclasses, pathlib, typing, tempfile, shutil, subprocess, datetime, httpx, json
# inputs: ProjectStore, Config, audio options
# outputs: VoiceAppend.Result

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

from skills.living_truth_partner.config import Config
from skills.living_truth_partner.project_store import ProjectStore

__all__ = ["VoiceAppend"]


def _now() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


class VoiceAppend:
    @dataclass(frozen=True)
    class Result:
        transcript: str
        notes_path: Path
        words: list[Any]
        segments: list[Any]
        raw: dict[str, Any]

    @staticmethod
    def run(store: ProjectStore, config: Config, audio_path: Path | None, record_seconds: int | None) -> Result:
        temp_path = None
        path = audio_path
        if path is None:
            temp_path = VoiceAppend._record_audio(record_seconds or 60)
            path = temp_path
        try:
            payload = VoiceAppend._transcribe(config.whisper_url, path, config.whisper_verify)
        finally:
            if temp_path is not None and temp_path.exists():
                temp_path.unlink()
        transcript = payload.get("text", "").strip()
        if not transcript:
            raise RuntimeError("Empty transcript")
        notes_path = store.new_history_note_path()
        notes_path.write_text(transcript + "\n", encoding="utf-8")
        VoiceAppend._append_discussion(store.discussion_path, transcript)
        words = payload.get("words", [])
        segments = payload.get("segments", [])
        return VoiceAppend.Result(transcript, notes_path, words, segments, payload)

    @staticmethod
    def _record_audio(seconds: int) -> Path:
        handle = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
        handle.close()
        target = Path(handle.name)
        if shutil.which("ffmpeg"):
            cmd = ["ffmpeg", "-y", "-f", "pulse", "-i", "default", "-t", str(seconds), str(target)]
        elif shutil.which("sox"):
            cmd = ["sox", "-d", str(target), "trim", "0", str(seconds)]
        elif shutil.which("arecord"):
            cmd = ["arecord", "-d", str(seconds), "-f", "cd", str(target)]
        else:
            target.unlink(missing_ok=True)
            raise RuntimeError("No audio recorder found; provide --file")
        subprocess.run(cmd, check=True)
        return target

    @staticmethod
    def _transcribe(url: str, audio_path: Path, verify: bool | str | Path | None) -> dict[str, Any]:
        with audio_path.open("rb") as data:
            files = {"file": (audio_path.name, data, "audio/wav")}
            verify_arg = str(verify) if isinstance(verify, Path) else verify
            try:
                response = httpx.post(url, files=files, timeout=120.0, verify=verify_arg)
            except httpx.HTTPError as exc:
                raise RuntimeError(f"Whisper request failed: {exc}") from exc
        response.raise_for_status()
        try:
            return json.loads(response.text)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Invalid Whisper response: {response.text[:200]}") from exc

    @staticmethod
    def _append_discussion(path: Path, transcript: str) -> None:
        block = ["## " + _now(), "", transcript.strip(), "", ""]
        with path.open("a", encoding="utf-8") as handle:
            handle.write("\n".join(block))
