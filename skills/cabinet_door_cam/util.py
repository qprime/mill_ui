# path: cliff_ai/skills/cabinet_door_cam/util.py
# desc: Small helpers for rounding, json IO, canonical hashing, and clamping.
# api: round_mm, round_feed, clamp, load_json, dump_canonical, stable_hash
# tags: utils, determinism, io

from __future__ import annotations
from typing import Any
from pathlib import Path
import json, hashlib
from skills.cabinet_door_cam.settings import GEOM_MM_PLACES, FEED_MM_MIN_PLACES, JSON_INDENT, JSON_SORT_KEYS

def round_mm(v: float) -> float:
    return round(float(v), GEOM_MM_PLACES)

def round_feed(v: float) -> float:
    return round(float(v), FEED_MM_MIN_PLACES)

def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))

def load_json(p: Path) -> dict:
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)

def dump_canonical(obj: Any) -> str:
    return json.dumps(obj, indent=JSON_INDENT, sort_keys=JSON_SORT_KEYS, separators=(",", ":"))

def stable_hash(obj: Any) -> str:
    data = dump_canonical(obj).encode("utf-8")
    return hashlib.sha256(data).hexdigest()[:16]
