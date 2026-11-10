---
description: Regenerate all recipe outputs from current code.
---

# /snapshot-recipes — Recipe Output Snapshot

Regenerate every recipe's `output/`, the recipe index, the category READMEs and the feature guide from current code. Recipe outputs are regenerated and committed with any change that alters them.

## When To Use

- After a batch of implementation changes that intentionally alter recipe output
- When the user explicitly asks to update recipe snapshots

Do **not** run this as part of normal cam-engineer or close-out workflows.

---

## Execution

Run both steps sequentially. Pipe to `tail` for context discipline.

```bash
# 1. Regenerate all recipe outputs
.venv/bin/python -m cli.recipes --regen 2>&1 | tail -5

# 2. Verify everything passes
.venv/bin/python -m cli.recipes 2>&1 | tail -5
```

All recipes must pass after regeneration. If any fail, diagnose and raise to the user.

---

## After Snapshot

Report to the user:
- Number of recipes regenerated
- Whether all recipes pass
- Ask if they want to commit the snapshot (stage every changed file under `docs/recipes/*/*/output/` and every changed generated document: `docs/recipes/README.md`, `docs/recipes/*/README.md`, `docs/feature_guide.md`; one path per `git add`)

Do not commit automatically — the user decides when to commit snapshot updates.
