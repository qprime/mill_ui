# Feature Development Tracker

This document tracks new features added to mill_ui, their design, implementation status, and review status.

## Feature Status Legend

- 🔵 **Design** - Feature is being designed/specified
- 🟡 **Implemented** - Code is written and tests pass
- 🟢 **Reviewed** - Codex has reviewed and approved
- ⚪ **Not Started** - Pending work

---

## F001: Pocket Wall Cleanup Pass

**Status:** 🟡 Implemented

**Priority:** High

**Architecture Layer:** Planner Strategy (CAM execution detail, not IR semantic)

### Problem Statement

When pocketing with raster toolpaths, walls perpendicular to the raster direction get scalloped due to the round bit profile, while walls parallel to the raster direction are smooth. We need a cleanup pass that efficiently finishes only the scalloped walls without changing nominal geometry.

**Visual:**
```
Raster direction: X (horizontal) →

╔═════════════╗
║ ∩∩∩∩∩∩∩∩∩∩∩ ║  ← Top wall: scalloped (perpendicular to raster)
║             ║  ← Side walls: smooth (parallel to raster)
║ ∩∩∩∩∩∩∩∩∩∩∩ ║  ← Bottom wall: scalloped (perpendicular to raster)
╚═════════════╝
```

### Design

**Pipeline Location:**
`PML/JSON → LayoutAST → RemovalIntent → planner strategies → **[NEW: wall cleanup]** → moves → gcode`

**Key Principles:**
1. **No IR changes** - This is a toolpath optimization, not semantic intent
2. **Selective finishing** - Only clean walls likely to be scalloped (perpendicular to raster)
3. **Configurable** - Allow override to finish all walls, or disable entirely

**Implementation Points:**

1. **Intent Hints (Optional Configuration):**
   - Add to `RemovalIntent.metadata` or new `PocketStrategy` field:
     - `finish_policy`: `"perp_walls"` (default) | `"all_walls"` | `"none"`
     - `finish_allowance_mm`: Optional finish pass allowance (default: 0.0)

2. **Raster Strategy Extension:**
   - Track raster direction vector (X or Y axis)
   - Analyze pocket boundary segments
   - Select segments where `abs(dot(segment_tangent_unit, raster_dir_unit)) < cos(60°)`
   - Skip segments shorter than `2 × tool_diameter`

3. **Finish Pass Generation:**
   - Generate contour moves along selected segments
   - Execute at final depth (or per depth band if multi-pass)
   - Respect finish_allowance_mm if specified

4. **Segment Selection Algorithm:**
   ```python
   def should_finish_segment(segment, raster_dir, tool_diameter):
       """Determine if segment needs finish pass."""
       # Calculate segment direction
       tangent = normalize(segment.end - segment.start)

       # Perpendicularity check (< 60° from perpendicular)
       perpendicularity = abs(dot(tangent, raster_dir))
       threshold = cos(60°)  # ~0.5

       # Length check
       length = segment.length()
       min_length = 2 * tool_diameter

       return perpendicularity < threshold and length >= min_length
   ```

### Test Plan

**Test Cases:**

1. **test_pocket_cleanup_raster_x_direction**
   - Rectangular pocket with raster direction = X
   - Assert: Left and right walls (perpendicular) get finish passes
   - Assert: Top and bottom walls (parallel) do NOT get finish passes

2. **test_pocket_cleanup_raster_y_direction**
   - Rectangular pocket with raster direction = Y
   - Assert: Top and bottom walls (perpendicular) get finish passes
   - Assert: Left and right walls (parallel) do NOT get finish passes

3. **test_pocket_cleanup_polygon**
   - Irregular polygon pocket
   - Assert: Only segments perpendicular to raster get finished
   - Assert: Short segments are skipped

4. **test_pocket_cleanup_all_walls_policy**
   - Set `finish_policy = "all_walls"`
   - Assert: All boundary segments get finish passes

5. **test_pocket_cleanup_none_policy**
   - Set `finish_policy = "none"`
   - Assert: No finish passes generated

6. **test_pocket_cleanup_with_allowance**
   - Set `finish_allowance_mm = 0.1`
   - Assert: Finish passes are offset inward by allowance

### Files to Modify

- `cam/path/strategies.py` - Add cleanup pass logic to raster strategy
- `cam/ops/pocket.py` - Integrate cleanup into pocket operation
- `ir/removal_intent.py` - Add optional metadata fields (or keep in planner config)
- `tests/test_pocket_cleanup.py` - New test file
- `FEATURES.md` - This document

