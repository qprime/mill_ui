# Mill UI Refactor - Codex Stage Review Template

**Instructions**: Use this template for reviewing each completed stage. Replace `{STAGE_ID}`, `{STAGE_NUMBER}`, and other placeholders with stage-specific values.

---

## Review Parameters

- **Stage**: {STAGE_ID} (Stage {STAGE_NUMBER})
- **Stage Name**: {STAGE_NAME}
- **Reviewer Model**: Codex Max (recommended)
- **Review Date**: {DATE}
- **Commits**: {COMMIT_HASHES}
- **Stage Tag**: {STAGE_TAG}

---

## Context

You are reviewing **Stage {STAGE_NUMBER} ({STAGE_ID})** of the Mill UI v2 refactor, a staged implementation plan for transforming a CAD/CAM system into an AI-first compositional architecture.

This is a collaborative multi-agent refactor. Claude has completed Stage {STAGE_NUMBER}. Your role is to verify correctness, adherence to constraints, and architectural soundness before proceeding to the next stage.

## Background Documents

Read these files in order:
1. `skills/mill_ui/mill_ui_refactor.md` - Full refactor specification with 11-stage plan
2. `skills/mill_ui/CLAUDE.md` - Agent collaboration protocol and invariants
3. {ADDITIONAL_DOCS}

## Stage {STAGE_NUMBER} Specification

**Goal**: {GOAL}

**Scope**:
{SCOPE}

**Deliverables**:
{DELIVERABLES}

**Acceptance Tests**:
{ACCEPTANCE_TESTS}

**Equivalence Type**: {EQUIVALENCE_TYPE}

**Back-Compat Guarantee**: {BACK_COMPAT_GUARANTEE}

**Risk / Rollback**: {RISK_ROLLBACK}

**Blocking Dependencies**: {BLOCKING_DEPENDENCIES}

**Commits**: {COMMIT_HASHES}

---

## Your Review Tasks

### 1. Verify Deliverables

For each deliverable listed in the specification:
- [ ] Confirm artifact exists
- [ ] Verify artifact meets specification requirements
- [ ] Check artifact quality and completeness

### 2. Verify Acceptance Tests

For each acceptance test:
- [ ] Run the test command
- [ ] Verify expected output/behavior
- [ ] Document any failures or deviations

### 3. Verify Constraints

- [ ] Confirm v1 code unchanged (unless stage explicitly modifies v1)
- [ ] Verify no unintended side effects outside stage scope
- [ ] Check imports and dependencies still work
- [ ] Verify commits are clean and scoped to stage

### 4. Verify Stage Tracking

- [ ] Confirm `mill_ui_refactor.md` marks stage status as `done`
- [ ] Verify commit hashes recorded in stage table
- [ ] Check "Stage Execution Status" section updated
- [ ] Confirm stage tag `refactor_v2_{STAGE_ID}` exists

### 5. Verify Equivalence Requirements

Based on stage equivalence type: {EQUIVALENCE_TYPE}

**If byte-identical**:
- [ ] Verify G-code output matches v1 byte-for-byte
- [ ] Check deterministic hashing validation passed

**If semantic/geometry-equivalent**:
- [ ] Verify RemovalIntent correctness (region count/types)
- [ ] Check SVG verification (boundaries, toolpaths, envelopes)
- [ ] Verify safety invariants (safe-Z, depth limits, feeds)
- [ ] Confirm geometry verification (dimensions, depths, features)

**If behavioral/safety-equivalent**:
- [ ] Verify safe toolpaths within bounds
- [ ] Check depth constraints respected
- [ ] Confirm feed/spindle rates within tool DB limits

### 6. Code Quality Assessment

- [ ] Code follows Python/project style guidelines
- [ ] Dataclasses used where appropriate (per CLAUDE.md)
- [ ] Pure functions preferred over stateful code
- [ ] All dimensions in millimeters (no mixed units)
- [ ] Adequate test coverage for new code
- [ ] No drive-by refactors outside stage scope

### 7. Architectural Soundness

