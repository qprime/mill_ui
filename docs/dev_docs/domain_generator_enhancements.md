# Domain/Generator Enhancements

Future enhancements to the domain/generator system. For the implemented Stages 1-9, see [domain_generator_design.md](domain_generator_design.md).

**Implementation Status:**
- Stages 1-9: Complete (see domain_generator_design.md)
- Stage 10: Not started
- Stage 11: Complete (`local_coords` parameter added to split operations)
- Stage 12: Complete (PML generator syntax implemented)
- Stage 13: Partial (Domain utilities added: `from_arch()`, `from_polygon()`, `split_horizontal_with_gaps()`, param classes `LinePatternParams`, `ConcentricBorderParams`. Generators pending: `line_pattern_generator`, `concentric_border_generator`)
- Stage 14: Not started

---

## How to Implement a Stage

Use this prompt in a new Claude Code session:

```
Read CLAUDE.md, then read docs/domain_generator_enhancements.md and implement Stage N.
```

Each stage has an **Implementation** section with:
- Files to modify/create
- Tests to write
- Commands to run
- Dependencies on prior stages

---

## Stage 10: Variable-Depth Semantics

**Goal:** Support non-constant Z depths for V-bit carving, bevels, and gradient machining.

### Problem

Current `RemovalIntent` assumes constant depth (`z_top`, `z_bottom`). Bevels and chamfers emit as pocket/profile with metadata, but the CAM planner has no way to interpret variable-depth toolpaths.

### Solution

Add `DepthProfile` to the IR layer:

```python
@dataclass(frozen=True)
class DepthProfile:
    """Describes Z variation across a removal region."""
    mode: str  # "constant", "linear_gradient", "v_carve"
    z_top: float
    z_bottom: float
    # For gradients
    gradient_direction_deg: float | None = None
    # For V-carve
    v_angle_deg: float | None = None
```

Update `RemovalIntent`:

```python
@dataclass(frozen=True)
class RemovalIntent:
    region_id: str
    bounds: Bounds2D
    depth_profile: DepthProfile  # Replaces z_top/z_bottom
    allowance: Allowance
    constraints: Constraints
    metadata: dict
```

### Validation

- V-carve angle must match available tooling
- Gradient depth must not exceed sheet thickness
- Bevel inner depth must be reachable with specified angle

### Migration

- Existing code uses `z_top`/`z_bottom` directly
- Add `depth_profile` with `mode="constant"` as default
- Deprecate direct `z_top`/`z_bottom` access

### Implementation

**Files to modify:**
- `ir/removal_intent.py` — Add `DepthProfile` dataclass, update `RemovalIntent`
- `adapters/ast_to_removal.py` — Emit `DepthProfile` instead of raw z values
- `adapters/hints_to_removal.py` — Same
- `validation/removal_checks.py` — Add depth profile validation

**Tests:**
- Add tests to `tests/test_removal_intent.py` for DepthProfile modes
- Verify existing tests pass with `mode="constant"` default

**Run:** `python -m tests.run_edge_tests`

**Dependencies:** None (first enhancement stage)

---

## Stage 11: Local-Coordinate Split Operations

**Goal:** Enable split operations aligned to domain-local axes for rotated panels.

### Problem

Current `split_horizontal`/`split_vertical`/`split_grid` operate in sheet-space coordinates. A domain rotated 45° still splits along sheet X/Y axes, not along its own orientation.

### Solution

Add `local_coords` parameter to split methods:

```python
def split_horizontal(
    self,
    n: int,
    gap_mm: float = 0.0,
    local_coords: bool = False,  # New parameter
) -> MultiDomain:
    """
    Args:
        local_coords: If True, split along domain's local Y axis.
                      If False (default), split along sheet Y axis.
    """
```

Implementation:
1. If `local_coords=False`: current behavior (sheet-aligned)
2. If `local_coords=True`:
   - Transform domain to local coordinates
   - Perform axis-aligned split
   - Transform results back to sheet coordinates

### Use Cases

- Rotated cabinet doors with proper stile/rail orientation
- Angled panels with subdivisions following panel edges
- Nested rotated components