### Acceptance Criteria

- [x] Code implements perimeter cleanup for pockets (simplified to full perimeter)
- [x] Tests verify finish pass generation when enabled
- [x] Tests verify finish pass skipped when disabled
- [x] Tests verify cleanup offset parameter works correctly
- [x] No changes to RemovalIntent geometry semantics
- [ ] Codex review passes (pending)

### Implementation Notes

**Implementation Date:** 2025-12-19

**Actual Implementation:**
The feature was implemented as a simpler full-perimeter cleanup pass instead of selective perpendicular-wall detection. This provides a complete solution for scalloping cleanup while maintaining architectural simplicity.

**Changes Made:**

1. **[cam/config.py](cam/config.py:32)** - Added `pocket_finish_perimeter: bool = True` configuration field
   - Default: True (enabled by default as requested)
   - Normalizer: `_normalise_bool()` for flexible config parsing
   - Environment variable: `CAM_POCKET_FINISH_PERIMETER`

2. **[cam/path/strategies.py](cam/path/strategies.py:241-318)** - Modified `pocket_then_finish_profile()`
   - Added `finish_perimeter: bool = True` parameter
   - When `finish_perimeter=True`:
     - Shrinks rough pocket by `(tool_radius + cleanup_offset_mm)`
     - Generates finish profile pass at final depth on full perimeter
   - When `finish_perimeter=False`:
     - Cuts pocket raster to full boundary
     - No finish pass generated

3. **[cam/planner/passes/pocket.py](cam/planner/passes/pocket.py:86)** - Wired config to strategy
   - Passes `config.pocket_finish_perimeter` to strategy function

4. **[tests/test_pocket_cleanup.py](tests/test_pocket_cleanup.py)** - New test suite
   - 4 test cases with mocked native backend
   - Validates finish pass generation and skipping logic
   - Validates cleanup offset parameter handling

**Design Simplifications:**
- **Full perimeter cleanup** instead of selective perpendicular walls
  - Rationale: Simpler implementation, ensures all walls are clean
  - Future optimization: Can add selective cleanup in follow-on feature
- **No raster direction detection** in v1
  - Rationale: Full perimeter cleanup makes direction detection unnecessary
- **Planner-level config only** (not in RemovalIntent metadata)
  - Rationale: This is execution/finish-quality, not design intent
  - Config placement: `cam.config.Config.pocket_finish_perimeter`

**Test Results:**
- All 4 new unit tests passing (with mocked native backend for fast CI)
- All 35 existing tests passing
- **Native backend verification**: Tested end-to-end with compiled C++ backend
  - With `finish_perimeter=True`: Generates rough pocket + finish profile pass
  - With `finish_perimeter=False`: Generates full pocket raster only
  - Verified correct comment markers in move lists
  - Confirmed finish pass behavior (smaller rough area + perimeter cleanup)
- No breaking changes to existing functionality

---

## Feature Template (for future features)

```markdown
## FXXX: Feature Name

**Status:** 🔵 Design | 🟡 Implemented | 🟢 Reviewed

**Priority:** High | Medium | Low

**Architecture Layer:** IR | Planner | Parser | etc.

### Problem Statement
[Description]

### Design
[Design details]

### Test Plan
[Test cases]

### Files to Modify
[List of files]

### Acceptance Criteria
- [ ] Criterion 1
- [ ] Criterion 2

### Implementation Notes
[Notes during implementation]
```

---

## F002: Blueprint Proof Drawing Export (SVG + PDF)

**Status:** ✅ Complete (Parts A-E) - Awaiting codex review

**Priority:** High

**Architecture Layer:** Export / Presentation (post-IR, pre-CAM)

### Problem Statement

Before cutting expensive material on a CNC machine, users need a clear visual proof of their design that shows:
- Accurate geometry from RemovalIntent semantics
- Key dimensions and measurements
- Feature labels (profiles, pockets, holes, engraves)
- Depth information for non-through features
- Sheet boundaries and part placement

**Current state:** Existing export modules are incomplete/broken:
- `export/svg_removal.py`: Basic SVG renderer (to be replaced)
- `cad/export/stl.py`: 1-line stub (non-functional)
- `cad/export/step.py`: Broken (missing cad.native module)
- `cad/export/svg.py`, `cad/export/svg_dims.py`: Legacy/unknown status

**Goal:** A deterministic, intent-derived "blueprint-style" inspection drawing that provides confidence before machining, with no manual tweaking required.

### Design

