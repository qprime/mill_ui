from __future__ import annotations

from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from skills.memory_framework.registry import MemoryRegistry
from skills.memory_framework.signatures import verify_signature

SENSITIVE_PURPOSES = {"doc.export", "cnc.gcode"}


def _decision_payload(decision_memory) -> dict:
    data = decision_memory.metadata.constraints.get("decision", {})
    return {k: v for k, v in data.items() if k != "signature"}, data.get("signature", "")


def main() -> int:
    registry = MemoryRegistry()
    decisions = registry.query({"type": "decision"}, limit=500)
    sensitive = registry.query({"type": "artifact"}, limit=1000)

    errors = []
    for memory in sensitive:
        if memory.purpose not in SENSITIVE_PURPOSES:
            continue
        action_id = memory.relations.thread_of
        if not action_id:
            errors.append(f"artifact {memory.id} missing thread reference")
            continue
        matched = False
        for decision in decisions:
            payload, signature = _decision_payload(decision)
            if decision.handle == action_id and verify_signature(payload, signature):
                matched = True
                break
        if not matched:
            errors.append(f"artifact {memory.id} for action {action_id} lacks decision")

    if errors:
        for error in errors:
            print(error)
        return 1
    print("decision coverage ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
