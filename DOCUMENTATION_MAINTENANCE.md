# Documentation Maintenance Guide

This document identifies which documentation files must be kept up-to-date as the system evolves, and which are historical/archival.

---

## Active Documentation (MUST MAINTAIN)

These documents are **living references** that must stay synchronized with code changes.

### Tier 1: Core Architecture (Update with ANY architectural change)

| Document | Purpose | Update When |
|----------|---------|-------------|
| [README.md](README.md) | Main entry point, architecture overview, quick start | • Pipeline changes<br>• New features added to core IR<br>• Directory structure changes<br>• Installation steps change |
| [CLAUDE.md](CLAUDE.md) | AI agent development guide, practical patterns | • Common task workflows change<br>• Extension patterns change<br>• New pitfalls discovered<br>• Mental models need refinement |
| [GROUND_TRUTH.md](GROUND_TRUTH.md) | Factual system state extracted from source | • Data model changes<br>• Pipeline boundaries shift<br>• Coordinate conventions change<br>• New validation added |

**Maintenance cadence:** Review on every PR that touches core architecture (AST, IR, adapters, planner interface).

### Tier 2: Technical Specifications (Update with related code changes)

| Document | Purpose | Update When |
|----------|---------|-------------|
| [pml/syntax_spec.md](pml/syntax_spec.md) | PML language grammar | • Parser changes<br>• New shape types added<br>• Feature syntax changes |
| [docs/WORKFLOW.md](docs/WORKFLOW.md) | Pipeline flow diagram, format conversions | • New adapters added<br>• Pipeline stages added/removed<br>• Export formats change |
| [docs/compositional_layout.md](docs/compositional_layout.md) | Compositional AST system spec | • Layout managers added/changed<br>• Resolution logic changes<br>• Component system changes |
| [docs/shape_primitives.md](docs/shape_primitives.md) | Shape geometry specifications | • New shapes added (Ellipse, Polygon, etc.)<br>• Geometry parameters change |
| [docs/layout_primitives.md](docs/layout_primitives.md) | Layout manager specifications | • New layout managers (Split, Stack, etc.)<br>• Grid/Frame semantics change |
| [docs/keepout_islands.md](docs/keepout_islands.md) | Constraint system documentation | • Keepout/island semantics change<br>• New constraint types added |
| [docs/edge_treatment.md](docs/edge_treatment.md) | Edge treatment feature spec | • Edge treatment implementation changes<br>• New treatment types added |
| [docs/studio_mode_geometry.md](docs/studio_mode_geometry.md) | Studio Mode (expressive geometry) spec | • Spline/polyline semantics change<br>• Studio mode features added |

**Maintenance cadence:** Update immediately when related code changes. Check during code review.

### Tier 3: Feature Tracking (Update as features evolve)

| Document | Purpose | Update When |
|----------|---------|-------------|
| [FEATURES.md](FEATURES.md) | Feature development tracker with status | • New feature designed<br>• Feature implementation completed<br>• Feature reviewed/approved<br>• Feature deprecated |

**Maintenance cadence:** Update at feature milestones (design → implemented → reviewed).

### Tier 4: Usage Examples (Verify on major releases)

| Document | Purpose | Update When |
|----------|---------|-------------|
| [docs/recipes/README.md](docs/recipes/README.md) | Recipe index | • New recipes added<br>• Recipe categories change |
| [docs/recipes/01_simple_profile.md](docs/recipes/01_simple_profile.md) | Basic profile workflow | • Profile syntax changes<br>• CLI tools change |
| [docs/recipes/02_pocket_with_cleanup.md](docs/recipes/02_pocket_with_cleanup.md) | Pocket cleanup (F001) example | • F001 feature changes<br>• Config options change |
| [docs/recipes/03_shaker_door_template.md](docs/recipes/03_shaker_door_template.md) | Shaker template usage | • Shaker template API changes<br>• Template system changes |

**Maintenance cadence:** Verify examples work before each major release. Update if breaking changes occur.

---

## Archival Documentation (READ-ONLY)

These documents are **historical records** and should NOT be updated (except for corrections to factual errors).

### Historical Artifacts

