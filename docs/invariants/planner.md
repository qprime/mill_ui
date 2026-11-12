# Planner Contract Invariants

**Applies to:** RemovalIntent → Planner adapter, CAM planner passes

---

## Core Invariant

| ID | Type | Invariant | Description |
|----|------|-----------|-------------|
| PC-1 | HARD | NO_SILENT_DROPS | Unsupported constraints must not silently pass. Safety-critical constraints error; others warn. |
| PC-2 | HARD | CONSTRAINT_AUDIT | Every pipeline run must audit constraints and emit a summary. |
| PC-3 | STRUCTURAL | TYPED_PLANNER_INPUT | Planner receives typed PlannerInput, not untyped hints dict. |
| PC-4 | HARD | REQUIRED_EDGE_MACHINING | A requested edge cut that cannot be planned is a design error; suppress G-code for that setup. |

---

## Constraint Support Matrix

The adapter (`adapters/removal_to_planner.py`) converts RemovalIntent to PlannerInput. This table documents what is honored vs. ignored.

| RemovalIntent Field | Support Status | Safety | Notes |
|---------------------|----------------|--------|-------|
| bounds | HONORED | — | Geometry passed through |
| shape_geometry.holes | HONORED | — | Polygon pockets: offset loops stay out of holes. Profile and edge passes follow the outer loop. |
| depth_profile.z_top/z_bottom | HONORED | — | As depth_mm, start_depth_mm |
| depth_profile.mode (constant) | HONORED | — | Default mode |
| depth_profile.mode (v_carve) | NOT_IMPLEMENTED | — | v_angle_deg not passed |
| depth_profile.mode (linear_gradient) | NOT_IMPLEMENTED | — | gradient_direction_deg not passed |
| constraints.tabs | HONORED | — | Profiles only |
| constraints.onion_skin_mm | HONORED | — | Profiles only; mutually exclusive with tabs |
| constraints.keepouts | HONORED | CRITICAL | PML Keepout zones attach to front intents. Complete cutting segments are checked against bounds expanded by tool radius; a violation blocks that setup's G-code. |
| constraints.islands | HONORED | — | Pockets: island bounds are subtracted from the pocket region, cut with offset loops. Rejected with surface_cooling. |
| constraints.edge_treatment | HONORED | — | Allowance type splits pocket/profile into rough+finish passes. Polygon pockets and pockets with islands: rough offset loops leave the rough allowance on every wall, finish contours cut to the finish allowance. |
| constraints.tolerance_mm | NOT_IMPLEMENTED | — | Uses global tolerance |
| constraints.safe_z_mm | NOT_IMPLEMENTED | — | Uses global safe_z |
| rest | HONORED | — | Two-tool rest pocketing: rough with large tool, finish corners + perimeter with small tool. A plain Rect uses the rectangle pass; a Polygon (holes allowed) or a Rect with islands uses offset loops that follow the region. Mutually exclusive with edge_treatment allowance. |
| corner_cleanup | HONORED | — | Secondary tool pass for rectangular pocket internal corners |
| dogbone | HONORED | — | Rectangular pockets, assembly dados, and notch internal corners: bore per style with reference_point for 2-corner notches |
| edge_feature (bevel/chamfer) | HONORED | CRITICAL | V-bit boundary-following pass; unavailable tooling or unsupported geometry errors |
| edge_feature (roundover) | HONORED | CRITICAL | Roundover bit boundary-following pass; unavailable tooling or unsupported geometry errors |
| edge_feature (raised_panel) | HONORED | CRITICAL | Compound offset-pocket and matching V-bit contour plan; required depth, cell containment and tooling are enforced |
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

## Required Edge Machining (PC-4)

A bevel, chamfer, roundover, or raised panel is part of the requested finished geometry. If the
planner cannot machine it, the job must not succeed with that cut omitted.
Missing or unknown specifications, unavailable tooling, invalid selected-tool
angles, nonpositive cutting depths, and unsupported or collapsed geometry produce
errors naming the feature and the unmet requirement.

