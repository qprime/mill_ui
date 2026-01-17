# Core Module Cleanup - Development Plan

**Document Purpose:** Define scope, stages, and exit criteria for cleanup refactoring to improve AI-coding stability and maintainability.

**Primary Audience:** AI agents (Claude Opus for implementation, ChatGPT Codex for review)

**Last Updated:** 2026-01-17 (Stage 5 complete - all stages done)

---

## 1. Overview

### 1.1 Problem Statement

Independent analysis by Claude and Codex identified structural issues in core modules that reduce AI-coding stability:

| Issue | Location | AI Impact |
|-------|----------|-----------|
| Hardcoded string keys | `hints_to_removal.py`, adapters | Typo-prone, no autocomplete |
| Duplicate bounds calculation | 3 implementations across modules | AI may call wrong one or create fourth |
| Mixed depth semantics | `Feature.depth: str \| float` | Ambiguous, AI generates wrong types |
| Silent error swallowing | `ast_to_removal.py:29-32` | Hidden failures during AI development |
| Large `_resolve_node()` | `layout_resolver.py:174-492` | Hard to modify correct branch |
| Inconsistent error types | `PMLParseError` vs `ParseError` | AI catches wrong exception |

### 1.2 Goals

1. **Reduce AI error surface** - Constants, enums, and typed access prevent hallucination errors
2. **Consolidate duplicates** - Single source of truth for bounds calculation
3. **Surface errors early** - Logging/warnings instead of silent continues
4. **Maintain compatibility** - No breaking changes to public APIs

### 1.3 Non-Goals

- Parser refactoring (low ROI, works correctly)
- Performance optimization (not the focus)
- New features (cleanup only)

### 1.4 Risk Assessment

| Change | Risk | Mitigation |
|--------|------|------------|
| Constants module | Very low | Additive, then mechanical find-replace |
| Bounds utility | Low | Extract, redirect calls, test |
| Depth enum | Moderate | Audit all `== "through"` checks |
| Error logging | Very low | Additive only |
| Resolver refactor | Moderate | Incremental, one node type at a time |

---

## 2. Architecture

### 2.1 New Module: `core/constants.py`

```python
# Hint dictionary keys
class HintKeys:
    ID = "id"
    SHAPE = "shape"
    FEATURE = "feature"
    DEPTH = "depth"
    CENTER_XY = "center_xy_mm"
    # ... etc

# Feature type constants
class FeatureTypes:
    PROFILE = "profile"
    POCKET = "pocket"
    HOLE = "hole"
    ENGRAVE = "engrave"

# Depth mode constants
class DepthMode:
    THROUGH = "through"
    # Numeric depths are floats, not in this enum
```

### 2.2 Unified Bounds Utility

Current state (3 implementations):
```
hints_to_removal.py:165-204  → _geometry_to_bounds() [v1 hint dict]
hints_to_removal.py:289-317  → _item_geometry_to_bounds() [Item dataclass]
layout_resolver.py:106-135   → inline in _collect_island_bounds()
```

Target state:
```
core/geometry.py:
  → compute_shape_bounds(shape_type, geometry_data, center_xy) -> Bounds2D

All three locations import and call this single function.
```

### 2.3 Depth Enum Strategy

Current:
```python
@dataclass(frozen=True)
class Feature:
    type: str
    depth: str | float = "through"  # Ambiguous
```

Target:
```python
class DepthSpec:
    THROUGH = "through"

    @staticmethod
    def is_through(depth: str | float) -> bool:
        return depth == DepthSpec.THROUGH

    @staticmethod
    def resolve(depth: str | float, sheet_thickness: float) -> float:
        if DepthSpec.is_through(depth):
            return sheet_thickness
        return float(depth)
```

This preserves the `str | float` union for backward compatibility while providing safe accessors.

---

## 3. Development Stages

### Stage 0: Planning Document (THIS DOCUMENT)
**Status:** ✅ Complete

**Scope:**
- Document issues, architecture, and stages
- Get user approval before implementation