### Implementation

**Files to modify:**
- `domains/domain.py` — Add `local_coords` parameter to `split_horizontal`, `split_vertical`, `split_grid`
- `core/geometry.py` — Add rotation transform utilities if needed

**Tests:**
- Add tests to `tests/test_domain.py` for rotated domain splits
- Test that `local_coords=False` (default) preserves existing behavior

**Run:** `python -m tests.test_domain`

**Dependencies:** None

---

## Stage 12: PML Generator Syntax

**Goal:** Extend PML to declare generators and domain operations, making Python code unnecessary for standard designs.

### Current State

Recipes are Python scripts with explicit API calls:

```python
door = Domain.from_rectangle(400, 600, center=(200, 300))
panel = door.inset(50).domains[0]
items = profile_generator(door, ProfileParams(...))
items += flat_pocket_generator(panel, FlatPocketParams(...))
```

### Target State

Recipes become PML files:

```pml
sheet 400mm 600mm 19mm

door Rect 400mm 600mm center 200mm 300mm
    profile outside through
    frame 50mm
        pocket 6mm
```

### PML Extensions Required

#### Generator Keywords

```pml
# Profile cut
profile <side> <depth>
profile outside through
profile inside 10mm

# Pocket
pocket <depth>
pocket 6mm

# Raised panel
raised_panel border <width> border_depth <depth> field_depth <depth>
raised_panel border 25mm border_depth 6mm field_depth 2mm

# Chamfer
chamfer <width> <depth>
chamfer 5mm 3mm

# Wave pattern
wave count <n> amplitude <mm> wavelength <mm> groove <mm> depth <mm>
wave count 5 amplitude 10mm wavelength 60mm groove 3mm depth 2mm

# Line pattern
lines angle <deg> spacing <mm> width <mm> depth <mm>
lines angle 45 spacing 25mm width 4mm depth 3mm
```

#### Domain Operation Keywords

```pml
# Frame (inset with implicit subtraction)
frame <width>
    <children operate on inset region>

# Split operations
split_horizontal <n> gap <mm>
split_vertical <n> gap <mm>
split_grid <rows> <cols> gap <mm>

# Explicit inset/offset
inset <distance>
offset <distance>
```

#### New Shape Primitives

```pml
# Arch-topped rectangle
Arch <width> <height> radius <mm>

# Inline polygon
Polygon points (0,0) (100,0) (100,100) (0,100)

# Polygon with holes
Polygon points (...) hole (...)
```

### Example: Cathedral Arch Door in PML

```pml
sheet 500mm 800mm 19mm

door Arch 500mm 800mm radius 250mm center 250mm 400mm
    profile outside through
    frame 60mm
        raised_panel border 25mm border_depth 6mm field_depth 2mm
```

### Example: Four-Panel Raised Door in PML

```pml
sheet 500mm 700mm 19mm

door Rect 500mm 700mm center 250mm 350mm
    profile outside through
    frame 65mm
        split_grid 2 2 gap 35mm
            raised_panel border 25mm border_depth 6mm field_depth 2mm
```

### Example: Wave Texture Panel in PML

```pml
sheet 300mm 300mm 19mm

panel Rect 300mm 300mm center 150mm 150mm
    profile outside through
    wave count 5 amplitude 10mm wavelength 60mm groove 3mm depth 2mm
```

### Implementation Approach

1. Extend `pml/compositional_parser.py` with generator keywords
2. Map PML generator syntax to `generators/` function calls
3. Domain operations (`frame`, `split_*`) become layout managers
4. Resolution phase converts PML AST → Domain operations → LayoutAST

### Implementation

**Files to modify:**
- `pml/compositional_parser.py` — Add generator and domain operation keywords
- `resolution/layout_resolver.py` — Map PML keywords to generator calls
- `layout_ast/layout.py` — May need new AST node types for generators

**Tests:**
- Add PML parsing tests to `tests/test_pml_parser.py`
- Add resolution tests that verify PML → LayoutAST produces correct Items
- Test each generator keyword (profile, pocket, raised_panel, chamfer, wave, lines)
- Test domain operations (frame, split_horizontal, split_vertical, split_grid)