The planner collects errors for every rejected edge while retaining valid planned
passes for diagnostics. `plan_passes()` returns passes, summary, warnings, and
errors. The pipeline suppresses every G-code file for a setup with planner errors,
retains its blueprint and metrics, and may retain valid programs for the other
setup. The CLI exits 3. The normal clean-output workflow removes stale programs.
An explicit `--no-clean` preserves existing files and does not certify them as
current build outputs; consumers must use the current metrics and output list.

Tool-library entries may include explicitly identified recipe example tools when
the owner authorizes them. These describe modeled geometry and example feeds,
not verified shop inventory. Do not silently invent availability or substitute
another machining strategy to make a failing recipe appear successful.
The tool selectors retain nearest-angle/radius lookup. A selected tool must also
be able to produce the requested geometry; selection and planning failures must
be surfaced rather than warned away.

Chamfers specify a slope from the stock surface. A surface angle `a` requires
a V-bit included angle `180 - 2a`. The tip follows the nominal edge and reaches
`width * tan(a)` below the local surface for either retained side. The selected
bit must reproduce the requested width within 0.001mm output precision and its
cutting radius must accommodate that width. Do not silently substitute a
different bevel slope or cut wider than the available cutter. Bevel and roundover
strategies retain their separate behavior.

Roundovers use a simple bearingless quarter-circle cutter model. For profile
radius `R` and full cutting diameter `D`, the nose radius is `D/2 - R` and must
be nonnegative. The axis follows that nose-radius offset from the nominal
boundary, outward for an outside edge and inward for an opening. Point cutters
with `D = 2R` follow the nominal boundary. Depth is `R` below the starting surface.
Do not use `R` itself as the lateral offset or silently accept a nearby rounding
radius. Selected tool radius must match within 0.001mm; invalid dimensions and
radius mismatch are required-planning errors. Bearing-guided and extended-nose
cutters require an appropriate geometry model before use.

The YAML machine library preserves `type: roundover` and
`roundover_radius_mm` through `Endmill`, resolved tool dictionaries,
`ToolSelection`, and `Tool`. A roundover requires a finite positive radius that
fits its diameter; another type must not carry a silently ignored roundover
radius. Material-specific feeds remain required for inclusion in a tool DB.

### Raised-panel profiles

RaisedPanel carries one semantic `RaisedPanelSpec` through AST, RemovalIntent,
and typed planner input. The generator does not encode computed toolpaths or
split it into unrelated bevel/pocket intents. The shared immutable edge plan
contains the V-bit contour and required flat-pocket regions/tools/depths; drawing
and machining consume that same plan.

`gutter` preserves the declared total border width, using a flat-bottom gutter
and a tool-matched inner slope. `v_groove` derives its border width from the
included bit angle and depths. Zero field depth preserves the original face and
emits no field pocket. Border depth is honored directly, never recalculated
from a hidden bevel angle, and must be less than stock thickness.

The selected V-bit must match the specified included angle and accommodate the
full cutting radius at maximum depth. Insets must leave a single connected
field and groove; the slope must preserve the declared field. The full V-bit
cutting footprint stays inside the cell. Flat clearing uses existing offset
pocket operations with a 0.0005mm rounded-offset arc approximation tolerance;
the default tolerance of unrelated pocket operations is unchanged. No surface
raster, ball-nose substitution or nearest-angle approximation is permitted.
No fitting flat tool, an empty required pocket toolpath, holes, nonzero starting
surfaces, or impossible geometry errors and blocks the setup. Finite cutters
leave rounded internal corners and retained stock; no sharp-corner guarantee
or automatic decorative dogbone is implied.

---

## Spiral Pocket Coverage

Spiral pockets complete each inset contour at every layer depth before moving
to the next contour. The outer contour starts at the actual end of its entry
ramp and must be completed at depth, including the edge used for ramping.
Bridges between contours must not replace a required boundary segment.

## Rectangle Profiles and Shared Cuts

Rectangle profiles use the canonical closed-profile operation with the requested
`inside`, `outside`, or `on` cutter offset. Isolated or incompatible profiles keep
their feed overrides, allowances, and existing holding operations.