**Pipeline Location:**
```
PML/JSON → LayoutAST → RemovalIntent → [NEW: Blueprint Export] → SVG/PDF
                                     ↘ CAM Planner → G-code
```

**Key Principles:**
1. **Intent-derived** - Render from LayoutAST/RemovalIntent, NOT toolpaths
2. **Deterministic** - Same input always produces same output (stable placement)
3. **Validation focus** - First line of proof before cutting
4. **Theme support** - Dark (screen) and print (paper) themes
5. **No manual tweaking** - Automated dimension and label placement

### Output Specifications

#### 1. File Formats
- **Primary:** SVG (deterministic, screen-friendly, supports themes)
- **Secondary:** PDF (print/share, derived from SVG via CairoSVG)

#### 2. Semantic Layers (SVG groups)
- `SHEET_OUTLINE` - Sheet boundary rectangle
- `PROFILE_CUTS` - Through-cut profile paths
- `POCKET_REGIONS` - Pocket boundaries with optional translucent fill
- `ENGRAVE_PATHS` - Engraving lines/polylines (sampled if splines)
- `HOLES` - Hole centers with diameter labels
- `CONSTRUCTION` - Optional faint frame/inset bounds
- `DIMENSIONS` - Dimension lines on outer "rails"
- `NOTES` - Text block (units, depths list, feature counts)
- `TITLE_BLOCK` - Project metadata (name, timestamp, units)
- `LEGEND` - Layer meaning key

#### 3. Dimensioning Strategy (Rails)

**Goal:** Avoid text inside part areas; place dimensions on outer "rails"

```
┌─────────────────────────────────────────────────────────┐
│  ┌──── 400mm ────┐                                      │
│  │                │                                      │
│  │                │                                      │
│  │     PART       │  600mm                               │
│  │                │                                      │
│  │                │                                      │
│  └────────────────┘                                      │
└─────────────────────────────────────────────────────────┘
```

**Rails placement:**
- **Top rail:** Overall width + key X distances
- **Right rail:** Overall height + key Y distances
- **Collision avoidance:** Simple bbox-based check; stack labels if overlap

**Minimum required dimensions (v1):**
- Sheet overall width/height
- Each part outline overall width/height
- Frame width/inset amounts (if present in AST)
- Hole center-to-center spacing (X and Y for patterns)
- Grid pitch and counts (if grid/split used)

**Depth annotations:**
Place in NOTES block, NOT scattered on geometry:
- Pocket depths present in design
- Engrave depths present
- Hole depths (if not through)

#### 4. Theme System

**Theme: "dark" (default)**
- Background: Very dark gray (`#1a1a1a`)
- Foreground: Off-white (`#e8e8e8`)
- Pockets: Light translucent fill (`rgba(100,150,200,0.2)`) + outline
- Engraves: Dashed lines, dimmed
- Dimensions: Muted accent color (`#5ab9ea` cyan-ish)
- Grid/construction: Very faint gray (`#333333`)

**Theme: "print"**
- Background: White (`#ffffff`)
- Foreground: Black (`#000000`)
- Pockets: Light gray fill (`#f0f0f0`) or no fill
- Engraves: Dashed black lines
- Dimensions: Dark gray (`#333333`)
- High contrast for paper printing

**Implementation:** Simple CSS style maps; themes affect only styling, not geometry.

### Implementation Plan

**Parts A-E with commits per part:**

#### Part A: Export Module Scaffolding + SVG Renderer
**Files to create:**
- `export/blueprint_svg.py` - Main SVG renderer
  - `render_blueprint_svg(layout_ast, removal_intents, theme="dark") -> str`
  - Produces SVG with proper layers/groups (`<g id="SHEET_OUTLINE">`, etc.)
  - Minimal legend/notes block area
  - No dimensions yet (or only sheet size)

**Files to modify/replace:**
- `export/svg_removal.py` - REPLACE (permission granted)
- `export/__init__.py` - Update imports

**Acceptance criteria:**
- SVG output contains all semantic layer groups
- Sheet boundary renders correctly
- Basic profiles/pockets render (no dimensions)
- Theme parameter toggles CSS/colors

**Commit:** `feat(F002-A): Blueprint SVG scaffolding with semantic layers`

---

#### Part B: Dimension Engine (Rails)
**Files to create:**
- `export/dimensions.py` - Dimension placement logic
  - `compute_bounding_boxes(ast, intents) -> dict[str, Bounds2D]`
  - `place_dimension_on_rail(rail_type, value, position, collision_checker) -> DimPlacement`
  - `render_dimension_line(start, end, value, arrowheads=True) -> SVGElement`
  - Simple bbox-based collision avoidance

