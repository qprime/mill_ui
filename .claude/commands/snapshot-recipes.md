---
description: Regenerate all recipe outputs, update commit hashes, and refresh golden metrics. Use on-demand to establish a new baseline — not on every commit.
---

# /snapshot-recipes — Recipe Baseline Snapshot

Regenerate all recipe artifacts and update the golden metrics baseline. This is an on-demand operation, not part of the normal development cycle.

---

## What This Does

1. Regenerates all recipe outputs (G-code, SVG, metrics) from current code
2. Updates `# mill_ui: <hash>` headers in every recipe PML file to the current commit
3. Refreshes the golden metrics store (`tests/golden/`)

## When To Use

- After a batch of implementation changes when you want to establish a new baseline
- Before benchmarking recipe metrics against a previous snapshot
- When the user explicitly asks to update recipe snapshots

Do **not** run this as part of normal cam-engineer or close-out workflows.

---

## Execution

Run all steps sequentially. Pipe to `tail` for context discipline.

```bash
source .venv/bin/activate

# 1. Regenerate all recipe outputs + commit headers
python -m tests.test_recipes --regen_recipes 2>&1 | tail -5

# 2. Update golden metrics baseline
python -m cli.generate_golden --all-recipes docs/recipes --update --force 2>&1 | tail -5

# 3. Verify everything passes
python -m tests.test_recipes 2>&1 | tail -5
```

All recipes must pass after regeneration. If any fail, diagnose and raise to the user.

---

## After Snapshot

Report to the user:
- Number of recipes regenerated
- Whether all recipes pass
- Ask if they want to commit the snapshot (stage `docs/recipes/` and `tests/golden/`)

Do not commit automatically — the user decides when to commit snapshot updates.