**Run:** `python -m tests.run_edge_tests`

**Dependencies:** None (generators already exist in Python API)

### Implementation Notes (Completed 2026-01-18)

**Implemented keywords:**
- `profile <side> <depth>` — ProfileGen node, resolved via layout_resolver
- `pocket <depth>` — PocketGen node, creates rectangular pocket
- `raised_panel border <w> border_depth <d> field_depth <d>` — RaisedPanelGen, calls raised_panel_generator
- `chamfer <width> <depth>` — ChamferGen node
- `wave count <n> amplitude <mm> wavelength <mm> groove <mm> depth <mm>` — WaveGen, calls wave_generator
- `split_horizontal <n> gap <mm>` — SplitHorizontal layout manager
- `split_vertical <n> gap <mm>` — SplitVertical layout manager
- `split_grid <rows> <cols> gap <mm>` — SplitGrid layout manager

**Not yet implemented (deferred to Stage 13):**
- `lines angle <deg> spacing <mm> width <mm> depth <mm>` — requires line_pattern_generator
- `Arch <width> <height> radius <mm>` — Domain.from_arch() exists but PML parsing not added
- `Polygon points (...)` — Domain.from_polygon() exists but PML parsing not added
- `offset <distance>` — Domain.offset() exists but PML keyword not added

**Key implementation details:**
- Wave generator uses `wave_count` to compute effective wavelength: `wavelength = domain_width / wave_count`
- Wave generates Polyline Items with `feature.type="engrave"`, which route to engraves bucket in v1 hints
- Polyline geometry (points) is preserved through RemovalIntent metadata and emitted in v1 hint geometry
- Deterministic shape IDs use resolver-level counter (`_shape_counter`) instead of `id(node)`

**Files modified:**
- `pml/compositional_parser.py` — Added generator keyword parsing
- `layout_ast/compositional.py` — Added AST node types (ProfileGen, PocketGen, etc.)
- `resolution/layout_resolver.py` — Added handler methods for each generator node
- `pml/compositional_formatter.py` — Added formatting for generator nodes
- `adapters/ast_to_removal.py` — Handle engrave polylines, bevel, chamfer, wave features
- `adapters/removal_to_planner.py` — Route feature types to correct v1 hint buckets
- `adapters/hints_to_removal.py` — Preserve polyline points in metadata
- `generators/area/wave.py` — Implement wave_count parameter

---

## Stage 13: Missing Generators and Utilities

**Goal:** Extract algorithms from recipes into reusable generators and domain utilities.

### Existing Generators (Already Implemented)

The following generators already exist and should **not** be reimplemented:

| Generator | Location | Parameters |
|-----------|----------|------------|
| `flat_pocket_generator` | `generators/area/flat.py` | `FlatPocketParams` |
| `wave_generator` | `generators/area/wave.py` | `WaveParams` (amplitude, wavelength, depth, direction, phase) |
| `grid_generator` | `generators/area/grid.py` | `GridParams` |
| `raised_panel_generator` | `generators/area/raised_panel.py` | `RaisedPanelParams` |
| `profile_generator` | `generators/loop/profile.py` | `ProfileParams` |
| `bead_generator` | `generators/loop/bead.py` | `BeadParams` |
| `chamfer_generator` | `generators/loop/chamfer.py` | `ChamferParams` |
| `svg_stamp_generator` | `generators/svg/stamp.py` | `SVGPathParams` |

**Note:** Recipe 27 (Wave Texture) should be refactored to use the existing `wave_generator` rather than its inline algorithm.

### Generators to Add

Based on recipe analysis, only the following generators are actually missing:

#### `line_pattern_generator`

Creates parallel line grooves across a domain at arbitrary angles.

```python
@dataclass(frozen=True)
class LinePatternParams(BaseParams):
    angle_deg: float = 0.0  # 0=horizontal, 90=vertical, 45=diagonal
    spacing_mm: float = 25.0
    line_width_mm: float = 4.0
    depth_mm: float = 3.0

def line_pattern_generator(
    domain: Domain,
    params: LinePatternParams,
) -> list[Item]:
    """Generate parallel line grooves at specified angle."""
```

