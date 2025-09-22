from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from time import time

PROJECT_ROOT = Path(__file__).resolve().parents[2]
LEDGER_PATH = PROJECT_ROOT / "memories" / "index.jsonl"

DEFAULT_THRESHOLD_MB = float(os.getenv("LEDGER_WARNING_THRESHOLD_MB", "50"))
_CACHE_TTL_SECONDS = 30


@dataclass(frozen=True)
class LedgerStatus:
    needs_compaction: bool
    size_mb: float
    size_bytes: int
    threshold_mb: float
    last_checked: float


_cache_status: LedgerStatus | None = None
_cache_expiry: float = 0.0


def _compute_status(threshold_mb: float) -> LedgerStatus:
    size_bytes = 0
    if LEDGER_PATH.exists():
        size_bytes = LEDGER_PATH.stat().st_size
    size_mb = size_bytes / (1024 * 1024) if size_bytes else 0.0
    needs = size_mb >= threshold_mb if threshold_mb > 0 else False
    now = time()
    return LedgerStatus(
        needs_compaction=needs,
        size_mb=round(size_mb, 2),
        size_bytes=size_bytes,
        threshold_mb=threshold_mb,
        last_checked=now,
    )


def get_ledger_status(refresh: bool = False, *, threshold_mb: float | None = None) -> LedgerStatus:
    global _cache_status, _cache_expiry
    threshold = float(threshold_mb) if threshold_mb is not None else DEFAULT_THRESHOLD_MB
    now = time()
    if not refresh and _cache_status and now < _cache_expiry and _cache_status.threshold_mb == threshold:
        return _cache_status

    status = _compute_status(threshold)
    _cache_status = status
    _cache_expiry = now + _CACHE_TTL_SECONDS
    return status
