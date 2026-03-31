---
description: Run the full post-implementation close-out workflow — verification, summary, and commit. Only use when the user explicitly asks — e.g. "close it out", "wrap it up", "/close-out". Never auto-trigger after implementation.
---

# /close-out — Implementation Close-Out

Close out the implementation for: $ARGUMENTS

This skill runs the full verification, summary, and commit cycle after an implementation is complete. Follow every phase in order.

---

## Phase 1: Verification

Run all verification steps. Do not skip any.

**Context discipline:** Verification commands produce large output. Pipe to `tail` to keep only the summary. If a command fails, re-run it WITHOUT the tail to see the full error.

```bash
source .venv/bin/activate

# 1. Full test suite — summary only
python -m pytest tests/ -x -q 2>&1 | tail -5

# 2. Recipe validation — summary only
python -m tests.test_recipes 2>&1 | tail -5

# 3. Lint and type checks — summary only
ruff check . 2>&1 | tail -3 && ruff format --check . 2>&1 | tail -3 && mypy . 2>&1 | tail -3
```

**ALL tests and recipes must pass. Zero failures, zero errors, no exceptions.** Do not classify any failure as "pre-existing" or "not part of this change" — if it fails, it blocks the commit. Re-run the failing command without `| tail` to diagnose, fix it, or raise it to the user. Do not proceed to Phase 2 with any failures.

If recipes need regeneration (new recipe added or output format changed):
```bash
python -m tests.test_recipes --regen_recipes 2>&1 | tail -5
python -m cli.generate_golden --all-recipes docs/recipes --update --force 2>&1 | tail -5
```

Report the results: test count, pass/fail. Zero failures required.

### Recipe cleanup

After verification passes, restore recipe output files to their committed state **unless** this implementation intentionally changed recipes (new recipe added, output format changed, or recipe regeneration was part of the work). Incidental recipe dirtiness from test runs must not leak into the commit.

```bash
git checkout -- docs/recipes/
```

If recipe files ARE part of the implementation:
1. Regenerate with `python -m tests.test_recipes --regen_recipes`
2. Update golden metrics with `python -m cli.generate_golden --all-recipes docs/recipes --update --force`
3. Stage the recipe files explicitly in Phase 5

---

## Phase 2: Implementation Summary

Draft an implementation summary as a GitHub issue comment. Use this exact structure:

```
## Implementation Summary

<1-2 sentence description of what shipped.>

### Files Modified (<N>)

| File | Change |
|------|--------|
| `path/to/file.py` | Description of change |

### Files Created (<N>) *(if any)*

| File | Purpose |
|------|---------|
| `path/to/file.py` | Purpose |

### Design Notes
- Key architectural decisions or non-obvious choices made during implementation
- Any deviations from the original spec and why

### Test Results
<N> passed, zero failures
```

Present this to the user before posting.

---

## Phase 3: Commit

After all phases pass with a clean verdict:

1. Stage the relevant files (not `git add -A` — be specific)
2. Commit with this format:
   - Subject: imperative mood, describes the change, ends with `(closes #N)` if closing an issue
   - Body: categorized bullet points of specific changes
   - Trailer: `Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>`
3. Run `git status` to confirm clean state

Do NOT push unless the user explicitly asks.

---

## Phase 4: Final Summary

Present the final summary to the user:

```
## Final Summary

Committed as `<hash>` — all checks pass (ruff, ruff format, mypy), <N> tests pass, zero failures, all recipes valid.

### What shipped
<2-3 sentence summary of the deliverable>

### Bugs fixed along the way *(if any)*
- **C-N:** <description>

### Files
- <N> source files modified/created
- <N> tests in `tests/test_foo.py`
- Recipe <N> (if applicable)
```

---

## Posting to GitHub *(if user requests)*

Post the Implementation Summary (Phase 2) as a comment on the issue. Use `gh issue comment <number> --body "..."`.
