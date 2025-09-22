from __future__ import annotations

import os
from pathlib import Path
from time import time

from flask import Blueprint, jsonify

system_api_bp = Blueprint("system_api_bp", __name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
LEDGER_PATH = PROJECT_ROOT / "memories" / "index.jsonl"
DEFAULT_THRESHOLD_MB = float(os.getenv("LEDGER_WARNING_THRESHOLD_MB", "50"))


@system_api_bp.get("/ledger/status")
def ledger_status():
    threshold = DEFAULT_THRESHOLD_MB
    size_bytes = LEDGER_PATH.stat().st_size if LEDGER_PATH.exists() else 0
    size_mb = round(size_bytes / (1024 * 1024), 2) if size_bytes else 0.0
    needs_compaction = threshold > 0 and size_mb >= threshold
    return jsonify(
        {
            "needs_compaction": needs_compaction,
            "size_mb": size_mb,
            "size_bytes": size_bytes,
            "threshold_mb": threshold,
            "checked_at": time(),
        }
    )
