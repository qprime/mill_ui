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

**Last Updated:** 2025-12-19
