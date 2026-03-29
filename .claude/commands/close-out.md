---
description: Run the full post-implementation close-out workflow — verification, summary, code review, and commit. Use after finishing an implementation task, when the user says "close it out", "wrap it up", or when implementation work is complete and ready for review.
---

# /close-out — Implementation Close-Out

Close out the implementation for: $ARGUMENTS

This skill runs the full verification, summary, and review cycle after an implementation is complete. Follow every phase in order.

---

## Phase 1: Verification

Run all verification steps. Do not skip any.

```bash
source .venv/bin/activate

# 1. Full test suite
python -m pytest tests/ -x

# 2. Recipe validation
python -m tests.test_recipes

# 3. Lint and type checks
ruff check . && ruff format --check . && mypy .
```

**ALL tests and recipes must pass. Zero failures, zero errors, no exceptions.** Do not classify any failure as "pre-existing" or "not part of this change" — if it fails, it blocks the commit. Fix it or raise it to the user. Do not proceed to Phase 2 with any failures.

If recipes need regeneration (new recipe added or output format changed):
```bash
python -m tests.test_recipes --regen_recipes
python -m cli.generate_golden --all-recipes docs/recipes --update --force
```

Report the results: test count, pass/fail. Zero failures required.

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

## Phase 3: Code Review

Perform a self-review of all changes. Read every modified file. Check against:

1. **Correctness** — Does the implementation match the spec? Any off-by-one errors, missing edge cases, or silent failures?
2. **Invariant compliance** — For each relevant invariant file, verify compliance. Build a table:
   ```
   | Invariant | Status |
   |-----------|--------|
   | XX-N (NAME) | Compliant / Exception (documented) |
   ```
3. **Test coverage** — Are all test cases from the spec implemented? Any gaps?
4. **Style** — No comments in code, no unnecessary abstractions, frozen dataclasses not mutated

Rate findings by severity:

```
| # | Severity | File:Line | Finding |
|---|----------|-----------|---------|
| 1 | Bug      | path:123  | Description |
| 2 | Smell    | path:45   | Description |
| 3 | Test gap | —         | Description |
```

**Verdict:** "Clean — ready to commit" or "Needs resolution — N issues"

If issues are found, fix them, re-run Phase 1, and update the summary.

---

## Phase 4: Review Response *(only if Phase 3 found issues)*

For each finding that was fixed:

```
### C-N: <Finding title> — Fixed

<1-2 sentences describing the fix.>
```

Re-run verification and report updated test counts.

---

## Phase 5: Commit

After all phases pass with a clean verdict:

1. Stage the relevant files (not `git add -A` — be specific)
2. Commit with this format:
   - Subject: imperative mood, describes the change, ends with `(closes #N)` if closing an issue
   - Body: categorized bullet points of specific changes
   - Trailer: `Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>`
3. Run `git status` to confirm clean state

Do NOT push unless the user explicitly asks.

---

## Phase 6: Final Summary

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

Post the Implementation Summary (Phase 2) and Code Review (Phase 3) as separate comments on the issue. Use `gh issue comment <number> --body "..."`.