| Document | Purpose | Status |
|----------|---------|--------|
| [V1toV2_artifacts/README.md](V1toV2_artifacts/README.md) | V1→V2 migration overview | ✅ Frozen |
| [V1toV2_artifacts/mill_ui_refactor.md](V1toV2_artifacts/mill_ui_refactor.md) | Original refactor design doc | ✅ Frozen |
| [V1toV2_artifacts/V2_PROMOTION_PLAN.md](V1toV2_artifacts/V2_PROMOTION_PLAN.md) | V2 promotion strategy | ✅ Frozen |
| [V1toV2_artifacts/STAGE_6_REVIEW_RESPONSE.md](V1toV2_artifacts/STAGE_6_REVIEW_RESPONSE.md) | Stage 6 review responses | ✅ Frozen |
| [V1toV2_artifacts/V2_ARCHIVE_README.md](V1toV2_artifacts/V2_ARCHIVE_README.md) | V2 archive notes | ✅ Frozen |
| [V1toV2_artifacts/reviews/*.md](V1toV2_artifacts/reviews/) | Codex review artifacts | ✅ Frozen |

**These documents capture design decisions and review history. Do not modify except to fix factual errors.**

### Test Documentation (Semi-Archival)

| Document | Purpose | Status |
|----------|---------|--------|
| [tests/EQUIVALENCE_TESTING.md](tests/EQUIVALENCE_TESTING.md) | V1/V2 equivalence test strategy | ⚠️ Update only if equivalence testing strategy changes |

---

## Special Cases

### UI_WORKPLAN.md
**Status:** ⚠️ Active project plan (separate from codebase docs)

This appears to be a UI development workplan. Update as UI project progresses, but it's independent of the core mill_ui CAM pipeline.

### cam/native/README.md
**Status:** 🔧 Maintenance (build instructions)

Update when:
- Build process changes
- Native backend API changes
- Dependencies change

---

## Synchronization Strategy

### When Adding a New Feature

**Required Updates:**
1. ✅ **FEATURES.md** - Add feature entry with status
2. ✅ **README.md** - Add to feature list (if user-visible) and extension points (if extensible)
3. ✅ **CLAUDE.md** - Add task example if it's a common workflow
4. ⚠️ **GROUND_TRUTH.md** - Update if it changes data models, pipeline, or validation
5. ⚠️ **Spec docs** - Update relevant docs/\*.md if it changes semantics

**Optional:**
- Add recipe to docs/recipes/ if it demonstrates new capability

### When Changing Core Data Models

**Required Updates:**
1. ✅ **GROUND_TRUTH.md** - Section 1 (Core Data Model)
2. ✅ **README.md** - Core Concepts section
3. ✅ **CLAUDE.md** - Update relevant task examples
4. ⚠️ **docs/WORKFLOW.md** - If pipeline stages change

### When Adding/Removing Pipeline Stages

**Required Updates:**
1. ✅ **GROUND_TRUTH.md** - Section 2 (Canonical Execution Path)
2. ✅ **README.md** - Pipeline diagram/description
3. ✅ **docs/WORKFLOW.md** - Full pipeline diagram
4. ⚠️ **CLAUDE.md** - Update mental model/compiler analogy if applicable

### When Modifying PML Syntax

**Required Updates:**
1. ✅ **pml/syntax_spec.md** - Grammar and examples
2. ✅ **README.md** - Quick start examples (if affected)
3. ⚠️ **docs/recipes/\*.md** - Update recipes using changed syntax

---

## Validation Checklist (For Code Reviewers)

Before merging a PR, verify:

- [ ] **FEATURES.md** updated if new feature added
- [ ] **README.md** updated if user-facing change or architecture shift
- [ ] **GROUND_TRUTH.md** updated if data models/pipeline/validation changed
- [ ] **Spec docs** (pml/syntax_spec.md, docs/\*.md) updated if semantics changed
- [ ] **CLAUDE.md** updated if common patterns/pitfalls/mental models affected
- [ ] **Recipes** (docs/recipes/\*.md) still work (run examples if breaking change)

---

## Document Dependencies

Understanding which docs reference which helps maintain consistency:

```
README.md
  ├─ References: CLAUDE.md, templates/shaker.py, tests/, docs/recipes/
  └─ Referenced by: CLAUDE.md (primary architecture reference)

CLAUDE.md
  ├─ References: README.md, layout_ast/layout.py, ir/removal_intent.py, adapters/ast_to_removal.py
  └─ Referenced by: (AI agent context loading)

GROUND_TRUTH.md
  ├─ References: All core source files with line numbers
  └─ Referenced by: (developer design reference)

FEATURES.md
  ├─ References: Implementation files for each feature
  └─ Referenced by: (feature tracking)

docs/WORKFLOW.md
  ├─ References: All pipeline components
  └─ Referenced by: README.md

pml/syntax_spec.md
  ├─ References: layout_ast/layout.py (implicitly)
  └─ Referenced by: README.md, pml parsers

docs/compositional_layout.md
  ├─ References: layout_ast/compositional.py, resolution/layout_resolver.py
  └─ Referenced by: README.md, CLAUDE.md
```

---

## Automation (IMPLEMENTED)

We have automated documentation validation to reduce manual burden and catch issues early.

### Validation Scripts (scripts/)

All scripts are located in `scripts/` and can be run locally or in CI:

1. **validate_doc_examples.py** ✅
   - Extracts Python and PML code blocks from markdown
   - Validates Python syntax and execution (safe code only)
   - Verifies PML examples parse correctly
   - **Usage:** `python3 scripts/validate_doc_examples.py`

2. **check_doc_links.py** ✅
   - Checks all `[text](path)` links in markdown
   - Validates file:line references like `[file.py:123](file.py#L123)`
   - Ensures directory links exist
   - **Usage:** `python3 scripts/check_doc_links.py`

3. **verify_ground_truth_refs.py** ✅
   - Validates all file:line references in GROUND_TRUTH.md
   - Ensures line numbers still point to correct code
   - **Usage:** `python3 scripts/verify_ground_truth_refs.py`

4. **detect_stale_docs.py** ✅
   - Uses git history to detect when source files changed without doc updates
   - Warns if core files (AST, IR, adapters) modified but docs not updated
   - Checks recent commits for doc-requiring changes
   - **Usage:** `python3 scripts/detect_stale_docs.py`

5. **validate_pml_examples.py** ✅
   - Extracts all PML code blocks from documentation
   - Tests with both flat and compositional parsers
   - **Usage:** `python3 scripts/validate_pml_examples.py`

### CI/CD Integration (GitHub Actions)

**File:** `.github/workflows/doc-validation.yml`

This workflow runs on every pull request that touches:
- Core source files (layout_ast, ir, adapters, pml, resolution, templates, validation)
- Documentation files (docs/, *.md)

**Jobs:**
- `validate-examples` - Runs validate_doc_examples.py
- `check-broken-links` - Runs check_doc_links.py
- `verify-ground-truth` - Runs verify_ground_truth_refs.py
- `detect-stale-docs` - Runs detect_stale_docs.py (warnings only)
- `validate-pml-syntax` - Runs validate_pml_examples.py

**Status:** PRs will fail if:
- Code examples don't work
- Links are broken
- GROUND_TRUTH.md references invalid lines

### Pre-Commit Hook (Optional)

**File:** `scripts/pre-commit-docs-check.sh`

Install locally for pre-commit validation:
```bash
ln -s ../../scripts/pre-commit-docs-check.sh .git/hooks/pre-commit
```

This hook runs quick checks before commits that modify core source files:
- Broken link detection
- GROUND_TRUTH.md reference validation
- Stale docs detection (warning only)

### Running All Checks Locally

```bash
# Run all validation scripts
python3 scripts/validate_doc_examples.py
python3 scripts/check_doc_links.py
python3 scripts/verify_ground_truth_refs.py
python3 scripts/detect_stale_docs.py
python3 scripts/validate_pml_examples.py
```

### Auto-Update Opportunities (Not Yet Implemented)

Future improvements:

1. **GROUND_TRUTH.md auto-extraction**
   - Script to extract dataclass definitions from source
   - Generate pipeline trace from test cases
   - Auto-map test coverage

2. **Doc coverage report**
   - Track which source files are documented
   - Identify undocumented APIs

3. **Changelog integration**
   - Auto-generate documentation update checklist based on changed files

---

## Summary: Quick Reference

**Always update:**
- FEATURES.md (when feature status changes)
- README.md (when user-facing changes occur)
- GROUND_TRUTH.md (when core architecture/data models change)

**Update when relevant:**
- CLAUDE.md (when dev patterns/workflows change)
- pml/syntax_spec.md (when parser changes)
- docs/WORKFLOW.md (when pipeline changes)
- docs/\*.md spec files (when semantics change)

**Never update:**
- V1toV2_artifacts/\* (historical record)

**Verify before release:**
- docs/recipes/\*.md (examples still work)