Replaces: Recipe 28 (Diamond Lattice) inline diagonal line algorithm

#### `concentric_border_generator`

Creates nested contour-following borders (inset loops).

```python
@dataclass(frozen=True)
class ConcentricBorderParams(BaseParams):
    insets_mm: tuple[float, ...]  # (15.0, 30.0, 45.0)
    groove_width_mm: float = 3.0
    depth_mm: float = 2.0

def concentric_border_generator(
    domain: Domain,
    params: ConcentricBorderParams,
) -> list[Item]:
    """Generate concentric groove borders following domain contour."""
```

Replaces: Recipe 25 (Decorative Border) inline subtract loop

### Domain Utilities to Add

#### `Domain.from_arch()`

Factory for arch-topped shapes.

```python
@classmethod
def from_arch(
    cls,
    width_mm: float,
    height_mm: float,
    arch_radius_mm: float,
    center: tuple[float, float] | None = None,
    arc_segments: int = 40,
) -> Domain:
    """Create a rectangular domain with an arched top."""
```

Replaces: Recipe 30 (Cathedral Arch) `_arch_outline()` function

#### `arc_points()` utility

Add to `core/geometry.py`:

```python
def arc_points(
    center: tuple[float, float],
    radius: float,
    start_deg: float,
    end_deg: float,
    segments: int = 20,
) -> list[tuple[float, float]]:
    """Generate points along a circular arc."""
```

#### `split_horizontal_with_gaps()`

Add to `Domain`:

```python
def split_horizontal_with_gaps(
    self,
    n: int,
    gap_mm: float,
) -> tuple[MultiDomain, MultiDomain]:
    """Split domain and return (cells, gaps) separately."""
```

Replaces: Recipe 26 (Faux Shutter) `_gap_domains_from_split()` function

### Polygon Utilities

Add to `generators/utils.py`:

```python
def shapely_to_item(
    polygon: Polygon,
    feature_type: str,
    depth_mm: float,
    shape_id: str,
) -> Item:
    """Convert a Shapely Polygon to a LayoutAST Item."""
```

Replaces: Recipes 27, 28 inline `_polygon_item()` functions

### Implementation

**Files to create:**
- `generators/area/line_pattern.py` — `line_pattern_generator`
- `generators/area/concentric_border.py` — `concentric_border_generator`
- `generators/utils.py` — `shapely_to_item` utility

**Files to modify:**
- `generators/__init__.py` — Export new generators
- `generators/base.py` — Add `LinePatternParams`, `ConcentricBorderParams`
- `domains/domain.py` — Add `from_arch()`, `split_horizontal_with_gaps()`
- `core/geometry.py` — Add `arc_points()`

**Tests:**
- Add tests to `tests/test_generators.py` for each new generator
- Add tests to `tests/test_domain.py` for `from_arch()` and gap extraction

**Run:** `python -m tests.test_generators && python -m tests.test_domain`

**Dependencies:** Stage 12 (PML) should define keywords these generators will back

### Implementation Notes (Completed 2026-01-18)

**Files created:**
- `generators/area/line_pattern.py` — `line_pattern_generator` with `local_coords` parameter
- `generators/area/concentric_border.py` — `concentric_border_generator` with overflow handling
- `generators/utils.py` — `shapely_to_item()`, `iter_polygons()` utilities

**Files modified:**
- `generators/__init__.py` — Export new generators and params
- `generators/area/__init__.py` — Export new area generators
- `generators/base.py` — Added `LinePatternParams`, `ConcentricBorderParams`
- `domains/domain.py` — Added `from_arch()`, `from_polygon()`, `split_horizontal_with_gaps()`
- `core/geometry.py` — Added `arc_points()`

**Key implementation details:**
- `line_pattern_generator` supports `local_coords: bool = False` parameter for domain-relative angles (matching `grid_generator`/`wave_generator` patterns)
- `concentric_border_generator` skips rings when groove width overflows available space (instead of silently producing full pockets)
- Both generators use `shapely_to_item()` for consistent Polygon → Item conversion
- `iter_polygons()` handles Polygon, MultiPolygon, and GeometryCollection uniformly