**Files to modify:**
- `export/blueprint_svg.py` - Hook dimension engine into rendering

**Acceptance criteria:**
- Sheet width/height dimensions appear on rails
- Part outline dimensions appear
- Dimension lines have arrowheads
- Text positioned deterministically
- Collision avoidance prevents overlaps (or stacks labels)

**Commit:** `feat(F002-B): Dimension engine with rail placement`

---

#### Part C: Polish (Line Weights, Fonts, Title Block)
**Files to modify:**
- `export/blueprint_svg.py` - Add title block, legend, notes depth list
  - Title block section (project name if available, timestamp optional, units)
  - Legend showing layer meaning
  - NOTES block with depth list and feature counts

**Acceptance criteria:**
- Title block renders with correct metadata
- Legend shows layer colors/meanings
- NOTES block contains depth information
- Line weights differentiated (profiles thicker than construction)
- Fonts readable and consistent

**Commit:** `feat(F002-C): Blueprint polish - title block, legend, notes`

---

#### Part D: PDF Export
**Files to create:**
- `export/blueprint_pdf.py` - PDF conversion
  - `svg_to_pdf(svg_string, output_path) -> None`
  - Uses CairoSVG if available; graceful failure with clear error if not
- `cli/export_blueprint.py` - CLI entry point
  - Flags: `--theme dark|print`, `--format svg|pdf|both`, `--input`, `--out`
  - Reads PML or JSON, runs full pipeline: parse → resolve → IR → blueprint

**Files to modify:**
- `requirements.txt` or `requirements-dev.txt` - Add `cairosvg` as optional dependency

**Acceptance criteria:**
- CLI accepts PML or JSON input
- CLI produces SVG output (always works)
- CLI produces PDF output (if CairoSVG installed)
- Clear error message if PDF requested but dependency missing
- Both theme options work
- Output filenames follow pattern: `{name}.blueprint.{theme}.{format}`

**Commit:** `feat(F002-D): PDF export and CLI for blueprint drawings`

---

#### Part E: Tests
**Files to create:**
- `tests/test_blueprint_export.py` - Test suite
  - `test_svg_output_deterministic()` - Same input → same SVG
  - `test_required_layers_exist()` - All semantic layers present
  - `test_shaker_dimensions()` - Known shaker example has expected dims
  - `test_label_placement_no_overlap()` - Collision avoidance works
  - `test_theme_toggle()` - Dark vs print changes CSS, not geometry
  - `test_pdf_export()` - PDF works if dependency installed; clean error otherwise

**Test data:**
- Shaker door example (from templates/shaker.py)
- Grid layout example (2x2 grid of parts)
- Single profile cut (simplest case)

**Acceptance criteria:**
- All tests pass
- Golden tests compare normalized SVG (strip timestamps)
- Tests cover both themes
- Tests verify dimension presence
- Tests verify layer structure
- PDF tests skip gracefully if CairoSVG not installed

**Commit:** `test(F002-E): Blueprint export test suite with golden files`

---

### Files to Modify/Create Summary

**Files to CREATE:**
- `export/blueprint_svg.py` (Part A)
- `export/dimensions.py` (Part B)
- `export/blueprint_pdf.py` (Part D)
- `cli/export_blueprint.py` (Part D)
- `tests/test_blueprint_export.py` (Part E)
- `tests/fixtures/blueprint_golden/` (Part E - golden test outputs)

**Files to REPLACE (permission granted):**
- `export/svg_removal.py` → replaced by `export/blueprint_svg.py`

**Files to MODIFY:**
- `export/__init__.py` (Part A - update imports)
- `requirements.txt` or `requirements-dev.txt` (Part D - add cairosvg)

