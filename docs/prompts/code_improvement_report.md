# Code Improvement Report — Multi-Phase Audit

**Usage:** Run each phase as a separate Claude session. Each phase reads/writes to a shared scratch file at `/tmp/audit_notes.md` to chain context between sessions.

---

## Why Multiple Phases?

A full codebase audit reads hundreds of files, which exceeds a single session's context window. Splitting into phases ensures each session has room to read source files, analyze them, and record findings — without hitting "prompt too long."

The scratch file (`/tmp/audit_notes.md`) persists between sessions and accumulates findings. Phase 7 reads the scratch file and compiles the final report.

---

## Phases

Run these in order. Each phase is a standalone prompt you can paste into a new Claude session with the mill_ui codebase loaded.

| Phase | File | What It Does | Approx. Scope |
|-------|------|-------------|---------------|
| 1 | [audit_phase1_structural_inventory.md](audit_phase1_structural_inventory.md) | Maps codebase structure vs. documented architecture | Docs + module catalogs |
| 2 | [audit_phase2_invariant_compliance.md](audit_phase2_invariant_compliance.md) | Verifies code obeys its own invariants | Invariant files + targeted source reads |
| 3a | [audit_phase3a_code_quality_core.md](audit_phase3a_code_quality_core.md) | Code quality in core pipeline modules | pml, layout_ast, ir, adapters, domains, generators, cam, validation, resolution, core |
| 3b | [audit_phase3b_code_quality_support.md](audit_phase3b_code_quality_support.md) | Code quality in assembly & support modules | assembly, nesting, templates, cli, export, diagram_ir, diagram_render, config, machines, cad, tools, scripts, mill_mcp |
| 4 | [audit_phase4_documentation.md](audit_phase4_documentation.md) | Checks for doc/code drift | Spec files vs. parsers, README accuracy, comment violations |
| 5 | [audit_phase5_test_coverage.md](audit_phase5_test_coverage.md) | Analyzes test coverage and quality | tests/ directory, golden files, recipe coverage |
| 6 | [audit_phase6_architectural_coherence.md](audit_phase6_architectural_coherence.md) | Checks pattern consistency and dependency direction | Cross-module analysis |
| 7 | [audit_phase7_compile_report.md](audit_phase7_compile_report.md) | Compiles scratch notes into final report | Reads only `/tmp/audit_notes.md`, no source code |

---

## Running the Audit

### Manual (paste each phase)

```bash
# Start fresh
rm -f /tmp/audit_notes.md

# Run each phase in a new Claude session
# Paste the contents of each phase file as your prompt
# Phase 1 → Phase 2 → Phase 3a → Phase 3b → Phase 4 → Phase 5 → Phase 6 → Phase 7
```

### Automated (sequential sessions)

```bash
rm -f /tmp/audit_notes.md /tmp/mill_ui_code_improvement_report.md

for phase in \
  audit_phase1_structural_inventory \
  audit_phase2_invariant_compliance \
  audit_phase3a_code_quality_core \
  audit_phase3b_code_quality_support \
  audit_phase4_documentation \
  audit_phase5_test_coverage \
  audit_phase6_architectural_coherence \
  audit_phase7_compile_report; do

  echo "=== Running $phase ==="
  claude -p "$(cat docs/prompts/${phase}.md)"
done

echo "Report written to /tmp/mill_ui_code_improvement_report.md"
```

---

## Output

- **Scratch file:** `/tmp/audit_notes.md` (accumulated findings from phases 1–6)
- **Final report:** `/tmp/mill_ui_code_improvement_report.md` (compiled by phase 7)

---

## Report Format

The final report contains these sections:

1. **Executive Summary** — Overall health + top 5 findings
2. **Critical Issues** `[CRIT-NNN]` — Invariant violations, correctness risks
3. **Consistency Issues** `[CONS-NNN]` — Terminology drift, pattern inconsistency
4. **Duplication Issues** `[DUPL-NNN]` — Code that should be consolidated
5. **Documentation Drift** `[DOCS-NNN]` — Where docs and code disagree
6. **Dead Code** `[DEAD-NNN]` — Unused functions, vestigial imports
7. **Test Gaps** `[TEST-NNN]` — Missing or inadequate coverage
8. **Architectural Observations** — Lower-priority structural notes
9. **Remediation Roadmap** — Findings grouped into themed tiers (Tier 1–6)
