# Memory Framework Overview

The memory framework extends cliff_ai with a deterministic, AI-first operating model. Every interaction writes a typed Memory into an append-only ledger, chained by SHA-256. Truth lives in `cliff_ai.mind.md`; all actions reference it explicitly.

The system provides:

- **Typed Memories** with lifecycle and registry status controls.
- **Deterministic Capsules** that capture truth, notes, and files under explicit budgets.
- **Executors** (`prose_llm`, `codex_cli`, `ops_shell`) that emit manifests, environment captures, and artifacts while respecting OFFLINE mode.
- **Guardrails and Policies** integrating safety paths, PII rules, and freeze windows with signed decisions.
- **Timeline & Interfaces** spanning CLI, REST, and web UI for action orchestration and escalation review.

All workflows default to AI autonomy; humans escalate only when policies demand. Tests and CI enforce ledger integrity, decision coverage, and reproducibility under OFFLINE conditions.

