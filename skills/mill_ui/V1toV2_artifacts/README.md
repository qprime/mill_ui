# V1 to V2 Development Artifacts

This folder contains historical documents from the mill_ui v1 → v2 migration/promotion process.

## Contents

- **V2_PROMOTION_PLAN.md** - Step-by-step promotion plan with verification checkpoints
- **V2_ARCHIVE_README.md** - Original v2/ directory README
- **mill_ui_refactor.md** - Refactor planning and architecture notes
- **STAGE_6_REVIEW_RESPONSE.md** - Stage 6 code review response
- **reviews/** - Codex AI code reviews (Stages 1, 15-19)

## Historical Context

These documents chronicle the development process from:
- v1 architecture (JSON ingestion → CAD hints → CAM planner → G-code)
- v2 architecture (PML/JSON → LayoutAST → RemovalIntent IR → CAM planner → G-code)

The promotion process involved:
1. Building v2 as parallel implementation in `v2/` directory
2. Validating v2 functionality through staged development (S1-S19)
3. Promoting v2 to canonical mill_ui (flattening directory structure)
4. Removing backward compatibility code (compositions, introspect, core utilities)
5. Refactoring remaining v1 CAM backend integration

## Preservation

These artifacts are preserved in git tag `v1_v2_artifacts` before final cleanup.
The v1 codebase is preserved in tag `v1_final`.
The v2 pre-promotion state is preserved in tag `v2_pre_promotion`.
