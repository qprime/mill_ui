# Memories Ledger

Owner path: memories/

## 1. What this is

Memories is the canonical ledger for every action, policy, and artifact.
It stores typed memories under an append-only chain referenced by the rest of the stack.

## 2. When to use it

- Append new actions, policies, artifacts, or decisions produced by skills.
- Audit ledger integrity or decision coverage during CI.
- Query historical context for chat, CAM, or documentation workflows.

## 3. How to run

Use the provided CI helpers to validate ledger integrity before shipping.

```bash
python scripts/ci_registry_integrity.py
python scripts/ci_decision_coverage.py
python scripts/ci_reproduce_sample.py
```

## 4. Inputs & outputs (for AI & humans)

- `memories/index.jsonl` — hash-chained ledger of Memory envelopes.
- `memories/actions/` — executor manifests with captured environments.
- `memories/artifacts/` — generated assets such as G-code, patches, and exports.
- `memories/policies/` — JSON guardrails loaded by policy evaluators.
- `memories/living_truths/` — historical guidance documents kept for reference.

## 5. Public surface

- `memories.framework.registry.MemoryRegistry` — append or query typed memories with integrity checks.
- `memories.memory_manager.get_known_contexts()` — enumerate available memory domains.
- `memories.memory_manager.add_to_domain(domain, text, source)` — append narrative or note entries.
- `memories.memory_graph.scan_memory()` — build a JSON summary of memory domains.

## 6. Invariants & guardrails

- Ledger entries must be canonical JSON with stable key ordering.
- Registry status transitions follow staged → registered → referenced → archived.
- Artifact hashes recorded in manifests must match on-disk contents.
- All workflows run with `OFFLINE=1`; remote fetches are disallowed by default.

## 7. Extension points

- Create new domains by adding folders under `memories/` and documenting them here.
- Add policy schemas under `memories/policies/` and wire them into guardrails.
- Extend the registry by implementing companion models in `memories/framework/models.py`.
- Record additional CI checks under `scripts/` and reference them in this README.

## 8. AI reading order

- `memories/framework/registry.py` — Implements MemoryRegistry and chain logic.
- `memories/memory_manager.py` — Helpers for chat logs and domain access.
- `memories/memory_graph.py` — Generates memory domain summaries.
- `memories/index.jsonl` — Append-only ledger file (inspect tail entries).
- `scripts/ci_registry_integrity.py` — Validates ledger integrity in CI.
