from __future__ import annotations

import os
import threading
import time
from typing import Final

__all__ = ["generate_ulid", "ulid_timestamp_ms"]

_CROCKFORD32: Final[str] = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_RANDOM_BITS: Final[int] = 80
_TIMESTAMP_BITS: Final[int] = 48
_RANDOM_MAX: Final[int] = (1 << _RANDOM_BITS) - 1

_lock = threading.Lock()
_last_timestamp_ms = 0
_last_random = 0


def _encode_base32(value: int, length: int) -> str:
    chars = ["0"] * length
    for index in range(length - 1, -1, -1):
        chars[index] = _CROCKFORD32[value & 0x1F]
        value >>= 5
    return "".join(chars)


def _random_80_bits() -> int:
    return int.from_bytes(os.urandom(10), "big")


def ulid_timestamp_ms(ulid: str) -> int:
    timestamp_part = ulid[:10]
    value = 0
    for char in timestamp_part:
        value = (value << 5) | _CROCKFORD32.index(char)
    return value


def generate_ulid(now_ms: int | None = None) -> str:
    global _last_timestamp_ms, _last_random
    if now_ms is None:
        now_ms = int(time.time_ns() // 1_000_000)
    with _lock:
        if now_ms > _last_timestamp_ms:
            _last_timestamp_ms = now_ms
            _last_random = _random_80_bits()
        else:
            _last_random = (_last_random + 1) & _RANDOM_MAX
            if _last_random == 0:
                _last_timestamp_ms = now_ms + 1
        timestamp = _encode_base32(_last_timestamp_ms, 10)
        randomness = _encode_base32(_last_random, 16)
    return timestamp + randomness