**Exit Criteria:**
- [x] Document created
- [x] User approval to proceed

---

### Stage 1: Constants Module
**Status:** ✅ Complete

**Scope:**
- Create `core/constants.py` with all string key constants
- Create `core/__init__.py` to export constants
- Update imports in affected files (do NOT change logic yet)

**Files Created:**
- `core/__init__.py`
- `core/constants.py`

**Files Modified:**
- `adapters/hints_to_removal.py`
- `adapters/ast_to_removal.py`
- `adapters/removal_to_planner.py`

**Exit Criteria:**
- [x] All hardcoded string keys replaced with constants
- [x] All existing tests pass
- [x] No logic changes, only string replacements

**Actual Scope:** ~65 string replacements across 3 adapter files

**Implementation Notes (2026-01-17):**

Files created:
- `core/__init__.py` - Module init, exports all constant classes
- `core/constants.py` - All string constant definitions

Constant classes defined:
- `HintKeys` - v1 hint dictionary keys (id, shape, geometry, center_xy_mm, etc.)
- `GeometryKeys` - Geometry data keys (w_mm, h_mm, diameter_mm, islands, etc.)
- `TabKeys` - Tab constraint keys (count, height, height_mm, width_mm)
- `MetadataKeys` - RemovalIntent metadata keys (hint_type, original_id, etc.)
- `FeatureType` - Feature type values (profile, pocket, hole, engrave)
- `ShapeType` - Shape type values with helper methods (is_rect, is_circle)
- `Side` - Profile side values (outside, inside, on)
- `DepthMode` - Depth mode strings with helper methods (is_through, is_half, resolve)
- `HintCollectionKeys` - Top-level hint collection keys (profiles, pockets, etc.)

Tests verified passing:
- `run_edge_tests.py` - 6/6 passed
- `run_removal_intent_tests.py` - 7/7 passed
- `run_hints_adapter_tests.py` - 7/7 passed
- `run_planner_adapter_tests.py` - 7/7 passed
- `run_basic_tests.py` - 4/4 passed
- `run_compositional_pml_tests.py` - 10/10 passed
- `run_resolution_tests.py` - 8/8 passed

Note: Added `ShapeType.is_rect()` and `ShapeType.is_circle()` helper methods for case-insensitive shape comparison, and `DepthMode.resolve()` for depth resolution - these will be useful in Stage 4.

---

### Stage 2: Unified Bounds Utility
**Status:** ✅ Complete

**Scope:**
- Create `core/geometry.py` with `compute_shape_bounds()`
- Refactor three implementations to call single utility
- Add unit tests for bounds calculation

**Files Created:**
- `core/geometry.py`

**Files Modified:**
- `adapters/hints_to_removal.py` (two functions now delegate to unified utility)
- `resolution/layout_resolver.py` (`_collect_island_bounds` now uses `compute_shape_bounds_dict`)
- `core/__init__.py` (exports new geometry functions)

**Tests Added:**
- `tests/test_bounds_utility.py` - 11 tests covering all shape types

**Exit Criteria:**
- [x] Single bounds implementation
- [x] All three call sites updated
- [x] Unit tests for each shape type (Rect, Circle, RoundedRect, etc.)
- [x] All existing tests pass

**Implementation Notes (2026-01-17):**

Created `core/geometry.py` with two functions:
- `compute_shape_bounds(shape_type, geometry_data, center_xy) -> Bounds2D` - Main utility
- `compute_shape_bounds_dict(shape_type, geometry_data, center_xy) -> dict` - Dict variant for JSON contexts

Supported shapes:
- Rect, Rectangle (case-insensitive, alias)
- Circle (case-insensitive)
- RoundedRect (uses same w_mm/h_mm as Rect)
- Unknown shapes fallback to 1x1mm box

Refactored call sites:
1. `_geometry_to_bounds()` in hints_to_removal.py - Now a one-liner delegating to utility
2. `_item_geometry_to_bounds()` in hints_to_removal.py - Now a one-liner delegating to utility
3. Inline bounds calc in `_collect_island_bounds()` in layout_resolver.py - Replaced 22 lines with 5

