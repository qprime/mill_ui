# Planner Contract Invariants

**Applies to:** RemovalIntent → Planner adapter, CAM planner passes

---

## Core Invariant

| ID | Type | Invariant | Description |
|----|------|-----------|-------------|
| PC-1 | HARD | NO_SILENT_DROPS | Unsupported constraints must not silently pass. Safety-critical constraints error; others warn. |
| PC-2 | HARD | CONSTRAINT_AUDIT | Every pipeline run must audit constraints and emit a summary. |
| PC-3 | STRUCTURAL | TYPED_PLANNER_INPUT | Planner receives typed PlannerInput, not untyped hints dict. |

---

## Constraint Support Matrix

The adapter (`adapters/removal_to_planner.py`) converts RemovalIntent to PlannerInput. This table documents what is honored vs. ignored.

| RemovalIntent Field | Support Status | Safety | Notes |
|---------------------|----------------|--------|-------|
| bounds | HONORED | — | Geometry passed through |
| depth_profile.z_top/z_bottom | HONORED | — | As depth_mm, start_depth_mm |
| depth_profile.mode (constant) | HONORED | — | Default mode |
| depth_profile.mode (v_carve) | NOT_IMPLEMENTED | — | v_angle_deg not passed |
| depth_profile.mode (linear_gradient) | NOT_IMPLEMENTED | — | gradient_direction_deg not passed |
| constraints.tabs | HONORED | — | Profiles only |
| constraints.keepouts | HONORED | CRITICAL | Toolpath avoids keepout bounds |
| constraints.islands | NOT_IMPLEMENTED | — | Not yet passed to planner |
| constraints.edge_treatment | NOT_IMPLEMENTED | — | Not yet passed to planner |
| constraints.tolerance_mm | NOT_IMPLEMENTED | — | Uses global tolerance |
| constraints.safe_z_mm | NOT_IMPLEMENTED | — | Uses global safe_z |
| allowance.inside/outside/on | VALIDATED_ONLY | — | May be applied upstream by generators |
| allowance.kerf_compensation | VALIDATED_ONLY | — | Applied via global kerf_width_mm |

### Support Status Definitions

| Status | Meaning | Audit Behavior |
|--------|---------|----------------|
| HONORED | Constraint flows to planner and affects toolpath | No message |
| VALIDATED_ONLY | Constraint validated at IR level but not passed to planner | Warning |
| NOT_IMPLEMENTED | Constraint exists in IR but not yet supported | Warning |
| IGNORED | Constraint intentionally not supported | Warning |

### Safety Levels

| Level | Meaning | Audit Behavior |
|-------|---------|----------------|
| CRITICAL | Violation could damage machine, fixture, or part | Error (fails build) |
| — | No special safety concern | Warning only |

---

## Keepouts: Safety-Critical Constraint

Keepouts represent regions where the tool must not enter (typically fixture/clamp locations). Machining through a keepout can:

- Damage fixtures
- Break tooling
- Ruin workpiece
- Cause safety hazards

**Policy:** If any RemovalIntent specifies keepouts, the planner MUST avoid those regions. Failure to honor keepouts is a build error.

---

## Constraint Audit Output

Every pipeline run emits a constraint audit summary:

```
Constraint Audit:
  tabs: HONORED (3 intents)
  keepouts: HONORED (2 regions)
  islands: NOT_IMPLEMENTED (1 intent) [warning]
  edge_treatment: NOT_IMPLEMENTED (0 intents)
```

If safety-critical constraints are present but not honored, the build fails with an error.

---

## Adding New Constraint Support

When implementing support for a new constraint:

1. Update `PlannerInput` dataclass with new field
2. Update `removal_intent_to_planner_input()` to extract constraint
3. Update relevant planner pass to honor constraint
4. Add post-plan verification if applicable
5. Update this invariant file's support matrix
6. Add end-to-end test verifying constraint is honored

---

## Post-Plan Verification

For safety-critical constraints, the pipeline includes post-plan verification:

| Constraint | Verification |
|------------|--------------|
| keepouts | `verify_toolpath_avoids_keepouts()` — checks XY bounds of all moves |

Post-plan verification runs after toolpath generation and before G-code output. Violations are errors.

---

## Invariant Types

| Type | Meaning |
|------|---------|
| HARD | Violation breaks safety or correctness guarantees |
| STRUCTURAL | Requires coordinated migration to change |