**Files to IGNORE/LEAVE UNTOUCHED:**
- `cad/export/stl.py` (stub, not relevant)
- `cad/export/step.py` (broken, not relevant)
- `cad/export/panel_stl.py` (unknown status, leave alone)
- `cad/export/svg.py`, `cad/export/svg_dims.py` (legacy, investigate but don't modify yet)
- All CAM backend files (planner, strategies, native backend - completely untouched)

### Dependencies

**Required:**
- `svgwrite` (optional, can use manual string builder)
- Python stdlib: `dataclasses`, `typing`, `xml.etree.ElementTree` (for SVG manipulation)

**Optional:**
- `cairosvg` - For PDF export (graceful degradation if missing)

**Dependency strategy:**
Add to `requirements-dev.txt` (not core runtime requirement):
```
cairosvg>=2.7.0  # Optional: PDF export for blueprint drawings
```

### Test Plan

**Sample Layouts for Tests:**
1. **Shaker door** (from `templates/shaker.py`)
   - Parameters: `outer_w=400, outer_h=600, stile_w=50, rail_h=50, panel_recess=6`
   - Expected: 2 items (profile + pocket), dimensions for frame width and panel size

2. **Grid layout** (2x2 grid)
   - 4 parts on one sheet
   - Expected: Grid pitch dimensions, part spacing

3. **Simple profile** (single rectangle)
   - 200mm × 150mm profile cut
   - Expected: Basic width/height dimensions, simplest case

**Test Coverage:**
- ✓ SVG output is deterministic (stable element counts, key strings)
- ✓ Required layers exist in SVG (`<g id="SHEET_OUTLINE">`, etc.)
- ✓ Dimensions appear for shaker example (frame width, panel size)
- ✓ Label placement does not overlap (bbox collision check)
- ✓ Theme toggling changes CSS/colors but not geometry paths
- ✓ PDF export works if dependency installed; otherwise clean error

**Golden Test Approach:**
- Generate SVG for known inputs
- Strip timestamps and non-deterministic fields
- Compare normalized SVG to golden file
- Fail if geometry paths change unexpectedly

### Acceptance Criteria

- [x] **Part A**: SVG scaffolding renders semantic layers
- [x] **Part B**: Dimension engine places labels on rails without overlap
- [x] **Part C**: Title block, legend, notes render correctly
- [x] **Part D**: CLI produces SVG/PDF with theme support
- [x] **Part E**: Tests validate determinism and correctness
- [x] **Integration**: Can run `PYTHONPATH=. python3 -m cli.export_blueprint --input door.pml --theme dark --format both --out out/`
- [x] **Output Quality**: Drawing is readable, has key dims, requires no manual adjustment
- [ ] **Codex Review**: Feature reviewed and approved (pending)

### Definition of Done

This feature is complete when:

1. **CLI command works:**
   ```bash
   PYTHONPATH=. python3 -m cli.export_blueprint \
     --input examples/shaker_door.pml \
     --theme dark \
     --format both \
     --out out/
   ```

2. **Outputs produced:**
   - `out/shaker_door.blueprint.dark.svg` (always works)
   - `out/shaker_door.blueprint.dark.pdf` (if CairoSVG installed)

3. **Output quality:**
   - Drawing is readable on dark background (or white for print theme)
   - Key dimensions present (sheet size, part size, frame widths)
   - Labels do not overlap
   - No manual adjustment required

4. **Tests pass:**
   - All 6+ tests in `tests/test_blueprint_export.py` pass
   - Golden tests match expected SVG structure
   - PDF export test passes (or skips gracefully)

5. **Documentation:**
   - Recipe added to `docs/recipes/` showing blueprint export workflow
   - README updated with blueprint export section

### Implementation Notes

**Implementation Date:** 2025-12-19 (planned)

**Design Decisions:**

1. **SVG over DWG/DXF:**
   - Rationale: Web-first workflow, programmatic control, version control friendly
   - DXF/DWG can be added later as optional interchange format

2. **Intent-derived, not toolpath-based:**
   - Rationale: Faster to generate, no CAM backend dependency, clearer validation
   - Focus: "What will be cut" not "how it will be cut"

3. **Rails strategy for dimensions:**
   - Rationale: Deterministic placement, avoids cluttering part area
   - Trade-off: Less flexibility than manual CAD, but acceptable for proof drawings

4. **Dark theme as default:**
   - Rationale: Modern screen-first workflow, easier on eyes during design iteration
   - Print theme available for paper/PDF sharing

5. **Replace, not preserve:**
   - Permission granted to dump `export/svg_removal.py` and any legacy cad/export files
   - Rationale: Clean slate, no backward compatibility burden
   - Git history preserves old code if needed

**Adversarial Review Notes (Codex):**
- [ ] Verify dimension placement algorithm is deterministic
- [ ] Check for edge cases (very small parts, many overlapping features)
- [ ] Validate theme CSS does not leak into geometry
- [ ] Confirm PDF dependency is truly optional (graceful degradation)
- [ ] Review test coverage for golden file approach
- [ ] Ensure no CAM backend dependencies (IR only)

---

**Last Updated:** 2025-12-19
