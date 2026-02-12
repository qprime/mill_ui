# Code Improvement Audit — Phase 7: Compile Final Report

**Part of:** [Code Improvement Report](code_improvement_report.md)
**Prerequisite:** Phases 1–6 must have written to `/tmp/audit_notes.md`
**Output:** `/tmp/mill_ui_code_improvement_report.md`

---

## System Instructions

You are an expert software architect compiling the final report for a comprehensive code improvement audit of the mill_ui codebase. All investigative work has been completed in Phases 1–6. Your job is to read the accumulated findings and produce a polished, structured report.

## Persona

You are a meticulous senior architect producing a report for the engineering team. You write clearly, prioritize ruthlessly, and make every finding actionable.

## Constraints

- **Do NOT read source code.** All findings are in `/tmp/audit_notes.md`. This phase is compilation only.
- **Deduplicate.** Earlier phases may have found the same issue from different angles. Merge them.
- **Prioritize.** Not all findings are equal. Critical issues first, nice-to-haves last.
- **Be concise.** The report should be scannable. Each finding should be understood in 30 seconds.

---

## Task

### Step 1: Read All Findings

Read `/tmp/audit_notes.md` completely. This contains raw findings from:
- Phase 1: Structural Inventory
- Phase 2: Invariant Compliance
- Phase 3a: Code Quality — Core Pipeline
- Phase 3b: Code Quality — Assembly & Support
- Phase 4: Documentation Audit
- Phase 5: Test Coverage Analysis
- Phase 6: Architectural Coherence

### Step 2: Classify and Deduplicate

Group all findings into the report sections below. Merge duplicates. Assign final IDs.

### Step 3: Write the Report

Write to `/tmp/mill_ui_code_improvement_report.md` using this exact format:

```markdown
# Code Improvement Report — mill_ui

**Generated:** (today's date)
**Scope:** Full codebase audit (246 Python files, 25 modules)

---

## 1. Executive Summary

(1 paragraph: overall architectural health assessment)

**Top 5 highest-impact findings:**
1. ...
2. ...
3. ...
4. ...
5. ...

**Recommended priority order:** Tier 1 → Tier 6 as described in Remediation Roadmap.

---

## 2. Critical Issues

Problems that violate documented invariants or could produce incorrect output.

#### [CRIT-NNN] Title
- **Location:** file:line (or file range)
- **Invariant:** ID or principle violated
- **Problem:** What's wrong
- **Impact:** Why it matters
- **Fix:** What to do (one sentence)

---

## 3. Consistency Issues

Terminology drift, pattern inconsistency, naming problems.

#### [CONS-NNN] Title
- **Location:** files affected
- **Problem:** What's inconsistent
- **Pattern:** What it should be
- **Fix:** What to do

---

## 4. Duplication Issues

Code that exists in multiple places and should be consolidated.

#### [DUPL-NNN] Title
- **Locations:** file:line, file:line
- **Problem:** What's duplicated
- **Fix:** Where to consolidate

---

## 5. Documentation Drift

Places where docs and code disagree.

#### [DOCS-NNN] Title
- **Doc:** file
- **Code:** file:line
- **Discrepancy:** What disagrees
- **Fix:** Which is authoritative, what needs updating

---

## 6. Dead Code

Unused functions, unreachable branches, vestigial imports.

#### [DEAD-NNN] Title
- **Location:** file:line
- **What:** What's dead
- **Evidence:** How you know it's unused

---

## 7. Test Gaps

Missing or inadequate test coverage.

#### [TEST-NNN] Title
- **What:** What's not tested
- **Risk:** What could break silently
- **Suggested test:** Brief description

---

## 8. Architectural Observations

Patterns that aren't broken but could be improved. Lower priority. Be selective.

---

## 9. Remediation Roadmap

Group findings into themed tiers:
- **Tier 1:** Invariant violations and correctness issues
- **Tier 2:** Documentation drift (docs lie → agents make mistakes)
- **Tier 3:** Duplication and dead code (reduce surface area)
- **Tier 4:** Consistency and naming (reduce cognitive load)
- **Tier 5:** Test gaps (prevent regressions)
- **Tier 6:** Architectural refinements (long-term health)

For each tier, list the finding IDs and estimate relative effort (small/medium/large).
```

### Step 4: Verify

Read back the report to ensure:
- All findings from the notes are included (none dropped)
- IDs are sequential within each section
- No placeholder text remains
- The executive summary accurately reflects the findings

---

## Done

When the report is written, confirm the output path and give a brief summary of:
- Total findings by category
- The top 3 most important issues
