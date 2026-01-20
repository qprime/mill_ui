<!-- spec-style -->
# Documentation Maintenance

As-Of Date: 2026-01-19
Document Type: Maintenance Contract
Authority: This document defines which documentation MUST be maintained.

---

## Purpose

Define maintenance obligations for documentation files in this repository.

---

## Terminology

- **Tier 1**: Core architecture documents. MUST update with any architectural change.
- **Tier 2**: Technical specifications. MUST update when related code changes.
- **Tier 3**: Feature trackers. MUST update at feature milestones.
- **Tier 4**: Usage examples. SHOULD verify before major releases.
- **Archival**: Historical records. MUST NOT update except for factual errors.

---

## Active Documentation

### Tier 1: Core Architecture

| Document | Update When |
|----------|-------------|
| README.md | Pipeline changes, data model changes, validation changes, directory structure |
| CLAUDE.md | Workflow changes, extension pattern changes, new pitfalls |

### Tier 2: Technical Specifications

| Document | Update When |
|----------|-------------|
| pml/syntax_spec.md | Parser changes, new shape types, feature syntax changes |
| docs/WORKFLOW.md | New adapters, pipeline stage changes |
| docs/compositional_layout.md | Layout manager changes, resolution logic changes |
| docs/shape_primitives.md | New shapes added |
| docs/layout_primitives.md | New layout managers |
| docs/keepout_islands.md | Constraint system changes |
| docs/edge_treatment.md | Edge treatment implementation changes |
| docs/studio_mode_geometry.md | Spline/polyline semantics changes |

### Tier 3: Feature Tracking

| Document | Update When |
|----------|-------------|
| FEATURES.md | Feature designed, implemented, reviewed, or deprecated |

### Tier 4: Usage Examples

| Document | Update When |
|----------|-------------|
| docs/recipes/README.md | New recipes added |
| docs/recipes/**/README.md | Related syntax or CLI changes |

---

## Synchronization Rules

### When Adding a New Feature

1. FEATURES.md - Add feature entry with status.
2. README.md - Update if user-visible, data models, or pipeline change.
3. CLAUDE.md - Add task example if common workflow.
4. Spec docs - Update relevant docs/*.md if semantics change.

### When Changing Core Data Models

1. README.md - Update data model and terminology sections.
2. CLAUDE.md - Update relevant task examples.
3. docs/WORKFLOW.md - Update if pipeline stages change.

### When Modifying PML Syntax

1. pml/syntax_spec.md - Update grammar and examples.
2. README.md - Update quick start examples if affected.
3. docs/recipes/*.md - Update recipes using changed syntax.

---

## Validation Checklist

Before merging a PR, verify:

- [ ] FEATURES.md updated if new feature added.
- [ ] README.md updated if user-facing, data models, or pipeline changed.
- [ ] Spec docs updated if semantics changed.
- [ ] CLAUDE.md updated if patterns/pitfalls affected.
- [ ] Recipes still work if breaking change.

---

## Automation

### Validation Scripts (scripts/)

| Script | Purpose |
|--------|---------|
| validate_doc_examples.py | Extract and validate code blocks. |
| check_doc_links.py | Check markdown links and file:line references. |
| verify_readme_refs.py | Validate README.md line references. |
| detect_stale_docs.py | Detect source changes without doc updates. |
| validate_pml_examples.py | Test PML code blocks with parsers. |

### CI/CD Integration

File: `.github/workflows/doc-validation.yml`

Runs on PRs touching core source or documentation files.

PRs MUST fail if:
- Code examples don't work.
- Links are broken.
- README.md references invalid lines.

### Pre-Commit Hook

```bash
ln -s ../../scripts/pre-commit-docs-check.sh .git/hooks/pre-commit
```

---

## Document Dependencies

```
README.md
  ├─ References: CLAUDE.md, templates/shaker.py, tests/, docs/recipes/, all core source files
  └─ Referenced by: CLAUDE.md, developer reference

CLAUDE.md
  ├─ References: README.md, layout_ast/layout.py, ir/removal_intent.py
  └─ Referenced by: AI agent context

FEATURES.md
  ├─ References: Implementation files for each feature
  └─ Referenced by: Feature tracking

docs/WORKFLOW.md
  ├─ References: All pipeline components
  └─ Referenced by: README.md
```

---

## Quick Reference

**Always update:** FEATURES.md, README.md (when relevant).

**Update when relevant:** CLAUDE.md, pml/syntax_spec.md, docs/WORKFLOW.md, docs/*.md.

**Verify before release:** docs/recipes/*.md.
