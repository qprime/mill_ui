# Audit Context

Living document maintained by the `/audit` skill with user approval. Tracks deferred findings, dismissed observations, and escalation history across audit runs.

The audit skill proposes changes to this file at the end of each run. Changes require user approval before being written.

---

## Last Audit

- **commit**: 087504fd
- **date**: 2026-04-02
- **scope**: Full audit (initial run — conventions.md gap analysis)
- **trigger**: `/audit conventions.md` — assessed conventions coverage against codebase patterns

---

## Deferred Findings

Items classified as shareability debt — real structural problems not causing bugs or agent errors today. Rechecked on subsequent audits; escalated if the debt grows.

Format: `[area] description — first observed [date], commit [hash]. Reason for deferral. Stable count: N`

### Dispatch Debt

- **[pml/yaml_parser.py] `parse_node()` if/elif chain** — first observed 2026-04-02, commit 087504fd. 40+ node types in a single if/elif chain. Documented as known debt in conventions.md ("Not registry-based, known debt, deferred"). Not causing agent errors because conventions document it explicitly. Stable count: 0

- **[cam/planner/passes] Shape-type dispatch if/elif chains** — first observed 2026-04-02, commit 087504fd. Profile planning dispatches on shape type via if/elif with `.lower()`. Documented as known debt in conventions.md. Stable count: 0

### Duplication

- **[generators/measurement] Measurement generator duplication** — first observed 2026-04-02, commit 087504fd. Tracked in #101. Multiple measurement generators share parameter patterns and coordinate logic. Stable count: 0

---

## Dismissed Findings

Observations the user has explicitly dismissed. The audit skill will not re-report these unless the surrounding code changes materially.

(none yet)

---

## Escalation History

Items that graduated from deferred to filed as issues.

(none yet)

---

## Audit Log

| Date | Commit | Scope | Filed | Deferred | Dismissed |
|------|--------|-------|-------|----------|-----------|
| 2026-04-02 | 087504fd | conventions.md gap analysis | 0 | 3 | 0 |