Profile edge allowances may combine with tabs or onion skin. Roughing retains a
continuous bottom web equal to the tab height or onion-skin thickness. The final
XY contour is then cut in a deferred `profile_finish` operation, keeping tabs or
leaving the specified onion skin. The same scheduler handles every supported
profile shape and global or per-feature holding options.

Tab height and onion-skin thickness are measured from the nominal cut depth;
cut-through is added once to the final cutting depth and never reduces the
specified holding thickness. Tab spans survive entry ramps, retracing, and polygon
corners. Tabs and onion skin on the same feature remain mutually exclusive.

Onion-skin removal uses a separate `release` operation after every deferred finish.
Its programs remain separate and last even with per-tool output grouping, so a
release cannot move ahead of another tool's finishing. Planned passes and emitted
program order must both respect this barrier. An inside rectangle whose
compensated centerline collapses is rejected.

A shared cut preserves both nominal parts. It is eligible only where compensated
outside tool centerlines coincide, with identical depth and no per-feature feeds,
allowance, tabs, onion skin, ramp distance, or nonzero start depth. Any job using
tabs or onion skin keeps ordinary profiles. Connected compatible rectangles use
shared seams followed by closed contours around their union, including holes.
Partial seams retain the rest of the boundary. All contours use the existing
profile operation; ramp entries follow boundary segments without corner shortcuts.

Two outside rectangle profiles require at least the selected cutter's diameter
between retained material regions, including each profile's largest positive
rough/finish allowance, even when merging is disabled. Touching nominal
rectangles cannot share a cut while preserving dimensions and are rejected.
Nesting must provide the configured kerf plus gap margin. A larger actual selected
cutter can still cause the planner to reject that spacing.

`merge_epsilon_mm <= 0` disables sharing. A positive value enables it but never
permits moving separated tool centerlines together: only floating-point precision
(1e-9 mm) is used to identify coincident paths. Existing minimum-overlap settings
continue to limit eligible seams.

---

## Keepouts: Safety-Critical Constraint

Keepouts represent regions where the tool must not enter (typically fixture/clamp locations). Machining through a keepout can:

- Damage fixtures
- Break tooling
- Ruin workpiece
- Cause safety hazards

**Policy:** If any RemovalIntent specifies keepouts, the planner MUST avoid those regions. Failure to honor keepouts is a build error.

PML `Keepout` declares fixture geometry; `Island` declares material a pocket preserves. Keepouts apply to the front setup only, whose fixtures are independent of the back setup. Verification follows modal XY positions across moves and passes in each emitted file, including Z-only plunges. An unknown cutting position is an error. The verifier does not clip or reroute paths.

Rapid crossings warn with zone identity and safe Z. Clamp height is not modeled, so the operator confirms clearance. A cutting violation suppresses all `.nc` output for the affected setup while retaining diagnostic geometry and blueprints.

---

## Constraint Audit Output

Every pipeline run emits a constraint audit summary:

```
Constraint Audit:
  tabs: HONORED (3 intents)
  keepouts: HONORED (2 regions)
  islands: HONORED (1 intent)
  edge_treatment: HONORED (1 intent)
```

If safety-critical constraints are present but not honored, the build fails with an error.

---

## Adding New Constraint Support

When implementing support for a new constraint:

1. Update `PlannerInput` dataclass with new field
2. Update `removal_intents_to_planner_input()` to extract constraint
3. Update relevant planner pass to honor constraint
4. Add post-plan verification if applicable
5. Update this invariant file's support matrix
6. Add end-to-end test verifying constraint is honored

---

## Post-Plan Verification

For safety-critical constraints, the pipeline includes post-plan verification:

| Constraint | Verification |
|------------|--------------|
| keepouts | `verify_toolpath_avoids_keepouts()` — checks complete cutting segments and plunges, expanded by tool radius; rapids warn |

Post-plan verification runs after toolpath generation and before G-code output. Violations are errors.

---

## Invariant Types

| Type | Meaning |
|------|---------|
| HARD | Violation breaks safety or correctness guarantees |
| STRUCTURAL | Requires coordinated migration to change |
