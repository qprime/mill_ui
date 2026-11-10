---
description: Regenerate all recipe outputs and refresh golden metrics. Use on-demand to establish a new golden baseline.
---

# /snapshot-recipes — Recipe Baseline Snapshot

Regenerate all recipe artifacts and update the golden metrics baseline. This is an on-demand operation for the golden baseline. Recipe outputs themselves are regenerated and committed with any change that alters them.

---

## What This Does

1. Regenerates all recipe outputs (G-code, SVG, metrics, machining summary) from current code
2. Refreshes the golden metrics store (`tests/golden/`)

## When To Use

- After a batch of implementation changes when you want to establish a new baseline
- Before benchmarking recipe metrics against a previous snapshot
- When the user explicitly asks to update recipe snapshots

Do **not** run this as part of normal cam-engineer or close-out workflows.

---

## Execution

Run all steps sequentially. Pipe to `tail` for context discipline.

```bash
# 1. Regenerate all recipe outputs
.venv/bin/python -m tests.test_recipes --regen_recipes 2>&1 | tail -5

# 2. Update golden metrics baseline
.venv/bin/python -m cli.generate_golden --all-recipes docs/recipes --update --force 2>&1 | tail -5

# 3. Verify everything passes
.venv/bin/python -m tests.test_recipes 2>&1 | tail -5
```

All recipes must pass after regeneration. If any fail, diagnose and raise to the user.

---

## After Snapshot

Report to the user:
- Number of recipes regenerated
- Whether all recipes pass
- Ask if they want to commit the snapshot (stage every changed file under `docs/recipes/*/output/` and `tests/golden/`, one path per `git add`)

Do not commit automatically — the user decides when to commit snapshot updates.
