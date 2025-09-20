from __future__ import annotations

import contextlib
import hashlib
import json
import os
import random
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

__all__ = [
    "OFFLINE",
    "ENABLE_FFMPEG",
    "ENABLE_PANDOC",
    "MAX_DIFF_SLOC",
    "WORKTREE_ROOT",
    "acquire_lock",
    "canonical_dumps",
    "ensure_dir",
    "env_flag",
    "read_json",
    "read_text",
    "sha256_bytes",
    "sha256_file",
    "sha256_text",
    "strip_comments",
    "trim_chars",
    "utc_now",
    "write_json",
    "write_text",
]

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MEMORIES_ROOT = PROJECT_ROOT / "memories"

OFFLINE = os.getenv("OFFLINE", "0") == "1"
ENABLE_PANDOC = os.getenv("ENABLE_PANDOC", "0") == "1"
ENABLE_FFMPEG = os.getenv("ENABLE_FFMPEG", "0") == "1"
WORKTREE_ROOT = Path(os.getenv("WORKTREE_ROOT", PROJECT_ROOT))
MAX_DIFF_SLOC = int(os.getenv("MAX_DIFF_SLOC", "500"))


def utc_now() -> str:
    now = datetime.now(timezone.utc)
    return now.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def canonical_dumps(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    ensure_dir(path.parent)
    path.write_text(canonical_dumps(data), encoding="utf-8")


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    ensure_dir(path.parent)
    path.write_text(text, encoding="utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    lowered = raw.lower().strip()
    if lowered in {"1", "true", "yes", "on"}:
        return True
    if lowered in {"0", "false", "no", "off"}:
        return False
    return default


@contextlib.contextmanager
def acquire_lock(lock_path: Path) -> Iterator[None]:
    ensure_dir(lock_path.parent)
    while True:
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
            break
        except FileExistsError:
            from time import sleep

            sleep(0.005 + random.random() * 0.002)
    try:
        yield
    finally:
        try:
            os.unlink(lock_path)
        except FileNotFoundError:
            pass


_COMMENT_MD = re.compile(r"<!--.*?-->", re.DOTALL)


def _strip_py(text: str) -> str:
    import io
    import tokenize

    out: list[str] = []
    reader = io.StringIO(text).readline
    for token in tokenize.generate_tokens(reader):
        if token.type == tokenize.COMMENT:
            continue
        if token.type == tokenize.NL and token.line.strip().startswith("#"):
            continue
        out.append(token.string)
    return "".join(out)


def strip_comments(path: Path, text: str) -> str:
    suffix = path.suffix.lower()
    if suffix == ".py":
        try:
            return _strip_py(text)
        except Exception:
            return text
    if suffix == ".md":
        return _COMMENT_MD.sub("", text)
    return text


def trim_chars(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)] + "..."


def copy_file(src: Path, dst: Path) -> None:
    ensure_dir(dst.parent)
    shutil.copy2(src, dst)
