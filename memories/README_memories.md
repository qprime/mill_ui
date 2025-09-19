# Memories Ledger

The `memories/` root records every typed Memory emitted by the framework. Key locations:

- `index.jsonl` — append-only hash-chained ledger of Memory envelopes.
- `truth/` — canonical source documents (`cliff_ai.mind.md` is the ground truth).
- `actions/` — executor manifests and environment captures per action run.
- `artifacts/` — diff patches, exports, logs, and CNC outputs grouped by purpose.
- `capsules/` — deterministic prompt capsules with captured context and prompt hash.
- `decisions/` — policy check sidecars and signed approvals.
- `notes/` — narrative and note memories.
- `policies/` — JSON guardrails loaded by the policy evaluator.

## Ledger hygiene

Use the CLI (`ltp ctx registry-validate`) or `scripts/ci_registry_integrity.py` to verify the chain. Any tampering with `index.jsonl` breaks the rolling SHA-256 chain.

## CI helpers

- `scripts/ci_registry_integrity.py` — validates the chain and ensures no staged memories remain.
- `scripts/ci_decision_coverage.py` — asserts that sensitive outputs (external exports, CNC gcode) have a matching signed decision.
- `scripts/ci_reproduce_sample.py` — replays a stored manifest in dry mode to check reproducibility.

All CI and tests run with `OFFLINE=1`.

