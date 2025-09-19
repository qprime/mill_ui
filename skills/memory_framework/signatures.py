from __future__ import annotations

import hmac
import os
from hashlib import sha256
from typing import Any, Dict

from .utils import canonical_dumps

__all__ = ["ACTOR_SIGNING_SECRET", "sign_payload", "verify_signature"]

ACTOR_SIGNING_SECRET = os.getenv("ACTOR_SIGNING_SECRET", "test-secret").encode("utf-8")


def sign_payload(payload: Dict[str, Any]) -> str:
    message = canonical_dumps(payload).encode("utf-8")
    return hmac.new(ACTOR_SIGNING_SECRET, message, sha256).hexdigest()


def verify_signature(payload: Dict[str, Any], signature: str) -> bool:
    expected = sign_payload(payload)
    return hmac.compare_digest(expected, signature)

