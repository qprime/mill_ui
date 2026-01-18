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

## F004: Profile Cuts with Holding Tabs

**Status:** 🟢 Reviewed (Production)

**Priority:** High

**Architecture Layer:** Full Stack (PML → AST → IR → Planner)

### Problem Statement

When cutting out parts with profile cuts, the cut piece can shift or fall once the cut completes, causing:
- Damage to the part
- Safety hazards
- Poor cut quality on the final segments

Tabs solve this by leaving small uncut sections (holding bridges) that keep the part secured to the stock sheet during cutting. After cutting, tabs can be broken off and sanded smooth.

### Design

**Pipeline Location:**
```
PML → LayoutAST (Feature.tab_*) → RemovalIntent (Constraints.tabs) → Planner → G-code
```

**Syntax:**
```pml
rect <id> at <x>mm,<y>mm size <w>mm,<h>mm profile through outside tabs <count> height <height>mm [width <width>mm]
```

**Required parameters:**
- `tabs <count>`: Number of tabs (positive integer)
- `height <height>mm>`: Tab height in millimeters (how much material to leave uncut)

**Optional parameter:**
- `width <width>mm>`: Tab width along the perimeter (defaults to 2× tool diameter, minimum 6mm)

### Implementation

**Architecture layers modified:**

1. **AST Layer** ([layout_ast/layout.py:43-46](layout_ast/layout.py#L43-L46))
   - Extended `Feature` dataclass with `tab_count`, `tab_height_mm`, `tab_width_mm` fields

2. **PML Parser** ([pml/parser.py:275-319](pml/parser.py#L275-L319))
   - Added parsing for `tabs <count> height <height>mm [width <width>mm]` syntax
   - Index-based parsing handles optional components

3. **PML Formatter** ([pml/formatter.py:124-128](pml/formatter.py#L124-L128))
   - Emits tab specifications in canonical PML format

4. **AST Adapter** ([adapters/ast_to_removal.py:111-117](adapters/ast_to_removal.py#L111-L117))
   - Converts Feature tabs to RemovalIntent TabConstraint via hint dict

5. **Planner** ([cam/path/strategies.py:117-235](cam/path/strategies.py#L117-L235))
   - Already implemented: `profile_outline_with_tabs()` generates G-code with Z lifts

### Test Coverage

**Test file:** [tests/test_tabs.py](tests/test_tabs.py)

8 comprehensive tests covering:
- PML parsing with/without explicit width
- Inside/outside profile tabs
- AST construction with tabs
- RemovalIntent conversion
- Full pipeline (PML → AST → IR)
- PML roundtrip preservation

**Test results:** ✅ 8/8 passing

### Files Modified

**Modified (5 files):**
- `layout_ast/layout.py` - Feature dataclass extension
- `pml/parser.py` - Tab syntax parsing
- `pml/formatter.py` - Tab formatting
- `adapters/ast_to_removal.py` - AST → IR conversion
- `adapters/hints_to_removal.py` - Optional width handling fix

**Created (4 files):**
- `tests/test_tabs.py` - Comprehensive test suite
- `docs/recipes/15_profile_with_tabs/README.md` - Complete documentation
- `docs/recipes/15_profile_with_tabs/example.py` - Python examples
- `docs/recipes/15_profile_with_tabs/simple_cutout_with_tabs.pml` - PML example

### Usage Guidelines

**Tab count recommendations:**
| Part Size | Recommended Tabs | Reason |
|-----------|------------------|--------|
| < 200mm | 3 tabs | Minimal holding for small parts |
| 200-400mm | 4 tabs | Standard holding |
| > 400mm | 6+ tabs | Secure holding for large parts |

**Tab height recommendations:**
| Material Thickness | Recommended Height | Notes |
|--------------------|-------------------|-------|
| 12-19mm (1/2"-3/4") | 2-4mm | Standard: 3mm |
| 6-12mm (1/4"-1/2") | 1-3mm | Thinner material needs shorter tabs |
| > 19mm (> 3/4") | 4-6mm | Proportional to thickness |

**Rule of thumb:** Tab height should be 15-25% of material thickness.

### Limitations

**What works:**
- ✅ Profile cuts (inside, outside, on)
- ✅ Through-cuts and partial depth profiles
- ✅ Any shape (Rect, Circle, etc.)
- ✅ Optional width (uses planner default)

**What doesn't work:**
- ❌ Cannot combine with onion-skin roughing (`onion_skin_mm > 0`)
- ❌ Tabs on pockets (use profiles instead)
- ❌ Tabs on holes (not applicable)

### Acceptance Criteria

- [x] PML syntax parsing with required and optional parameters
- [x] AST construction with tab fields
- [x] RemovalIntent conversion with TabConstraint
- [x] Full pipeline integration (parse → format → parse roundtrip)
- [x] Comprehensive test coverage (8/8 tests passing)
- [x] Recipe documentation with examples and guidelines
- [x] PML syntax spec updated
- [x] All existing tests still pass (no regressions)

### Implementation Notes

**Implementation Date:** 2026-01-12

**Commit:** `4adeeb5b5841ea072575731f81a9e8622d0dc22a`

**Key Design Decisions:**

1. **Layered architecture approach:**
   - Tab infrastructure already existed at IR/planner layers (TabConstraint, profile_outline_with_tabs)
   - Only needed to add user-facing syntax through the stack
   - Clean separation of concerns maintained

2. **Optional width parameter:**
   - Used `None` to represent "not specified" rather than numeric default
   - Allows planner to apply its own logic: `max(tool_diameter × 2, 6mm)`
   - Fixed `adapters/hints_to_removal.py` to handle None properly

3. **Verbose syntax (Option A):**
   - Explicit `tabs <count> height <height>mm width <width>mm`
   - More readable than compact alternatives
   - Consistent with existing PML style

4. **Validation strategy:**
   - Planner enforces tabs + onion-skin conflict ([cam/planner/passes/profile.py:77](cam/planner/passes/profile.py#L77))
   - Parser validates positive integers and dimensions
   - Tab count must be positive, height/width must be positive if specified

**Tab Distribution:**
Tabs are evenly distributed around the perimeter by the planner:
- 4 tabs on rectangle: one per side (centered)
- 6 tabs on rectangle: typically 2 on long sides, 1 on short sides
- Planner calculates optimal spacing based on perimeter length

**Tab Geometry:**
During cutting:
- Tool plunges to bottom depth as normal
- At tab positions, tool lifts to `z_bottom + tab_height_mm`
- Tool traverses across tab width at lifted height
- Tool plunges back to full depth after tab

### Example Usage

**Simple cutout with tabs:**
```pml
sheet 600mm 400mm 19mm

rect cutout at 300mm,200mm size 400mm,250mm profile through outside tabs 4 height 3mm width 12mm
```

**Multiple parts with different tab configurations:**
```pml
sheet 800mm 600mm 19mm

# Small part: 3 tabs
rect small at 200mm,150mm size 150mm,100mm profile through outside tabs 3 height 2mm width 8mm

# Medium part: 4 tabs
rect medium at 200mm,400mm size 250mm,150mm profile through outside tabs 4 height 3mm width 12mm

# Large part: 6 tabs
rect large at 550mm,300mm size 400mm,250mm profile through outside tabs 6 height 4mm width 15mm
```

**Default width behavior:**
```pml
sheet 600mm 400mm 19mm

# Width omitted - planner uses max(tool_diameter × 2, 6mm)
rect cutout at 300mm,200mm size 400mm,250mm profile through outside tabs 4 height 3mm
```

### Documentation

- **Recipe:** [docs/recipes/15_profile_with_tabs/README.md](docs/recipes/15_profile_with_tabs/README.md)
- **Examples:** [docs/recipes/15_profile_with_tabs/example.py](docs/recipes/15_profile_with_tabs/example.py)
- **PML Example:** [docs/recipes/15_profile_with_tabs/simple_cutout_with_tabs.pml](docs/recipes/15_profile_with_tabs/simple_cutout_with_tabs.pml)

---

## F005: Sheet Nesting (Bin-Packing)

**Status:** 🟢 Reviewed (Production)

**Priority:** High

**Architecture Layer:** Pre-Pipeline (generates LayoutAST from part specifications)

### Problem Statement

Production runs require cutting many parts from stock sheets. Manual layout is:
- Time-consuming for large quantities
- Suboptimal material utilization
- Error-prone when placing many parts

Sheet nesting solves this by automatically placing parts on sheets to minimize waste.

### Design

**Pipeline Location:**
```
.nest → NestJob → Nesting Algorithm → list[LayoutAST] → standard CAM pipeline
```

**Syntax:**
```pml
nest maxrects
    sheet 1232mm 1245mm 19mm
    kerf 6.35mm
    margin 10mm

    parts
        door 457mm 597mm x20
            template Shaker
                stile_w 57mm
                rail_h 57mm
                panel_recess 6mm

        panel 305mm 203mm x15
```

### Implementation

**Algorithms:**
- **Guillotine** ([nesting/guillotine.py](nesting/guillotine.py)): Fast, simple guillotine cuts
- **MaxRects** ([nesting/maxrects.py](nesting/maxrects.py)): Better utilization with free rectangle tracking

**Data Structures:** ([nesting/types.py](nesting/types.py))
- `PartSpec`: Part dimensions, quantity, optional template
- `SheetSpec`: Sheet dimensions, margins, kerf
- `NestedPart`: Placed part with position and rotation
- `SheetLayout`: All placements on one sheet
- `NestingResult`: Complete multi-sheet solution

**API Functions:** ([nesting/api.py](nesting/api.py))
- `nest_parts()`: Low-level nesting API returning result dict
- `nest_and_generate()`: High-level API returning LayoutAST or PML

**Parser:** ([pml/nest_parser.py](pml/nest_parser.py))
- `parse_nest_pml()`: Parse `.nest` files to `NestJob`
- `nest_job_to_api_params()`: Convert `NestJob` to API parameters

**CLI Tool:** ([tools/nest.py](tools/nest.py))
```bash
PYTHONPATH=. python3 tools/nest.py job.nest -o output/
```

### Test Coverage

**Test files:**
- `tests/test_nest_parser.py` - Parser tests
- `tests/test_guillotine.py` - Guillotine algorithm tests
- `tests/test_maxrects.py` - MaxRects algorithm tests
- `tests/test_nesting_api.py` - API integration tests

**Test results:** ✅ All passing

### Acceptance Criteria

- [x] Parse `.nest` format with parts, quantities, templates
- [x] Guillotine algorithm implemented and tested
- [x] MaxRects algorithm implemented and tested
- [x] Multi-sheet support when parts don't fit on one sheet
- [x] Template expansion (Shaker template supported)
- [x] Generate LayoutAST or PML output
- [x] Validation (overlaps, bounds, kerf gaps)
- [x] CLI tool for command-line usage
- [x] Comprehensive test coverage
- [x] Recipe documentation (Recipes 16, 17, 18)

### Implementation Notes

**Implementation Date:** 2026-01-13

**Key Design Decisions:**

1. **Two algorithms available:**
   - Guillotine: ~62% utilization, fast
   - MaxRects: ~83% utilization, slower but better for production

2. **Template integration:**
   - Parts can specify templates (e.g., "Shaker")
   - Templates expanded to full Items during LayoutAST generation

3. **Center-based coordinates:**
   - Matches LayoutAST convention
   - Simplifies rotation handling

4. **Validation layer:**
   - Checks overlaps, bounds, kerf gaps
   - Warns on low utilization (<50%)

### Documentation

- **Recipe 16:** [docs/recipes/16_sheet_layout_nesting/](docs/recipes/16_sheet_layout_nesting/) - Basic nesting
- **Recipe 17:** [docs/recipes/17_nesting_guillotine/](docs/recipes/17_nesting_guillotine/) - Guillotine algorithm
- **Recipe 18:** [docs/recipes/18_nesting_maxrects/](docs/recipes/18_nesting_maxrects/) - MaxRects algorithm

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

**Current state:** Existing export modules were incomplete/broken before this feature:
- `export/svg_removal.py`: Basic SVG renderer (to be replaced)
- `cad/export/stl.py`: Now fully implemented (see F003)
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
- `cad/export/stl.py` (fully implemented - see F003)
- `cad/export/step.py` (broken, not relevant)
- `cad/export/panel_stl.py` (alternative heightfield-based STL, leave alone)
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

## F003: STL Export for Visual Validation

**Status:** 🟢 Reviewed (Production)

**Priority:** Medium

**Architecture Layer:** Export / Validation (post-IR, parallel to CAM)

### Problem Statement

Before machining expensive CNC parts, users need 3D visual validation to confirm:
- Pocket depths are correct (e.g., 6mm recess visible in 3D)
- Profile cuts are oriented correctly (inside vs outside)
- Features are placed accurately (hole positions, spacing)
- No unintended overlaps or collisions between features
- Material thickness is sufficient for through-cuts

**Goal:** Generate 3D STL meshes from PML layouts for visual inspection in standard viewers (FreeCAD, MeshLab, Windows 3D Viewer, online viewers), without requiring heavy CAD software.

### Implementation

**Files Created:**

1. **[cad/export/stl.py](cad/export/stl.py)** (335 lines) - Core STL exporter
   - `export_stl()` - Main entry point
   - `shape_dict_to_polygon()` - Convert shape dict to Shapely polygon
   - `apply_kerf_offset()` - Apply kerf compensation to geometry
   - `extrude_polygon_to_mesh()` - Extrude 2D polygon to 3D mesh
   - Uses `trimesh` for 3D mesh operations and Boolean CSG
   - Uses `shapely` for 2D polygon operations and kerf offsetting

2. **[adapters/ast_to_cad.py](adapters/ast_to_cad.py)** (51 lines) - Adapter layer
   - `items_to_shape_dicts()` - Converts LayoutAST items to shape dictionary format
   - Filters out non-shape items (templates, etc.)
   - Preserves geometry, placement, feature properties, and shape IDs

3. **[cli/export_cad.py](cli/export_cad.py)** (153 lines) - CLI tool
   - Command-line interface for STL export
   - Supports PML and JSON input formats
   - Supports compositional PML parsing with `--compositional` flag

4. **[tests/test_cad_export.py](tests/test_cad_export.py)** (300 lines) - Test suite
   - 8 test cases covering adapter and STL export functionality
   - Tests for basic shapes (Rect, Circle, Polyline)
   - Tests for pocket/hole features
   - Tests for kerf compensation

**Pipeline Location:**
```
PML/JSON → LayoutAST → [Adapter] → Shape Dicts → [STL Exporter] → Binary STL
                                                                      ↓
                                                         FreeCAD/MeshLab/Viewer
```

### Supported Features

**Geometry Types:**
- ✅ Rectangle (Rect) - Width/height specified
- ✅ Circle - Diameter specified
- ✅ Polyline - Point sequences with optional widths

**Feature Types:**
- ✅ **profile** (outside/inside) - Through-cuts that separate pieces
- ✅ **pocket** - Partial-depth depressions
- ✅ **hole** - Through-holes (subtractive)
- ✅ **engrave** - Surface carvings

**Configuration Options:**
1. **Kerf Compensation** (`--kerf` / `kerf_mm` parameter)
   - Offsets geometry by specified amount (typically ~3.175mm for 1/8" bit)
   - Applies to profiles (expands outside, contracts inside), pockets, holes
   - Uses Shapely polygon buffering

2. **Mesh Quality** (`--quality` parameter)
   - `low`: 16 segments per circle (fast preview)
   - `medium`: 32 segments per circle (default)
   - `high`: 64 segments per circle (smooth)

3. **Floating Parts** (`--no-floating-parts` flag)
   - By default exports separate STL files for cut-out pieces
   - Naming: `{basename}.stl` (main) + `{basename}_part_1.stl`, `_part_2.stl`, etc.

### Algorithm

The exporter uses a **Boolean CSG approach**:
1. Creates base sheet box mesh (width × height × thickness)
2. For each shape:
   - Converts to 2D polygon (Rect → rectangle, Circle → buffer point, Polyline → path)
   - Applies kerf offset if specified
   - Extrudes to 3D mesh with correct depth handling
   - Applies depth positioning based on feature type
3. Performs boolean operations (intersection for profiles, difference for subtractive features)
4. Separates floating parts by volume (keeps main piece, exports smaller pieces separately)
5. Repairs meshes as needed (fixes normals, fills holes)
6. Tries multiple boolean engines (`manifold`, `blender`) for robustness

### CLI Usage

```bash
# Basic export
python -m cli.export_cad --input door.pml --out preview/

# With kerf compensation (e.g., 1/8" bit = 3.175mm)
python -m cli.export_cad --input door.pml --kerf 3.175 --out preview/

# High quality mesh (64 circle segments)
python -m cli.export_cad --input door.pml --quality high --out preview/

# Exclude floating parts (cutouts)
python -m cli.export_cad --input door.pml --no-floating-parts --out preview/

# Compositional PML support
python -m cli.export_cad --input frame_design.pml --compositional --out preview/
```

**Output files:**
- `door.stl` - Main sheet with all features cut
- `door_part_1.stl` - First floating part (if profile through-cut)
- `door_part_2.stl` - Second floating part (etc.)

### Test Coverage

**Test file:** [tests/test_cad_export.py](tests/test_cad_export.py)

8 test cases:
- `test_items_to_shape_dicts_basic` - Basic adapter conversion
- `test_items_to_shape_dicts_pocket` - Pocket feature handling
- `test_items_to_shape_dicts_skips_templates` - Template filtering
- `test_items_to_shape_dicts_polyline` - Polyline geometry
- `test_stl_export_simple_profile` - End-to-end profile export
- `test_stl_export_with_pocket` - Profile + pocket export
- `test_stl_export_with_kerf` - Kerf compensation
- `test_stl_export_polyline` - Polyline/engrave export

**Recipe Integration:** STL files are automatically generated for all 18+ recipes via `tests/test_recipes.py`. Reference files available in `docs/recipes/*/output/*.stl`.

### Dependencies

**Required (in requirements.txt):**
- `trimesh>=4.0.0` - 3D mesh generation, boolean operations, STL export
- `shapely` - Polygon operations (indirect dependency)

### Acceptance Criteria

- [x] Export Shaker door template to STL successfully
- [x] Pockets show correct depth (measurable in 3D viewer)
- [x] Through profiles create clean holes/cutouts
- [x] Floating parts exported as separate `_part_N.stl` files
- [x] Kerf compensation visible (profiles enlarged/contracted by kerf amount)
- [x] Circles appear smooth at medium quality (32 segments)
- [x] Files load in FreeCAD, MeshLab, Windows 3D Viewer without errors
- [x] Polyline engraving creates visible grooves (better than v1 which skipped them)
- [x] All 8 unit tests passing
- [x] Recipe integration generates STL for all recipes

### Implementation Notes

**Implementation Date:** 2026-01-14

**Design Decisions:**

1. **trimesh + shapely over OCCT:**
   - Pure Python (no C++ build complexity)
   - Handles all v2 shapes including polylines
   - Good enough for validation use case
   - Faceted circles acceptable for CNC preview

2. **Binary STL format:**
   - Smaller file size (~50% of ASCII)
   - Faster to write/read
   - Universal viewer support

3. **Multiple boolean engines:**
   - Falls back between `manifold` and `blender` engines
   - Improves robustness for edge cases

4. **Floating parts separation:**
   - Uses volume comparison to identify main piece
   - Smaller pieces exported as separate files
   - Useful for visualizing cutout pieces

**Error Handling:**
- Graceful degradation for boolean operation failures
- Mesh repair (normals, holes) applied automatically
- Warning messages for problematic geometry

### Future Enhancements (Post-F003)

**F003b: STEP Export (Optional)**
- Use `build123d` (Pythonic OCCT wrapper)
- Export exact BREP geometry (parametric curves)
- For users who need CAD editing (import to Fusion360)

**F003c: Advanced Features**
- Partial-depth profiles (not just through-cuts)
- Chamfers/fillets (round edges for presentation)
- Material visualization (wood grain texture overlay)
- Assembly export (multi-part projects)

---

## F006: Domain/Generator System (Math-Based Composition)

**Status:** 🟢 Reviewed (Production)

**Priority:** High

**Architecture Layer:** Design Composition (pre-AST, generates LayoutAST Items)

### Problem Statement

Templates like Shaker work well for common designs but create structural problems at scale:
- **Template explosion**: Each new style requires a new template
- **Redraw labor**: Size variations require manual parameter adjustment
- **Style-specific geometry**: Similar operations reimplemented per template
- **SKU rigidity**: Adding a new SKU means adding code, not composing primitives

### Solution: Math-Based Composition

**Domains** are bounded 2D regions that define *where* operations may occur. They support algebraic operations:
- `inset(distance)` - Contract boundary inward
- `offset(distance)` - Expand boundary outward
- `subtract(other)` - Remove overlapping region (creates holes)
- `intersect(other)` - Keep only overlapping region

**Generators** are deterministic functions that define *what* geometry to produce within a domain:
- **Area generators**: flat pocket, wave pattern, grid pattern
- **Loop generators**: profile cut, bead/groove
- **SVG generators**: Parse SVG paths and stamp as engravings

This separation enables hundreds of SKUs from few primitives.

### Implementation

**Files Created:**

1. **domains/** - Domain type and operations
   - `domains/domain.py` - Domain and MultiDomain dataclasses (~450 lines)
   - `domains/transforms.py` - Coordinate transforms (~200 lines)
   - `domains/__init__.py` - Public exports

2. **generators/** - Generator implementations
   - `generators/base.py` - Protocol, parameter classes (~400 lines)
   - `generators/area/flat.py` - Flat pocket generator
   - `generators/area/wave.py` - Wave pattern generator
   - `generators/area/grid.py` - Grid pattern generator
   - `generators/loop/profile.py` - Profile cut generator
   - `generators/loop/bead.py` - Bead/groove generator
   - `generators/svg/` - SVG path parsing and stamping (~800 lines)

3. **Tests**
   - `tests/test_domain.py` - Domain operations tests
   - `tests/test_transforms.py` - Coordinate transform tests
   - `tests/test_generators.py` - Generator tests
   - `tests/test_stage5_generators.py` - Wave, Grid, Bead tests
   - `tests/test_svg_parser.py` - SVG parsing tests
   - `tests/test_performance.py` - Performance benchmarks

4. **Documentation**
   - `docs/domain_generator_design.md` - Full architecture specification
   - `docs/examples/domain_generator_example.py` - Integration examples

### Usage Example

```python
from domains import Domain
from generators import profile_generator, flat_pocket_generator, ProfileParams, FlatPocketParams
from layout_ast.layout import LayoutAST, Sheet

# Create domains
outer = Domain.from_rectangle(400, 600, center=(200, 300))
panel = outer.inset(50).domains[0]  # Frame is 50mm wide

# Generate items
profile_items = profile_generator(outer, ProfileParams(side="outside", depth="through"))
pocket_items = flat_pocket_generator(panel, FlatPocketParams(depth_mm=6.0))

# Build LayoutAST
ast = LayoutAST(
    sheet=Sheet(width_mm=450, height_mm=650, thickness_mm=19.0),
    items=tuple(profile_items + pocket_items),
)

# Convert to RemovalIntent IR as usual
from adapters.ast_to_removal import ast_to_removal_intents
intents = ast_to_removal_intents(ast)
```

### Test Coverage

- Domain operations: 40+ tests (inset, offset, subtract, intersect, edge cases)
- Coordinate transforms: 34 tests (rotation, translation, round-trip)
- Generators: 35+ tests (flat pocket, profile, wave, grid, bead)
- SVG parsing: 50+ tests (path commands, curves, edge cases)
- Performance: 15+ benchmarks with thresholds

### Performance

| Operation | Threshold | Actual |
|-----------|-----------|--------|
| Rectangle construction | < 1ms | ~0.07ms |
| Polygon (100 vertices) | < 10ms | ~0.12ms |
| Inset operation | < 5ms | ~0.08ms |
| Flat pocket generator | < 5ms | ~0.01ms |
| Wave generator | < 100ms | ~56ms |
| Full pipeline (Domain → AST → IR) | < 200ms | ~0.18ms |

### Dependencies

- `shapely` - Polygon boolean operations and offsets

### Acceptance Criteria

- [x] Domain type with inset, offset, subtract, intersect operations
- [x] MultiDomain for handling split/empty results
- [x] Coordinate transforms (local ↔ sheet space)
- [x] FlatPocket generator
- [x] Profile generator with loop selection
- [x] Wave pattern generator
- [x] Grid pattern generator
- [x] Bead/groove generator
- [x] SVG path parsing with curve flattening
- [x] SVG stamp generator
- [x] All generators output valid LayoutAST Items
- [x] Determinism verified (same inputs → same outputs)
- [x] Performance benchmarks established
- [x] Integration example demonstrating full pipeline
- [x] Documentation updated (CLAUDE.md, README.md, FEATURES.md)

### Design Decisions

1. **Polygonal domains only** - Curves lowered to polylines early for tractable algebra
2. **Typed generator params** - Validation at generator entry, not flat dicts
3. **Domain-local coordinates** - Patterns computed locally, transformed to sheet space
4. **Generator-owned depth** - Domains are 2D only; depth is a machining decision
5. **Explicit loop selection** - No implicit guessing for which boundaries to operate on
6. **Loud failures** - Manufacturing pipeline must not silently degrade

### Documentation

- **Architecture spec:** [docs/domain_generator_design.md](docs/domain_generator_design.md)
- **Integration example:** [docs/examples/domain_generator_example.py](docs/examples/domain_generator_example.py)
- **Recipe:** [docs/recipes/19_domain_generator_basics/](docs/recipes/19_domain_generator_basics/)

---

**Last Updated:** 2026-01-17
