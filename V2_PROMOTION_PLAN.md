# mill_ui v2 Promotion Plan

## Purpose

Promote v2 architecture to canonical mill_ui codebase. v2 is a complete rewrite with clean IR layer (RemovalIntent), compositional AST, and PML frontend. v1 CAM backend (planner, gcode) is retained as it works correctly and doesn't need replacement.

## Current State

```
mill_ui/
├── api/          [DELETE - unused by v2]
├── apps/         [DELETE - unused by v2]
├── cad/
│   ├── export/   [KEEP - STEP/STL/SVG export for future v2 integration]
│   └── (rest)    [DELETE - unused by v2]
├── cam/          [KEEP - v2 uses this backend]
├── compositions/ [KEEP - v2 introspect uses resolve_templates]
├── core/         [KEEP - v2 tests use Config]
├── io/           [DELETE - unused by v2]
├── recipes/      [DELETE - unused by v2]
├── tests/        [DELETE - replaced by v2 tests]
└── v2/           [PROMOTE to top level]
```

## Promotion Steps

### Step 1: Pre-flight Check
**Goal**: Verify all v2 tests pass before promotion

```bash
# Run all v2 test suites
PYTHONPATH=/home/squinlan/cliff_ai python3 -m skills.mill_ui.v2.tests.run_edge_tests
PYTHONPATH=/home/squinlan/cliff_ai python3 -m skills.mill_ui.v2.tests.run_spline_tests
PYTHONPATH=/home/squinlan/cliff_ai python3 -m skills.mill_ui.v2.tests.run_keepout_tests
PYTHONPATH=/home/squinlan/cliff_ai python3 -m skills.mill_ui.v2.tests.run_compositional_pml_tests
PYTHONPATH=/home/squinlan/cliff_ai python3 -m skills.mill_ui.v2.tests.run_resolution_tests
PYTHONPATH=/home/squinlan/cliff_ai python3 -m skills.mill_ui.v2.tests.run_gcode_equivalence_tests
PYTHONPATH=/home/squinlan/cliff_ai python3 -m skills.mill_ui.v2.tests.run_shaker_v2_end_to_end
```

**Verification**: All tests must pass. If any fail, stop and fix.

**Checkpoint**:
- [ ] All v2 tests passing

---

### Step 2: Create Safety Tags
**Goal**: Tag current state for rollback if needed

```bash
git tag v1_final          # Last commit with v1 as canonical
git tag v2_pre_promotion  # State before promotion
```

**Verification**: Tags created successfully

**Checkpoint**:
- [ ] Tags created
- [ ] `git tag | grep -E "(v1_final|v2_pre_promotion)"` shows both tags

---

### Step 3: Move v2 Directories to Top Level
**Goal**: Flatten v2 structure (no deletions yet)

```bash
# Move v2 modules up
mv v2/adapters ./
mv v2/ast ./
mv v2/cli ./
mv v2/docs ./
mv v2/export ./
mv v2/ir ./
mv v2/pml ./
mv v2/resolution ./
mv v2/templates ./
mv v2/validation ./

# Move v2 tests (rename to avoid conflict with v1 tests/)
mv v2/tests ./tests_v2

# Keep v2 directory metadata
mv v2/README.md ./V2_ARCHIVE_README.md
mv v2/STAGE_6_REVIEW_RESPONSE.md ./docs/

# Remove empty v2 directory
rmdir v2
```

**Verification**: Check directory structure

```bash
ls -d adapters ast cli docs export ir pml resolution templates validation tests_v2
```

**Checkpoint**:
- [ ] All v2 directories moved to top level
- [ ] v2/ directory removed
- [ ] No errors from mv commands

---

### Step 4: Fix v2 Internal Imports
**Goal**: Update all `skills.mill_ui.v2.X` → `skills.mill_ui.X`

