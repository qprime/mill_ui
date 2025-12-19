# Mill UI Refactor - Codex Review Results: Stage 19

## Stage 19 (S19_CENTERLINE_SPLINES) Review: ✅ PASS

### Review Parameters
- **Stage Name**: Centerline Spline / Expressive Path Support (Studio Mode)
- **Review Date**: 2025-12-17
- **Commits Reviewed**: `499c34b` (implementation), `5c48527` (tracking update)
- **Stage Tag**: `refactor_v2_S19_CENTERLINE_SPLINES`
- **Tests Executed**: `PYTHONPATH=/home/squinlan/cliff_ai PYTHONPATH=. python3 -m v2.tests.run_spline_tests`

### Deliverables Verification
- **Studio Mode geometry policy** documented in `v2/docs/studio_mode_geometry.md` (centerline intent, permissive warnings, design-first philosophy). ✓
- **SplinePath AST node** added with normalized coordinates, tolerance parameter, and validation (`mill_ui/v2/ast/compositional.py:354`). ✓
- **Immediate lowering** implemented via `sample_catmull_rom_spline` with SplinePath resolved straight to polyline items (metadata preserved) in `mill_ui/v2/resolution/layout_resolver.py:44-573`. ✓
- **Catmull-Rom sampling** deterministic and tolerance-driven; helper function lives in resolver module. ✓
- **PML syntax + formatter** (`parse_spline`, canonical formatter output) support optional ID/feature/tolerance per spec. ✓
- **Integration**: Splines respect current region context, support engrave features, and produce standard polyline items consumed by existing adapters. ✓

### Acceptance Tests Results
- `run_spline_tests.py`: **✓ PASS** – 5/5 acceptance scenarios covered:
  1. Spline parsing + round-trip preservation
  2. Deterministic lowering to polyline (metadata + sampling)
  3. Spline + engrave → valid RemovalIntent
  4. Tool diameter changes do not invalidate design (policy enforcement)
  5. Tolerance parameter affects sampling density
- Regression note: Stage 17 (keepout) and Stage 18 (edge) suites were already passing after their respective fixes.

### Constraint Verification
- v1 untouched: **✓**
- Imports working: **✓** Runner executed via `PYTHONPATH`.
- Commits scoped: **✓** Implementation commit limited to AST/parser/resolver/docs/tests; tracking update separate.
- Side effects: **✓** No unrelated edits beyond stage scope.

### Stage Tracking
- `mill_ui_refactor.md`: **✓** Stage 19 marked `done` with commit `499c34b`; current stage advanced to `S20`.
- Tag `refactor_v2_S19_CENTERLINE_SPLINES`: **✓** points to the implementation commit.

### Equivalence Verification (Foundation)
- Splines are additive, lowering exclusively to polylines so downstream CAM logic remains unchanged. Studio Mode guarantees (centerline interpretation, permissive validation) are enforced via documentation and non-blocking resolver behavior.

### Code Quality
- Implementation is clear and well-documented; Catmull-Rom sampling function encapsulated and unit-tested via acceptance suite.
- Tests provide deterministic checks for geometry + RemovalIntent integration.
- Documentation includes FAQ, policy, and next-step roadmap.

### Issues Found
None.

### Recommendation
- [x] ✅ Approve - Proceed to next stage
- [ ] ⚠️ Conditional Approval - Proceed with noted issues to address
- [ ] ❌ Reject - Requires rework before proceeding

### Additional Notes
- Future enhancements (closed splines, adaptive sampling, Studio Mode warnings) are explicitly deferred, so any new work should build atop the current immediate-lowering approach to keep CAM simple.