Test results: All 49+ existing tests pass, 11 new bounds utility tests added.

---

### Stage 3: Error Logging
**Status:** ✅ Complete

**Scope:**
- Add logging to silent `except` blocks in `ast_to_removal.py`
- Add optional warning collection parameter
- Do NOT change control flow (still continue on error)

**Files Modified:**
- `adapters/ast_to_removal.py`

**Files Created:**
- `tests/run_ast_to_removal_tests.py`

**Exit Criteria:**
- [x] Silent catches now log warnings
- [x] Optional `warnings: list` parameter to collect issues
- [x] All existing tests pass
- [x] New test verifying warnings are collected

---

### Stage 4: Depth Accessor Utilities
**Status:** ✅ Complete

**Scope:**
- Add `DepthSpec` class with `is_through()` and `resolve()` methods
- Update depth comparisons to use `DepthSpec.is_through()`
- Do NOT change `Feature.depth` type signature (backward compat)

**Files to Create:**
- Add to `core/constants.py` or new `core/depth.py`

**Files to Modify:**
- `adapters/ast_to_removal.py` (depth resolution)
- `adapters/hints_to_removal.py` (depth handling)
- Any other depth comparisons

**Exit Criteria:**
- [x] All `depth == "through"` replaced with `DepthSpec.is_through(depth)`
- [x] All depth-to-mm conversions use `DepthSpec.resolve()`
- [x] All existing tests pass
- [x] Feature.depth type unchanged for compatibility

**Implementation Notes (2026-01-17):**

Used existing `DepthMode` class (created in Stage 1) as the `DepthSpec` implementation. The class already had `is_through()`, `is_half()`, and `resolve()` methods.

**Files Modified:**

Core adapter updates to use `DepthMode.is_through()` and `DepthMode.resolve()`:
- `adapters/ast_to_removal.py` - `_resolve_depth()` now delegates to `DepthMode.resolve()`
- `cad/export/stl.py` - 2 depth comparisons updated
- `cad/export/panel_stl.py` - 2 depth comparisons updated
- `cam/model/hints.py` - 1 depth comparison updated
- `pml/parser.py` - 1 depth comparison updated, uses `DepthMode.THROUGH` constant
- `pml/formatter.py` - 2 depth comparisons updated
- `resolution/layout_resolver.py` - 1 depth comparison updated
- `validation/assertions/intent_assertions.py` - 3 depth comparisons updated
- `export/blueprint_svg.py` - 2 depth comparisons updated

**Tests Added:**
- `tests/test_depth_spec.py` - 11 tests covering:
  - `is_through()` with strings, numerics, and None
  - `is_half()` behavior
  - `resolve()` for through, half, numeric, None, and string numbers
  - Integration with `_resolve_depth()` in ast_to_removal

**Test Results:** All 80+ tests across 10 test suites passed:
- `run_edge_tests.py` - 6/6 passed
- `run_removal_intent_tests.py` - 7/7 passed
- `run_hints_adapter_tests.py` - 7/7 passed
- `run_planner_adapter_tests.py` - 7/7 passed
- `run_basic_tests.py` - 4/4 passed
- `run_compositional_pml_tests.py` - 10/10 passed
- `run_resolution_tests.py` - 8/8 passed
- `run_pml_tests.py` - 14/14 passed
- `run_ast_to_removal_tests.py` - 6/6 passed
- `test_bounds_utility.py` - 11/11 passed
- `test_depth_spec.py` - 11/11 passed

**Note:** Some test files (e.g., `tests/test_pml_corner_cleanup.py`, `tests/run_shaker_tests.py`) still use `== "through"` in test assertions. This is intentional - test files verify the expected string value, not the accessor pattern. Production code now consistently uses `DepthMode.is_through()`.

---

### Stage 5: Resolver Visitor Pattern (Optional)
**Status:** ✅ Complete

