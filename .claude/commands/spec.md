---
description: Draft a GitHub issue implementation specification. Use when planning a new feature, refactor, or bug fix that needs a detailed spec before implementation.
---

# /spec — Implementation Specification

Draft a GitHub issue implementation specification for: $ARGUMENTS

## Process

1. **Research first.** Read the relevant source files, invariants, and existing patterns before writing anything. Understand what exists before proposing changes.

2. **Draft the spec** as a GitHub issue body using the section template below. Every section is required unless explicitly marked optional. Omit a section only if it genuinely does not apply (e.g., a pure deletion has no PML syntax).

3. **Present the draft** to the user for review before creating the issue.

---

## Title

Start with an action verb. Describe what the change *does*, not what's missing or broken.

- **Good:** "Add holding strategies (onion skin, tabs) to nest jobs"
- **Bad:** "Nest jobs don't support holding strategies (onion skin, tabs)"
- **Good:** "Migrate nest CLI output from dead flat format to YAML"
- **Bad:** "Nest CLI outputs dead indent-based PML format, mill CLI can't consume it"

## Section Template

### Summary
1-3 sentences. What is being added, changed, or fixed. Actionable and specific.

### Motivation
Why this matters. Concrete pain points — user-facing or developer-facing. Not hypothetical benefits.

### Existing Architecture
What exists today that this change touches. Reference specific files and line numbers. Include function signatures, data flow, and relevant patterns. This section grounds the implementation in reality — do not skip it.

### Design
The technical approach:
- **PML syntax** (if applicable): Show both simple and explicit forms with YAML examples
- **Data flow**: ASCII diagram showing how data moves through pipeline layers
- **Code signatures**: Exact frozen dataclass fields, function signatures with type annotations
- **Invariant exceptions**: If any invariant is bent, document the exception and why it's contained

### Constraint Interactions
How this feature interacts with existing features. For each relevant interaction:
- Is it compatible, mutually exclusive, or conditionally compatible?
- What validation enforces the constraint?

*Optional — omit only if the change is truly isolated (rare).*

### Implementation
Phased or numbered steps. For each step:
- Which file(s) change
- What specifically changes (field additions, new functions, modified logic)
- Code snippets showing exact signatures where the change is non-obvious

Use a per-file change table when touching 3+ files:

```
| File | Change |
|------|--------|
| `path/to/file.py` | Description of change |
```

### Invariants
Which invariant files apply to this change. For each:
- Invariant ID and name
- Whether this change complies or requires a documented exception

### Testing Strategy
Named test cases with expected behavior. Not "write tests" — specific test names and what they verify:

```
TestClassName:
    test_case_name — description of what it verifies and expected outcome
```

Include verification commands:
```bash
python -m pytest tests/test_specific.py -x -v
python -m pytest tests/ -x
```

### What NOT to do
Explicit anti-patterns and scope boundaries. Things that might seem like natural extensions but should not be done in this issue. Explain why for each.

### Files to Modify
Master table of every file that will be created or modified:

```
| File | Change |
|------|--------|
| `path/to/file.py` | Brief description |
```

### Dependencies *(optional)*
Related issues, prerequisites, or things this supersedes.

---

## Quality Checks

Before presenting the draft, verify:

- [ ] Every file referenced actually exists (or is explicitly marked as new)
- [ ] Line numbers are current (not stale from a previous version)
- [ ] Function signatures match the actual codebase
- [ ] Invariant IDs are real (check the invariant files)
- [ ] No section is vague hand-waving — if you can't be specific, you haven't researched enough
- [ ] The "What NOT to do" section has at least one entry
- [ ] Test cases have names, not just descriptions
