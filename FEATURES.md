<!-- spec-style -->
# Feature Development Tracker

As-Of Date: 2026-01-19
Document Type: Feature Status Registry

---

## Status Legend

| Symbol | Status | Definition |
|--------|--------|------------|
| 🔵 | Design | Feature is being specified. |
| 🟡 | Implemented | Code written, tests pass. |
| 🟢 | Reviewed | Codex reviewed and approved. |
| ⚪ | Not Started | Pending work. |

---

## Feature Registry

| ID | Name | Status | Layer | Priority |
|----|------|--------|-------|----------|
| F001 | Pocket Wall Cleanup Pass | 🟡 Implemented | Planner Strategy | High |
| F002 | Blueprint Proof Drawing Export | ✅ Complete | Export | High |
| F003 | STL Export for Visual Validation | 🟢 Reviewed | Export | Medium |
| F004 | Profile Cuts with Holding Tabs | 🟢 Reviewed | Full Stack | High |
| F005 | Sheet Nesting (Bin-Packing) | 🟢 Reviewed | Pre-Pipeline | High |
| F006 | Domain/Generator System | 🟢 Reviewed | Design Composition | High |

---

## F001: Pocket Wall Cleanup Pass

**Status:** 🟡 Implemented
**Layer:** Planner Strategy (CAM execution detail)
**Implementation Date:** 2025-12-19

### Problem

Raster toolpaths create scalloped walls perpendicular to raster direction.

### Solution

Full-perimeter cleanup pass after rough pocket raster.

### Configuration

| Field | Location | Default |
|-------|----------|---------|
| pocket_finish_perimeter | cam/config.py:32 | True |

### Files Modified

- cam/config.py - Added configuration field.
- cam/path/strategies.py:241-318 - Modified pocket_then_finish_profile().
- cam/planner/passes/pocket.py:86 - Wired config to strategy.
- tests/test_pocket_cleanup.py - New test suite.

### Acceptance Criteria

- [x] Perimeter cleanup for pockets implemented.
- [x] Tests verify finish pass generation.
- [x] Tests verify finish pass skipped when disabled.
- [x] No changes to RemovalIntent geometry semantics.
- [ ] Codex review passes.

---

## F002: Blueprint Proof Drawing Export (SVG + PDF)

**Status:** ✅ Complete (Parts A-E)
**Layer:** Export / Presentation
**Implementation Date:** 2025-12-19

### Problem

Users need visual proof of design before cutting expensive material.

### Solution

Intent-derived blueprint-style SVG with semantic layers, dimensions, and theme support.

### Semantic Layers

SHEET_OUTLINE, PROFILE_CUTS, POCKET_REGIONS, ENGRAVE_PATHS, HOLES, CONSTRUCTION, DIMENSIONS, NOTES, TITLE_BLOCK, LEGEND.

### Themes

| Theme | Background | Foreground | Use Case |
|-------|------------|------------|----------|
| dark | #1a1a1a | #e8e8e8 | Screen viewing |
| print | #ffffff | #000000 | Paper printing |

### Files Created

- export/blueprint_svg.py - Main SVG renderer.
- export/dimensions.py - Dimension placement logic.
- export/blueprint_pdf.py - PDF conversion.
- cli/export_blueprint.py - CLI entry point.
- tests/test_blueprint_export.py - Test suite.

### CLI Usage

```bash
python -m cli.export_blueprint --input door.pml --theme dark --format both --out out/
```

### Acceptance Criteria

- [x] Part A: SVG scaffolding.
- [x] Part B: Dimension engine.
- [x] Part C: Title block, legend, notes.
- [x] Part D: PDF export and CLI.
- [x] Part E: Tests.
- [ ] Codex review.

---

## F003: STL Export for Visual Validation

**Status:** 🟢 Reviewed (Production)
**Layer:** Export / Validation
**Implementation Date:** 2026-01-14

### Problem

Users need 3D visual validation before machining.

### Solution

Boolean CSG approach using trimesh and shapely.

### Files Created

- cad/export/stl.py (335 lines) - Core STL exporter.
- adapters/ast_to_cad.py (51 lines) - Adapter layer.
- cli/export_cad.py (153 lines) - CLI tool.
- tests/test_cad_export.py (300 lines) - Test suite.

### Supported Features

| Geometry | Feature |
|----------|---------|
| Rectangle, Circle, Polyline | profile, pocket, hole, engrave |

### CLI Usage

```bash
python -m cli.export_cad --input door.pml --kerf 3.175 --quality high --out preview/
```

### Acceptance Criteria

- [x] Shaker door exports to STL.
- [x] Pockets show correct depth.
- [x] Kerf compensation works.
- [x] All 8 unit tests pass.

---

## F004: Profile Cuts with Holding Tabs