```bash
# Fix imports in moved modules
find adapters ast cli export ir pml resolution validation templates tests_v2 -name "*.py" -type f -exec sed -i 's/from skills\.mill_ui\.v2\./from skills.mill_ui./g' {} \;
find adapters ast cli export ir pml resolution validation templates tests_v2 -name "*.py" -type f -exec sed -i 's/import skills\.mill_ui\.v2\./import skills.mill_ui./g' {} \;
```

**Verification**: Check no v2 imports remain

```bash
rg "from skills\.mill_ui\.v2\." adapters/ ast/ cli/ pml/ ir/ resolution/ export/ validation/ templates/ tests_v2/ --type py || echo "✓ No v2 imports found"
```

**Checkpoint**:
- [ ] All imports updated
- [ ] Grep shows no v2 imports in moved code

---

### Step 5: Test v2 Functionality After Import Changes
**Goal**: Verify v2 still works with new import paths

```bash
# Run core v2 test suites with new paths
PYTHONPATH=/home/squinlan/cliff_ai python3 -m skills.mill_ui.tests_v2.run_edge_tests
PYTHONPATH=/home/squinlan/cliff_ai python3 -m skills.mill_ui.tests_v2.run_spline_tests
PYTHONPATH=/home/squinlan/cliff_ai python3 -m skills.mill_ui.tests_v2.run_keepout_tests
PYTHONPATH=/home/squinlan/cliff_ai python3 -m skills.mill_ui.tests_v2.run_compositional_pml_tests

# Test CLI tools still work
PYTHONPATH=/home/squinlan/cliff_ai python3 -m skills.mill_ui.cli.parse_compositional_pml --help
PYTHONPATH=/home/squinlan/cliff_ai python3 -m skills.mill_ui.cli.convert_layout --help
```

**Verification**: All tests pass, CLI tools show help

**Checkpoint**:
- [ ] Edge tests pass
- [ ] Spline tests pass
- [ ] Keepout tests pass
- [ ] Compositional PML tests pass
- [ ] CLI help commands work

---

### Step 6: Delete Unused v1 Code
**Goal**: Remove v1 code that v2 doesn't use

```bash
# Delete unused v1 modules
rm -rf api/
rm -rf apps/
rm -rf io/
rm -rf recipes/
rm -rf tests/

# Delete unused parts of cad/ (keep only export/)
rm -rf cad/ingest/
rm -rf cad/layout/
rm -rf cad/native/
rm -f cad/compose.py
rm -f cad/geom_parse.py
rm -f cad/primitives.py
rm -f cad/shape.py
rm -f cad/transforms.py

# Keep cam/, compositions/, core/, cad/export/ (v2 dependencies and future integration)
```

**Verification**: Check remaining structure

```bash
ls -d cad cam compositions core adapters ast cli pml ir resolution export validation templates tests_v2
```