**Scope:**
- Extract node handlers from `_resolve_node()` into handler map
- Incremental: one node type at a time
- Each extraction is a separate commit

**Files to Modify:**
- `resolution/layout_resolver.py`

**Risk:** Moderate - this is the AST interpreter

**Exit Criteria:**
- [x] Handler map dispatches to per-type functions
- [x] Each handler is <50 lines
- [x] All existing tests pass after each extraction
- [x] Behavior identical (test coverage required first)

**Implementation Notes (2026-01-17):**

Refactored `_resolve_node()` from a 318-line if/elif chain into a handler map pattern with 16 dedicated handler methods.

**Architecture:**

```python
# Handler map (lazily initialized class variable)
_NODE_HANDLERS: dict[type, NodeHandler] = {
    Panel: LayoutResolver._handle_panel,
    Inset: LayoutResolver._handle_inset,
    Frame: LayoutResolver._handle_frame,
    Grid: LayoutResolver._handle_grid,
    Split: LayoutResolver._handle_split,
    Cell: LayoutResolver._handle_cell,
    UseComponent: LayoutResolver._handle_use_component,
    Place: LayoutResolver._handle_place,
    Rect: LayoutResolver._handle_rect,
    Circle: LayoutResolver._handle_circle,
    RoundedRect: LayoutResolver._handle_rounded_rect,
    Line: LayoutResolver._handle_line,
    Polyline: LayoutResolver._handle_polyline,
    SplinePath: LayoutResolver._handle_spline_path,
    Keepout: LayoutResolver._handle_keepout,
    Item: LayoutResolver._handle_item,
}

# New dispatcher (15 lines)
def _resolve_node(self, node, region, items, params) -> None:
    if node is None:
        return
    handler_map = self._get_handler_map()
    node_type = type(node)
    if node_type in handler_map:
        handler_map[node_type](self, node, region, items, params)
```

**Handler sizes (all under 50 lines):**
- `_handle_panel`: 3 lines
- `_handle_inset`: 4 lines
- `_handle_frame`: 15 lines
- `_handle_grid`: 14 lines
- `_handle_split`: 14 lines
- `_handle_cell`: 3 lines
- `_handle_use_component`: 9 lines
- `_handle_place`: 10 lines
- `_handle_rect`: 24 lines
- `_handle_circle`: 27 lines
- `_handle_rounded_rect`: 27 lines
- `_handle_line`: 21 lines
- `_handle_polyline`: 14 lines
- `_handle_spline_path`: 21 lines
- `_handle_keepout`: 2 lines
- `_handle_item`: 2 lines

**Benefits:**
1. **AI-coding stability**: Each node type is handled by a clearly named, isolated method
2. **Easier debugging**: Stack traces show specific handler (e.g., `_handle_rect`) instead of generic `_resolve_node`
3. **Extensibility**: Adding new node types requires only adding a handler method and one map entry
4. **Testability**: Individual handlers can be unit tested in isolation if needed

**Test Results:** All 56+ tests across 8 test suites passed:
- `run_resolution_tests.py` - 8/8 passed
- `run_edge_tests.py` - 6/6 passed
- `run_compositional_pml_tests.py` - 10/10 passed
- `run_basic_tests.py` - 4/4 passed
- `run_removal_intent_tests.py` - 7/7 passed
- `run_hints_adapter_tests.py` - 7/7 passed
- `run_planner_adapter_tests.py` - 7/7 passed
- `run_pml_tests.py` - 14/14 passed
- `run_ast_to_removal_tests.py` - 6/6 passed

---

## 4. Testing Strategy

### 4.1 Existing Test Coverage

Tests that must pass after each stage:
- `tests/run_edge_tests.py` - IR-level validation
- `tests/run_gcode_equivalence_tests.py` - End-to-end CAM (if available)
- Recipe validation via `cli/validate_cam.py`

### 4.2 New Tests Per Stage

