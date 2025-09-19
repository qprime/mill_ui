from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from .ids import generate_ulid
from .models import Actor, Memory, MemoryContent, MemoryMetadata, Relations
from .registry import MemoryRegistry
from .utils import MEMORIES_ROOT, ensure_dir, utc_now, write_json

__all__ = [
    "PolicyEvaluation",
    "PolicyStore",
]


@dataclass
class PolicyEvaluation:
    action_id: str
    path: Path
    requires_decision: bool
    escalation_reasons: List[str]
    required_signers: List[str]
    checks: Dict[str, Any]


class PolicyStore:
    def __init__(self, root: Path | None = None):
        self.root = root or (MEMORIES_ROOT / "policies")
        ensure_dir(self.root)
        self._cache: Dict[str, Any] = {}

    def _load(self, name: str) -> Any:
        if name not in self._cache:
            path = self.root / name
            if not path.exists():
                raise FileNotFoundError(f"Missing policy file {path}")
            self._cache[name] = path.read_text(encoding="utf-8")
        raw = self._cache[name]
        if isinstance(raw, str):
            import json

            data = json.loads(raw)
            self._cache[name] = data
            return data
        return raw

    @property
    def safety(self) -> Dict[str, Any]:
        return self._load("safety.json")

    @property
    def pii(self) -> Dict[str, Any]:
        return self._load("pii.json")

    @property
    def freeze(self) -> Dict[str, Any]:
        return self._load("freeze_windows.json")

    def evaluate_action(self, registry: MemoryRegistry, action, *, context: Dict[str, Any] | None = None) -> PolicyEvaluation:
        context = context or {}
        safety = self.safety
        pii = self.pii
        freeze = self.freeze

        requires_decision = False
        escalation_reasons: List[str] = []
        required_signers: List[str] = []

        paths = set(context.get("paths", []))
        safety_hits = [
            path
            for path in paths
            if any(path.startswith(prefix.rstrip("*")) for prefix in safety.get("safety_critical_paths", []))
        ]
        safety_required_tests = safety.get("required_tests", [])

        safety_section = {
            "paths": sorted(paths),
            "hits": safety_hits,
            "required_tests": safety_required_tests,
        }
        if safety_hits:
            requires_decision = True
            escalation_reasons.append("policy_required")
            required_signers.extend(safety.get("required_signers", []))

        pii_fields = [field.lower() for field in pii.get("fields", [])]
        requirements_text = " ".join(action.requirements).lower()
        pii_detected = [field for field in pii_fields if field in requirements_text]
        if context.get("sensitivity") == "pii":
            pii_detected.append("sensitivity_flag")
        pii_section = {
            "detected": sorted(set(pii_detected)),
            "requires_executor": pii.get("requires_executor"),
        }
        if pii_detected:
            requires_decision = True
            escalation_reasons.append("policy_required")

        freeze_windows = freeze.get("windows_utc", [])
        deny_intents = set(freeze.get("deny_intents", []))
        now_utc = datetime.now(timezone.utc)
        in_freeze = False
        for window in freeze_windows:
            start = datetime.fromisoformat(window["start"].replace("Z", "+00:00"))
            end = datetime.fromisoformat(window["end"].replace("Z", "+00:00"))
            if start <= now_utc <= end:
                in_freeze = True
                break
        freeze_section = {
            "active": in_freeze,
            "deny_intents": list(deny_intents),
        }
        if in_freeze and action.intent in deny_intents:
            requires_decision = True
            escalation_reasons.append("policy_required")

        checks = {
            "safety": safety_section,
            "pii": pii_section,
            "freeze": freeze_section,
        }

        policy_dir = MEMORIES_ROOT / "decisions" / "policy_checks"
        ensure_dir(policy_dir)
        policy_path = policy_dir / f"{action.id}.policy_check.json"
        payload = {
            "action_id": action.id,
            "evaluated_at": utc_now(),
            "checks": checks,
        }
        write_json(policy_path, payload)

        stamp = utc_now()
        memory = Memory(
            id=generate_ulid(),
            type="policy",
            purpose="safety.check",
            handle=action.thread,
            title=f"Policy check for {action.title}",
            tags=[action.intent, "policy"],
            state="active",
            registry_status="staged",
            relations=Relations(thread_of=action.id),
            content=MemoryContent(path=str(policy_path.relative_to(MEMORIES_ROOT))),
            metadata=MemoryMetadata(constraints={"checks": checks}),
            actor=Actor(actor_id="cliff_ai", actor_type="ai"),
            created_at=stamp,
            updated_at=stamp,
        )
        registry.register(memory)

        return PolicyEvaluation(
            action_id=action.id,
            path=policy_path,
            requires_decision=requires_decision,
            escalation_reasons=sorted(set(escalation_reasons)),
            required_signers=sorted(set(required_signers)),
            checks=checks,
        )