**Status:** 🟢 Reviewed (Production)
**Layer:** Full Stack (PML → AST → IR → Planner)
**Implementation Date:** 2026-01-12

### Problem

Cut pieces can shift or fall once profile cut completes.

### Solution

Tabs leave small uncut sections that keep parts secured.

### Syntax

```pml
rect cutout at 300mm,200mm size 400mm,250mm profile through outside tabs 4 height 3mm width 12mm
```

Required: `tabs <count> height <height>mm`. Optional: `width <width>mm`.

### Files Modified

- layout_ast/layout.py:43-46 - Feature dataclass extension.
- pml/parser.py:275-319 - Tab syntax parsing.
- pml/formatter.py:124-128 - Tab formatting.
- adapters/ast_to_removal.py:111-117 - AST → IR conversion.

### Files Created

- tests/test_tabs.py - 8 test cases.
- docs/recipes/15_profile_with_tabs/ - Recipe documentation.

### Tab Recommendations

| Part Size | Tabs | Material Thickness | Tab Height |
|-----------|------|-------------------|------------|
| < 200mm | 3 | 12-19mm | 2-4mm |
| 200-400mm | 4 | 6-12mm | 1-3mm |
| > 400mm | 6+ | > 19mm | 4-6mm |

### Acceptance Criteria

- [x] PML syntax parsing.
- [x] AST construction.
- [x] RemovalIntent conversion.
- [x] 8/8 tests passing.
- [x] Recipe documentation.

---

## F005: Sheet Nesting (Bin-Packing)

**Status:** 🟢 Reviewed (Production)
**Layer:** Pre-Pipeline
**Implementation Date:** 2026-01-13

### Problem

Manual layout for production runs is time-consuming and suboptimal.

### Solution

Automatic bin-packing with two algorithms.

### Algorithms

| Algorithm | Utilization | Speed |
|-----------|-------------|-------|
| Guillotine | ~62% | Fast |
| MaxRects | ~83% | Slower |

### Syntax

```pml
nest maxrects
    sheet 1232mm 1245mm 19mm
    kerf 6.35mm
    parts
        door 457mm 597mm x20
            template Shaker
```

### Files Created

- nesting/guillotine.py - Guillotine algorithm.
- nesting/maxrects.py - MaxRects algorithm.
- nesting/types.py - PartSpec, SheetSpec, NestingResult.
- nesting/api.py - nest_parts(), nest_and_generate().
- pml/nest_parser.py - .nest file parser.
- cli/nest.py - CLI tool.

### CLI Usage

```bash
python -m cli.nest job.nest -o output/ --export-stl --export-svg
```

### Acceptance Criteria

- [x] Parse .nest format.
- [x] Guillotine algorithm.
- [x] MaxRects algorithm.
- [x] Multi-sheet support.
- [x] Template expansion.
- [x] CLI tool.
- [x] Recipe documentation (16, 17, 18).

---

## F006: Domain/Generator System

**Status:** 🟢 Reviewed (Production)
**Layer:** Design Composition
**Implementation Date:** 2026-01-17

### Problem

Templates create structural problems at scale: explosion, redraw labor, rigidity.

### Solution

Math-based composition separating *where* (domains) from *what* (generators).

### Domain Operations

| Operation | Description |
|-----------|-------------|
| inset(distance) | Contract boundary inward. |
| offset(distance) | Expand boundary outward. |
| subtract(other) | Remove overlapping region. |
| intersect(other) | Keep only overlapping region. |

### Generators

| Type | Examples |
|------|----------|
| Area | flat_pocket_generator, wave_generator, grid_generator |
| Loop | profile_generator, bead_generator |
| SVG | svg_stamp_generator |

### Files Created

- domains/domain.py (~450 lines)
- domains/transforms.py (~200 lines)
- generators/base.py (~400 lines)
- generators/area/ - flat.py, wave.py, grid.py
- generators/loop/ - profile.py, bead.py
- generators/svg/ (~800 lines)

### Performance

| Operation | Threshold | Actual |
|-----------|-----------|--------|
| Rectangle construction | < 1ms | ~0.07ms |
| Inset operation | < 5ms | ~0.08ms |
| Full pipeline | < 200ms | ~0.18ms |

### Acceptance Criteria

- [x] Domain type with operations.
- [x] Coordinate transforms.
- [x] All generators output valid Items.
- [x] Determinism verified.
- [x] Performance benchmarks.
- [x] Documentation updated.

---

## Feature Template

```markdown
## FXXX: Feature Name

**Status:** 🔵 Design | 🟡 Implemented | 🟢 Reviewed
**Layer:** IR | Planner | Parser | etc.
**Priority:** High | Medium | Low

### Problem
[Description]

### Solution
[Design]

### Files Modified
[List]

### Acceptance Criteria
- [ ] Criterion 1
- [ ] Criterion 2
```