| Stage | New Tests |
|-------|-----------|
| 1 | None needed (mechanical replacement) |
| 2 | `tests/test_bounds_utility.py` - shape bounds calculation |
| 3 | `tests/test_ast_to_removal.py` - warning collection |
| 4 | `tests/test_depth_spec.py` - depth resolution |
| 5 | Existing tests sufficient (behavior unchanged) |

---

## 5. Documentation Updates

After completion, update:
- [x] `CLAUDE.md` - Core module noted in extension patterns (constants for hint keys)
- [x] `README.md` - No changes needed (architecture unchanged)
- [x] This document - All stages marked complete with implementation notes

---

## 6. Stage Log

### Stage 0 Notes (2026-01-17)

Document created based on joint Claude/Codex analysis. Key findings:
- Both models identified same issues independently (high confidence)
- Constants module has highest AI-stability ROI
- Parser refactoring explicitly out of scope (working correctly)
- Resolver refactoring is optional/last due to risk

User approval received to begin Stage 1.

---

### Stage 1 Notes (2026-01-17)

**Implementation Summary:**

Created `core/` module with comprehensive constants for all hint dictionary keys, geometry keys, feature types, shape types, and depth modes. Updated all three adapter files to use these constants.

**Key Decisions:**

1. **Class-based constants vs module-level:** Used classes (e.g., `class HintKeys`) rather than module-level constants for better namespacing and IDE autocomplete. Access pattern is `HintKeys.ID` rather than `HINT_KEY_ID`.

2. **Helper methods added:** Added `ShapeType.is_rect()`, `ShapeType.is_circle()`, and `DepthMode.resolve()` during implementation. These provide case-insensitive comparison and depth resolution logic that was previously scattered. This partially addresses Stage 4 goals early.

3. **Scope limited to adapter layer:** Only updated `adapters/` files in this stage. Other files (tests, CAM pipeline, etc.) still use hardcoded strings but these are less critical since they're either test fixtures or downstream consumers.

**Files Changed:**
- Created: `core/__init__.py`, `core/constants.py`
- Modified: `adapters/hints_to_removal.py`, `adapters/ast_to_removal.py`, `adapters/removal_to_planner.py`

**Test Results:** All 49+ tests across 7 test suites passed without modification.

---

### Stage 3 Notes (2026-01-17)

**Implementation Summary:**

Added error logging and optional warning collection to `ast_to_removal.py`. Previously, conversion errors were silently swallowed with a bare `continue`. Now errors are:
1. Logged via Python's `logging` module (at WARNING level)
2. Optionally collected into a user-provided list for programmatic access

**API Changes:**

```python
# Before (silent failures)
intents = ast_to_removal_intents(ast)

# After (backward compatible - warnings param is optional)
warnings: list[str] = []
intents = ast_to_removal_intents(ast, warnings=warnings)
# warnings now contains messages like:
# "Skipping item 'rect1': Item rect1 has no geometry"
```

**Key Decisions:**

1. **Optional parameter:** Made `warnings` optional (defaults to `None`) to maintain full backward compatibility. Existing callers work unchanged.

2. **Control flow preserved:** Still uses `continue` on error - no behavior change for valid inputs. Only adds visibility into failures.

3. **Structured messages:** Warning format is `"Skipping item '{shape_id}': {error_message}"` for easy parsing if needed.

**Files Changed:**
- Modified: `adapters/ast_to_removal.py` (added logging, warnings param)
- Created: `tests/run_ast_to_removal_tests.py` (6 test cases)

**Test Results:**
- New tests: 6/6 passed
- Existing tests: All 49+ across 7 suites passed

**Test Coverage Added:**
- `test_warning_collection_on_invalid_item` - missing geometry triggers warning
- `test_no_warnings_when_all_valid` - no warnings when items are valid
- `test_warnings_none_by_default` - backward compat without warnings param
- `test_skips_non_shape_items` - non-shape items don't trigger warnings
- `test_unknown_feature_type_warning` - unknown feature type triggers warning
- `test_multiple_warnings` - multiple failures each generate warnings
