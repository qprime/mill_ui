# Mill UI v2 Refactor

**Status**: In progress - do not use

This namespace contains the v2 refactor implementing the AI-first compositional architecture described in [../mill_ui_refactor.md](../mill_ui_refactor.md).

## Implementation Status

The refactor follows an 11-stage plan with explicit acceptance criteria. See the refactor document for current stage progress.

## Legacy Code

v1 code remains in parent directory (`skills/mill_ui/`) and is frozen via git tag `mill_ui_v1_frozen`. v1 will be used for:
- Reference implementation during v2 development
- Adapter validation (byte-identical G-code matching in Stage 6)
- Semantic equivalence verification (geometry validation in Stage 10)

## For Developers

Do not import from this namespace until the refactor is complete and marked stable.