**Checkpoint**:
- [ ] api/ deleted
- [ ] apps/ deleted
- [ ] io/ deleted
- [ ] recipes/ deleted
- [ ] tests/ deleted
- [ ] cad/ingest/, cad/layout/, cad/native/ deleted
- [ ] cad/*.py files deleted (except __init__.py)
- [ ] cad/export/ still present
- [ ] cam/ still present
- [ ] compositions/ still present
- [ ] core/ still present

---

### Step 7: Rename tests_v2 to tests
**Goal**: Make v2 tests the canonical test suite

```bash
mv tests_v2 tests
```

**Verification**: Tests directory exists

```bash
ls -d tests/
```

**Checkpoint**:
- [ ] tests/ directory exists
- [ ] tests_v2/ no longer exists

---

### Step 8: Final Test Run
**Goal**: Verify complete system works after promotion

```bash
# Run all test suites
PYTHONPATH=/home/squinlan/cliff_ai python3 -m skills.mill_ui.tests.run_edge_tests
PYTHONPATH=/home/squinlan/cliff_ai python3 -m skills.mill_ui.tests.run_spline_tests
PYTHONPATH=/home/squinlan/cliff_ai python3 -m skills.mill_ui.tests.run_keepout_tests
PYTHONPATH=/home/squinlan/cliff_ai python3 -m skills.mill_ui.tests.run_compositional_pml_tests
PYTHONPATH=/home/squinlan/cliff_ai python3 -m skills.mill_ui.tests.run_resolution_tests
PYTHONPATH=/home/squinlan/cliff_ai python3 -m skills.mill_ui.tests.run_gcode_equivalence_tests
PYTHONPATH=/home/squinlan/cliff_ai python3 -m skills.mill_ui.tests.run_shaker_v2_end_to_end

# Test all CLI tools
echo "sheet 400mm 400mm 19mm" | PYTHONPATH=/home/squinlan/cliff_ai python3 -m skills.mill_ui.cli.parse_compositional_pml
```

**Verification**: All tests pass, CLI accepts input

**Checkpoint**:
- [ ] All test suites pass
- [ ] CLI tools functional
- [ ] No import errors
- [ ] No missing module errors

---

### Step 9: Update README and Documentation
**Goal**: Document new structure

Update `README.md` to reflect v2 structure:
- Remove references to v1 api/, apps/, cad/
- Document v2 CLI tools (parse_compositional_pml, convert_layout, introspect)
- Update AI reading order for v2 modules

**Checkpoint**:
- [ ] README.md updated
- [ ] V2_PROMOTION_PLAN.md exists (this file)

---

### Step 10: Commit and Tag
**Goal**: Preserve promotion in git history

```bash
git add -A
git commit -m "[V2_PROMOTION] Promote v2 to canonical mill_ui

- Move all v2 modules to top level
- Delete unused v1 code (api, apps, io, recipes, old tests)
- Keep v1 backend modules (cam/, cad/, compositions/, core/)
- Fix all imports (skills.mill_ui.v2.X → skills.mill_ui.X)
- All tests passing

v2 is now canonical mill_ui architecture:
- PML/JSON → AST → RemovalIntent IR → CAM planner → G-code
- Clean separation of concerns
- Compositional layouts
- Extensible, testable, AI-friendly

Retained v1 modules for integration:
- cam/ (planner, gcode) - v2 uses this
- cad/export/ (STEP/STL/SVG export) - available for future v2 integration
- compositions/ (template resolver) - v2 uses this
- core/ (Config) - v2 uses this

v1 preserved in tags: v1_final, v2_pre_promotion
"

git tag v2_promoted
```

**Checkpoint**:
- [ ] Commit successful
- [ ] Tag v2_promoted created

---

## Final Structure

```
mill_ui/
├── adapters/       # v2: RemovalIntent ↔ planner adapters
├── ast/            # v2: LayoutAST, CompositionalLayoutAST
├── cad/
│   └── export/     # v1: STEP/STL/SVG export - retained for future v2 integration
├── cam/            # v1: CAM planner, gcode (retained)
├── cli/            # v2: parse_compositional_pml, convert_layout, introspect
├── compositions/   # v1: template resolver (retained, used by v2)
├── core/           # v1: Config (retained, used by v2 tests)
├── docs/           # v2: architecture docs
├── export/         # v2: SVG removal visualization (debug)
├── ir/             # v2: RemovalIntent IR
├── pml/            # v2: PML parser/formatter
├── resolution/     # v2: Layout resolver
├── templates/      # v2: ShakerV2, etc.
├── tests/          # v2: All test suites
├── validation/     # v2: Removal checks
└── README.md       # Updated for v2
```

## Rollback Plan

If anything fails:

```bash
git reset --hard v2_pre_promotion
git tag -d v2_promoted  # if created
```

All work preserved in git history.

## Success Criteria

- [x] All v2 tests passing (pre-promotion)
- [ ] All v2 tests passing (post-import-fix)
- [ ] All v2 tests passing (post-promotion)
- [ ] CLI tools functional
- [ ] No v2/ directory
- [ ] Unused v1 code deleted (api, apps, io, recipes)
- [ ] Useful v1 code retained (cam, cad/export, compositions, core)
- [ ] Clean directory structure
- [ ] Git commit + tag created
