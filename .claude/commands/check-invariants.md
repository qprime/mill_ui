---
description: Load and check relevant invariant files before modifying a subsystem. Use automatically when editing source files to ensure invariant compliance. Use explicitly when reviewing changes for invariant violations.
---

# Check Invariants

Before modifying any subsystem, read its invariant file and comply with all rules.

## Global Axioms

Always start with: `docs/invariants/README.md`

These are cross-cutting rules that apply to every subsystem.

## Subsystem Invariant Mapping

Read the invariant file that matches the files you are modifying:

| Subsystem Path | Invariant File |
|----------------|----------------|
| `layout_ast/*` | `docs/invariants/data_structures.md` |
| `domains/*` | `docs/invariants/domains.md` |
| `generators/*` | `docs/invariants/generators.md` |
| `assembly/*` | `docs/invariants/assembly.md` |
| `assembly/beams*` | `docs/invariants/beams.md` |
| `assembly/beds*` | `docs/invariants/beds.md` |
| `pml/*` | `docs/invariants/pml.md` |
| `validation/*` | `docs/invariants/validation.md` |
| `ir/*` | `docs/invariants/pipeline.md` |
| `cam/planner/*` | `docs/invariants/planner.md` |
| `cam/*` | `docs/invariants/gcode.md` |
| `nesting/*` | `docs/invariants/nesting.md` |
| `templates/*` | `docs/invariants/components.md` |
| All geometry | `docs/invariants/coordinates.md` |

## How to Use

1. Identify which subsystem(s) your changes touch
2. Read the corresponding invariant file(s)
3. Verify your changes comply with every rule
4. If a change requires an invariant exception, document it explicitly in the implementation spec and update the invariant file

## When Multiple Subsystems Are Touched

Read all relevant invariant files. Cross-cutting changes (e.g., adding a field that flows through AST → IR → Planner) require reading `data_structures.md`, `pipeline.md`, and `planner.md` at minimum.

## Invariant Exceptions

If you must bend an invariant:
1. Document which invariant ID is affected
2. Explain why the exception is necessary
3. Explain why the exception is contained (won't spread)
4. Update the invariant file to record the exception