**Tests added:**
- `tests/test_generators.py` — 15 new tests for line_pattern, concentric_border, and utilities
- `tests/test_domain.py` — 12 new tests for from_arch, split_horizontal_with_gaps, arc_points

**Test results:** 71 generator tests, 103 domain tests, 6 edge tests — all passing

---

## Stage 14: Recipe Cleanup

**Goal:** Refactor recipes 21-30 to use framework generators and PML.

### Before (Current State)

Recipes contain inline algorithms:

```python
# Recipe 27 - 100+ lines of numpy, shapely, manual Item construction
def build_ast():
    for wave_idx, base_y in enumerate(base_ys):
        xs = _linspace(x_min, x_max, samples)
        wave_line = LineString(points)
        wave_band = wave_line.buffer(GROOVE_WIDTH_MM / 2)
        # ... manual polygon iteration and Item creation
```

### After (Target State)

Recipes become declarative PML + trivial Python runner:

**design.pml:**
```pml
sheet 300mm 300mm 19mm

panel Rect 300mm 300mm center 150mm 150mm
    profile outside through
    wave count 5 amplitude 10mm wavelength 60mm groove 3mm depth 2mm
```

**example.py:**
```python
def main():
    pml = (Path(__file__).parent / "design.pml").read_text()
    ast = parse_pml(pml)
    write_recipe_outputs(ast, Path(__file__).parent / "output")
```

### Migration Checklist

| Recipe | Current Issue | Required Generator/Utility |
|--------|---------------|---------------------------|
| 21 | OK - uses framework | None |
| 22 | OK - uses framework | None |
| 23 | OK - uses framework | None |
| 24 | OK - uses framework | None |
| 25 | Inline subtract loop | `concentric_border_generator` |
| 26 | Inline gap extraction | `split_horizontal_with_gaps` |
| 27 | Inline wave algorithm | Refactor to use existing `wave_generator` |
| 28 | Inline diagonal lines | `line_pattern_generator` |
| 29 | OK - uses framework | None |
| 30 | Inline arch points | `Domain.from_arch()` |

### Success Criteria

- No recipe contains `math.sin`, `LineString.buffer()`, or manual `Item()` construction
- All recipes have a `design.pml` as the source of truth
- `example.py` files are under 20 lines each
- All recipes produce identical output before/after migration

### Implementation

**Files to modify:**
- `docs/recipes/25_decorative_border_panel/` — Replace with PML + trivial runner
- `docs/recipes/26_faux_shutter_panel/` — Replace with PML + trivial runner
- `docs/recipes/27_wave_texture_panel/` — Replace with PML + trivial runner
- `docs/recipes/28_diamond_lattice_panel/` — Replace with PML + trivial runner
- `docs/recipes/30_cathedral_arch_door/` — Replace with PML + trivial runner

**Files to keep (already clean):**
- Recipes 21, 22, 23, 24, 29 — Only convert to PML format

**Tests:**
- Run each recipe and compare output to pre-migration baseline
- Verify SVG preview matches visually

**Run:** `for d in docs/recipes/2*/; do python "$d/example.py"; done`

**Dependencies:** Stage 12 (PML), Stage 13 (Missing Generators)

---

## Priority Order

1. **Stage 10 (Variable-Depth)** — Unblocks proper bevel/chamfer CAM support
2. **Stage 11 (Local-Coordinate Splits)** — Enables rotated panel designs
3. **Stage 12 (PML Generators)** — Makes the system declarative
4. **Stage 13 (Missing Generators)** — Adds generators needed by recipes
5. **Stage 14 (Recipe Cleanup)** — Refactor recipes 21-30 to use new generators and PML

---

## Related Documents

- [domain_generator_design.md](domain_generator_design.md) — Stages 1-9 (implemented)
- [README.md](../README.md) — Architecture overview
- [CLAUDE.md](../CLAUDE.md) — Development guide