- [ ] Does implementation align with refactor goals?
- [ ] Are there risks to later stages?
- [ ] Is the approach consistent with established patterns?
- [ ] Are abstractions appropriate and not over-engineered?
- [ ] Does stage enable next stage's dependencies?

### 8. Documentation

- [ ] Code includes docstrings where needed
- [ ] README updates (if required by stage)
- [ ] Commit messages clear and descriptive
- [ ] Stage tracking comments accurate

---

## Review Output Format

Please provide your review as:

```markdown
## Stage {STAGE_NUMBER} ({STAGE_ID}) Review: [PASS / CONDITIONAL PASS / FAIL]

### Deliverables Verification
{For each deliverable}
- {Deliverable name}: [✓/✗] {observations}

### Acceptance Tests Results
{For each test}
- {Test description}: [✓/✗] {results/observations}

### Constraint Verification
- v1 unchanged: [✓/✗] {observations}
- Imports working: [✓/✗] {observations}
- Commits scoped: [✓/✗] {observations}
- Side effects: [✓/✗] {observations}

### Stage Tracking
- Status updated: [✓/✗] {observations}
- Commits recorded: [✓/✗] {observations}
- Tag created: [✓/✗] {observations}

### Equivalence Verification
{Based on stage equivalence type}
- [Equivalence criteria]: [✓/✗] {observations}

### Code Quality
- Style compliance: [✓/✗] {observations}
- Test coverage: [✓/✗] {observations}
- No scope creep: [✓/✗] {observations}

### Architectural Assessment
{Your assessment of:}
- Alignment with refactor goals
- Risks to future stages
- Pattern consistency
- Abstraction appropriateness
- Dependency enablement

### Issues Found
{List any issues by severity}

**Critical** (blocks stage approval):
- {Issue description}

**Major** (should fix before next stage):
- {Issue description}

**Minor** (suggestions for improvement):
- {Issue description}

### Recommendation
- [ ] ✅ Approve - Proceed to next stage
- [ ] ⚠️ Conditional Approval - Proceed with noted issues to address
- [ ] ❌ Reject - Requires rework before proceeding

{If conditional or reject, list specific actions required}

### Additional Notes
{Any other observations, suggestions, or concerns}
```

---

## Success Criteria for Your Review

Your review should:
1. Be thorough and objective
2. Apply rigorous standards consistently
3. Identify deviations from specification
4. Assess impact on future stages
5. Provide clear ruling with justification
6. Document specific issues with remediation steps

## Access Information

- **Repository**: `/home/squinlan/cliff_ai/`
- **Stage commits**: {COMMIT_HASHES}
- **Stage tag**: {STAGE_TAG}
- **Changed files**: {CHANGED_FILES}
- **Working directory**: `/home/squinlan/cliff_ai/skills/mill_ui/`

## Review Execution

1. Read all background documents
2. Review stage specification thoroughly
3. Execute all verification tasks (sections 1-8)
4. Document findings in output format
5. Provide clear recommendation with justification

---

## Notes for Codex

- **Be rigorous**: Apply the same standards you'd apply to production code
- **Be specific**: Reference file paths, line numbers, and commit hashes
- **Be constructive**: Suggest improvements when rejecting or conditionally approving
- **Be consistent**: Use the same evaluation criteria across all stages
- **Be objective**: Focus on specification adherence and architectural soundness

**CRITICAL CONSTRAINTS**:
- **DO NOT fix bugs** - This is a review, not an implementation session
- **DO NOT modify any code** - Only analyze and report findings
- **DO NOT suggest improvements to v1** - v1 is frozen unless stage explicitly modifies it
- **DO NOT rewrite deliverables** - Approve or reject as-is; if rejecting, specify required changes
- **DO NOT install dependencies or fix environment** - Analyze only
- **DO NOT exceed review scope** - Focus on stage specification adherence
- **OUTPUT FORMAT ONLY** - Provide review using the specified markdown template

---

**Template Version**: 1.0
**Last Updated**: 2025-12-16
**Maintained By**: Mill UI Refactor Team (Claude, Codex)
