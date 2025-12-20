# mill_ui Ground Truth Report

**Purpose:** Factual documentation of how the system actually works today, extracted from source code.

**Date:** 2025-12-19

**Scope:** Complete pipeline from PML input to G-code output, data models, coordinate systems, validation coverage, and test infrastructure.

---

## Table of Contents

1. [Core Data Model (Verbatim)](#1-core-data-model-verbatim)
2. [Canonical Execution Path](#2-canonical-execution-path)
3. [Planner Hint Schema (Concrete)](#3-planner-hint-schema-concrete)
4. [Coordinate, Units, and Conventions](#4-coordinate-units-and-conventions)
5. [Validation Coverage](#5-validation-coverage)
6. [Golden End-to-End Trace](#6-golden-end-to-end-trace)
7. [Duplicate or Legacy Paths](#7-duplicate-or-legacy-paths)
8. [Test Coverage Map](#8-test-coverage-map)
9. [Summary for Developers](#summary-for-developers)

---

## 1. Core Data Model (Verbatim)

### 1.1 layout_ast/layout.py - Core Dataclasses

**Sheet** ([layout_ast/layout.py:12-17](layout_ast/layout.py#L12-L17)):
```python
@dataclass(frozen=True)
class Sheet:
    """Sheet stock specification."""
    width_mm: float
    height_mm: float
    thickness_mm: float
```

**Placement** ([layout_ast/layout.py:20-23](layout_ast/layout.py#L20-L23)):
```python
@dataclass(frozen=True)
class Placement:
    """Item placement on sheet."""
    center_xy_mm: tuple[float, float]
```

**Geometry** ([layout_ast/layout.py:26-32](layout_ast/layout.py#L26-L32)):
```python
@dataclass(frozen=True)
class Geometry:
    """Shape geometry specification."""
    # Minimal representation - specific fields depend on shape type
    # Rect uses w_mm, h_mm
    # Circle uses diameter_mm or radius_mm
    data: dict[str, Any]
```

**Feature** ([layout_ast/layout.py:35-42](layout_ast/layout.py#L35-L42)):
```python
@dataclass(frozen=True)
class Feature:
    """CAM feature specification (profile, pocket, hole, engrave)."""
    type: str
    depth: str | float  # "through" or numeric depth_mm
    side: str | None = None  # "inside" | "outside" | "on" for profiles
    depth_mm: float | None = None  # Alternative to depth for numeric values
```

**Item** ([layout_ast/layout.py:44-58](layout_ast/layout.py#L44-L58)):
```python
@dataclass(frozen=True)
class Item:
    """Layout item (shape or template).

    For shapes: kind="shape", requires geometry, placement, feature
    For templates: kind="template", requires params, id is optional
    """
    kind: str  # "shape" | "template"
    type: str  # Shape type: "Rect", "Circle", etc. or template name
    geometry: Geometry | None = None  # Required for shapes, unused for templates
    placement: Placement | None = None  # Required for shapes, optional for templates
    feature: Feature | None = None  # Required for shapes, unused for templates
    params: dict[str, Any] | None = None  # Required for templates, unused for shapes
    shape_id: str | None = None  # Optional identifier for shapes
    id: str | None = None  # Optional identifier for templates
```

**LayoutAST** ([layout_ast/layout.py:61-74](layout_ast/layout.py#L61-L74)):
```python
@dataclass(frozen=True)
class LayoutAST:
    """Canonical layout AST.

    Captures both shape-based layouts and template-based layouts (v1 structure).
    """
    sheet: Sheet
    items: tuple[Item, ...]
    # Top-level configuration from v1 layouts
    project: str | None = None
    kerf_width_mm: float | None = None
    cam: dict[str, Any] | None = None
    layout: dict[str, Any] | None = None
    config: dict[str, Any] = field(default_factory=dict)
```

**Note:** The codebase does not have separate type classes for Rect, Circle, RoundedRect, Line, SplinePath. These are identified by `Item.type` string and their parameters live in `Geometry.data` dict.

### 1.2 ir/removal_intent.py - Core IR Dataclasses

**Bounds2D** ([ir/removal_intent.py:12-28](ir/removal_intent.py#L12-L28)):
```python
@dataclass(frozen=True)
class Bounds2D:
    """2D bounding box in XY plane.

    Represents the planar extent of a removal region.
    """
    x_min: float
    x_max: float
    y_min: float
    y_max: float

    def __post_init__(self):
        """Validate bounds."""
        if self.x_max < self.x_min:
            raise ValueError(f"x_max ({self.x_max}) < x_min ({self.x_min})")
        if self.y_max < self.y_min:
            raise ValueError(f"y_max ({self.y_max}) < y_min ({self.y_min})")
```

**Allowance** ([ir/removal_intent.py:31-40](ir/removal_intent.py#L31-L40)):
```python
@dataclass(frozen=True)
class Allowance:
    """Material allowance specification for removal operations.

    Defines how much material to leave or remove beyond nominal boundaries.
    """
    inside: float = 0.0  # Material to leave inside boundary (negative = remove more)
    outside: float = 0.0  # Material to leave outside boundary (negative = remove more)
    on: float = 0.0  # Material to leave on boundary (for 'on' side profiles)
    kerf_compensation: float = 0.0  # Tool kerf compensation (typically kerf_width_mm / 2)
```

**TabConstraint** ([ir/removal_intent.py:43-48](ir/removal_intent.py#L43-L48)):
```python
@dataclass(frozen=True)
class TabConstraint:
    """Tab (holding bridge) specification."""
    count: int  # Number of tabs
    height_mm: float  # Tab height (extends up from z_bottom)
    width_mm: float  # Tab width along boundary
```

**KeepoutRegion** ([ir/removal_intent.py:51-55](ir/removal_intent.py#L51-L55)):
```python
@dataclass(frozen=True)
class KeepoutRegion:
    """Region where toolpath must not enter."""
    bounds: Bounds2D
    reason: str = "keepout"  # Descriptive reason (e.g., "clamp zone", "fixture")
```

**Island** ([ir/removal_intent.py:58-62](ir/removal_intent.py#L58-L62)):
```python
@dataclass(frozen=True)
class Island:
    """Material island within removal region (material to preserve)."""
    bounds: Bounds2D
    label: str | None = None
```

**EdgeTreatment** ([ir/removal_intent.py:65-78](ir/removal_intent.py#L65-L78)):
```python
@dataclass(frozen=True)
class EdgeTreatment:
    """Edge treatment specification for finish operations.

    Describes decorative or functional edge modifications that affect
    toolpath planning (multi-pass, specialized bits, etc.).
    """
    type: str  # "fillet", "chamfer", "allowance"
    # For fillet/chamfer
    radius_mm: float | None = None  # Fillet radius
    distance_mm: float | None = None  # Chamfer distance
    # For allowance (multi-pass semantics)
    rough_allowance_mm: float | None = None  # Stock to leave for rough pass
    finish_allowance_mm: float | None = None  # Final allowance after finish pass
```

**Constraints** ([ir/removal_intent.py:81-89](ir/removal_intent.py#L81-L89)):
```python
@dataclass(frozen=True)
class Constraints:
    """Constraints on removal operation."""
    tabs: TabConstraint | None = None
    keepouts: tuple[KeepoutRegion, ...] = field(default_factory=tuple)
    islands: tuple[Island, ...] = field(default_factory=tuple)
    edge_treatment: EdgeTreatment | None = None  # Edge finish/decorative hints
    tolerance_mm: float = 0.1  # Allowable deviation from nominal geometry
    safe_z_mm: float = 5.0  # Safe Z height for rapid moves
```

**RemovalIntent** ([ir/removal_intent.py:92-110](ir/removal_intent.py#L92-L110)):
```python
@dataclass(frozen=True)
class RemovalIntent:
    """Canonical specification for material removal.

    Represents *what* volume to remove, independent of *how* (toolpath strategy).
    This is the fundamental IR for CAM operations.
    """
    region_id: str  # Unique identifier for this removal region
    bounds: Bounds2D  # Planar extent of removal
    z_top: float  # Top Z coordinate (typically 0.0 for stock surface)
    z_bottom: float  # Bottom Z coordinate (negative for removal depth)
    allowance: Allowance = field(default_factory=Allowance)  # Material allowance
    constraints: Constraints = field(default_factory=Constraints)  # Operational constraints
    metadata: dict[str, Any] = field(default_factory=dict)  # Optional metadata (shape_id, feature type, etc.)

    def __post_init__(self):
        """Validate removal intent."""
        if self.z_bottom > self.z_top:
            raise ValueError(f"z_bottom ({self.z_bottom}) > z_top ({self.z_top})")
```

---

## 2. Canonical Execution Path

Based on the source code, here is the actual call chain from compositional PML to G-code:

### Step 1: Parse Compositional PML
- **Entry function**: `parse_compositional_pml(text: str)` in [pml/compositional_parser.py](pml/compositional_parser.py)
- **Input**: PML text string
- **Output**: `CompositionalLayoutAST` (hierarchical AST with layout managers)

### Step 2: Resolve Layout
- **Entry function**: `resolve_layout(comp_ast: CompositionalLayoutAST)` in [resolution/layout_resolver.py](resolution/layout_resolver.py)
- **Input**: `CompositionalLayoutAST`
- **Output**: `LayoutAST` (flat AST with absolute coordinates)
- **Process**: Applies layout managers (frame, inset, grid), expands components, computes absolute positions

### Step 3: Convert AST → RemovalIntent
- **Entry function**: `ast_to_removal_intents(ast: LayoutAST)` in [adapters/ast_to_removal.py:22](adapters/ast_to_removal.py#L22)
- **Input**: `LayoutAST`
- **Output**: `list[RemovalIntent]`
- **Process**: For each `Item` in AST, calls `item_to_removal_intent()` which converts to intermediate hint dict, then routes to feature-specific converters (`profile_hint_to_removal_intent`, `pocket_hint_to_removal_intent`, etc.)

### Step 4: Convert RemovalIntent → Planner Hints
- **Entry function**: `removal_intents_to_v1_hints(intents, kerf_width_mm, min_channel_width_mm)` in [adapters/removal_to_planner.py:86](adapters/removal_to_planner.py#L86)
- **Input**: `list[RemovalIntent]`, kerf_width_mm, min_channel_width_mm
- **Output**: Planner hints dict with structure:
  ```python
  {
      "profiles": [...],
      "pockets": [...],
      "holes": [...],
      "engraves": [...],
      "kerf_width_mm": float,
      "min_channel_width_mm": float
  }
  ```

### Step 5: Plan Passes
- **Entry function**: `plan_passes(hints, config, tool_db, material, machine, stock, safe_z, prime_spindle, profile_opts)` in [cam/planner/passes/__init__.py:112](cam/planner/passes/__init__.py#L112)
- **Input**: Planner hints dict, config, tool database, material/machine/stock models
- **Output**: `tuple[List[Dict[str, Any]], Dict[str, Any]]` - list of pass records and summary
- **Process**: Calls `plan_pocket_passes()`, `plan_hole_passes()`, `plan_engrave_passes()`, then processes profiles with merge/seam logic

### Step 6: Generate G-code
- **Entry function**: `write_gcode(moves, unit, prec, safe_z, header, footer)` in [cam/post/gcode.py:8](cam/post/gcode.py#L8)
- **Input**: List of move dicts from pass records
- **Output**: G-code string
- **Process**: Delegates to `native_core.post_gcode()` (C++ native backend)

---

## 3. Planner Hint Schema (Concrete)

Based on [adapters/removal_to_planner.py](adapters/removal_to_planner.py), here is the exact structure:

### Example: Rectangle outside profile (through-cut) and pocket (6mm deep)

**Profile hint** (from [adapters/removal_to_planner.py:53-74](adapters/removal_to_planner.py#L53-L74)):
```python
{
    "id": "outer",
    "shape": "Rect",
    "geometry": {"w_mm": 400.0, "h_mm": 600.0},
    "center_xy_mm": (225.0, 325.0),
    "depth_mm": 19.0,
    "side": "outside",
    # Optional:
    "tabs": {
        "count": 4,
        "height_mm": 3.0,
        "width_mm": 10.0
    }
}
```

**Pocket hint** (from [adapters/removal_to_planner.py:76-79](adapters/removal_to_planner.py#L76-L79)):
```python
{
    "id": "panel",
    "shape": "Rect",
    "geometry": {"w_mm": 300.0, "h_mm": 500.0},
    "center_xy_mm": (225.0, 325.0),
    "depth_mm": 6.0,
    # Optional:
    "start_depth_mm": 0.0  # Only if z_top != 0
}
```

**Top-level hints structure** (from [adapters/removal_to_planner.py:131-139](adapters/removal_to_planner.py#L131-L139)):
```python
{
    "units": "mm",
    "kerf_width_mm": 3.175,
    "min_channel_width_mm": 6.0,
    "profiles": [<profile hints>],
    "pockets": [<pocket hints>],
    "holes": [<hole hints>],
    "engraves": [<engrave hints>]
}
```

### Where Consumed in Planner

- **Profiles**: [cam/planner/passes/__init__.py:149-227](cam/planner/passes/__init__.py#L149-L227)
  - Reads `hints.get("profiles")`
  - Extracts: `geometry`, `center_xy_mm`, `depth_mm`, `side`, `tabs`

- **Pockets**: [cam/planner/passes/pocket.py:48-113](cam/planner/passes/pocket.py#L48-L113)
  - Reads `hints.get("pockets")`
  - Extracts: `shape`, `geometry`, `depth_mm`, `start_depth_mm`

- **Holes**: [cam/planner/passes/pocket.py:122-150](cam/planner/passes/pocket.py#L122-L150)
  - Reads `hints.get("holes")`
  - Extracts: `geometry.diameter_mm`, `center_xy_mm`, `depth_mm`

---

## 4. Coordinate, Units, and Conventions

### Units
- **All layers**: Millimeters exclusively ([layout_ast/layout.py:3](layout_ast/layout.py#L3), [ir/removal_intent.py:3](ir/removal_intent.py#L3))
- **No conversions**: System is internally consistent, all dimensions in mm
- **G-code output**: [cam/post/gcode.py:8](cam/post/gcode.py#L8) supports `unit='mm'` or `unit='inch'` parameter for output only

### XY Coordinate System
- **PML/LayoutAST**: Absolute coordinates with center-based placement
  - `Placement.center_xy_mm`: tuple of (x, y) in millimeters
  - Origin is **lower-left** based on stock model: [cam/model/stock.py:5](cam/model/stock.py#L5) `origin='lower_left_top'`
- **RemovalIntent**: Bounds-based (x_min, x_max, y_min, y_max)
  - Converted from center coordinates in adapters
- **Compositional AST**: Normalized coordinates (0.0-1.0) relative to parent region
  - Resolved to absolute coordinates by layout resolver

### Z-axis Convention
From [ir/removal_intent.py:3](ir/removal_intent.py#L3):
- **Positive Z**: Up (away from material)
- **Negative Z**: Down (into material)
- **z_top**: Typically 0.0 (stock surface) [ir/removal_intent.py:101](ir/removal_intent.py#L101)
- **z_bottom**: Negative value for depth (e.g., -19.0 for through-cut in 19mm stock)
- **Depth calculation**: `z_top - z_bottom` [ir/removal_intent.py:114](ir/removal_intent.py#L114)

### Coordinate Reference
- **Sheet dimensions**: Width × Height × Thickness
- **Item placement**: Center coordinates (not corner)
- **Profile side offset**: Applied in planner based on tool diameter and `side` parameter

---

## 5. Validation Coverage

### IR-Level Validation
From [validation/removal_checks.py](validation/removal_checks.py):

1. **`check_overlap(intents)`** [validation/removal_checks.py:11-31](validation/removal_checks.py#L11-L31)
   - Detects overlapping XYZ regions between RemovalIntents
   - Uses 3D bounding box intersection test
   - Returns errors for each overlap pair

2. **`check_depth_feasibility(intent, sheet_thickness_mm)`** [validation/removal_checks.py:34-77](validation/removal_checks.py#L34-L77)
   - Validates `z_top >= z_bottom`
   - Warns if cutting deeper than sheet thickness
   - Suggests review for very shallow cuts (< 0.5mm)

3. **`check_toolability(intent, available_tools)`** [validation/removal_checks.py:80-130](validation/removal_checks.py#L80-L130)
   - Warns about very small features (< 1mm) requiring micro tooling
   - If tools provided: checks if any tool diameter fits feature size
   - Errors if no tool can reach the feature
   - Suggests smaller tools if options are limited

### What is NOT Validated at IR Level
- **Geometric collision detection**: Only bounding box overlap, not exact geometry intersection
- **Tool reach in constrained spaces**: e.g., pocket corners with specific tool diameter
- **Multi-pass depth strategy**: Whether stepdown is appropriate for material
- **Feed/speed validation**: Material/tool compatibility
- **Fixture/clamp interference**: Physical setup constraints beyond keepout regions
- **Tab placement feasibility**: Whether tab locations are geometrically valid
- **Path continuity**: Whether toolpaths can be executed without excessive retracts
- **Exact kerf compensation**: Only allowances stored, not validated against tool diameter

### Later Validation (Planner/Native Backend)
- Tool selection based on required width ([cam/planner/passes/pocket.py:58-62](cam/planner/passes/pocket.py#L58-L62))
- Stepdown/stepover calculation per tool ([cam/planner/passes/pocket.py:70-71](cam/planner/passes/pocket.py#L70-L71))
- Hole drilling vs boring strategy selection ([cam/planner/passes/pocket.py:135-149](cam/planner/passes/pocket.py#L135-L149))
- Profile merge feasibility (epsilon-based edge matching)

---

## 6. Golden End-to-End Trace

**Input PML:**
```pml
sheet 450mm 650mm 19mm

rect outer profile through outside
    inset 50mm
        rect inner pocket 6mm
```

### Step 1: Parsed Compositional AST
```
Sheet: 450.0x650.0x19.0mm
Root node type: Panel
Root children: 1
  Child 0: Rect (id=outer)
    Feature: profile through outside
    Subchild 0: Inset (amount=50mm)
      Subchild 0: Rect (id=inner)
        Feature: pocket 6mm
```

### Step 2: Resolved Flat LayoutAST
```python
LayoutAST(
    sheet=Sheet(width_mm=450.0, height_mm=650.0, thickness_mm=19.0),
    items=(
        Item(
            kind='shape',
            type='Rect',
            geometry=Geometry(data={'w_mm': 450.0, 'h_mm': 650.0}),
            placement=Placement(center_xy_mm=(225.0, 325.0)),
            feature=Feature(type='profile', depth='through', side='outside'),
            shape_id='outer'
        ),
        Item(
            kind='shape',
            type='Rect',
            geometry=Geometry(data={'w_mm': 350.0, 'h_mm': 550.0}),
            placement=Placement(center_xy_mm=(225.0, 325.0)),
            feature=Feature(type='pocket', depth=6.0, side=None),
            shape_id='inner'
        )
    )
)
```

### Step 3: RemovalIntent IR
```python
[
    RemovalIntent(
        region_id='profile_outer',
        bounds=Bounds2D(x_min=0.0, x_max=450.0, y_min=0.0, y_max=650.0),
        z_top=0.0,
        z_bottom=-19.0,
        allowance=Allowance(inside=0.0, outside=0.0, on=0.0, kerf_compensation=0.0),
        constraints=Constraints(tabs=None, keepouts=(), islands=(), tolerance_mm=0.1, safe_z_mm=5.0),
        metadata={'hint_type': 'profile', 'shape': 'Rect', 'side': 'outside', 'original_id': 'outer'}
    ),
    RemovalIntent(
        region_id='pocket_inner',
        bounds=Bounds2D(x_min=50.0, x_max=400.0, y_min=50.0, y_max=600.0),
        z_top=-0.0,
        z_bottom=-6.0,
        allowance=Allowance(inside=0.0, outside=0.0, on=0.0, kerf_compensation=0.0),
        constraints=Constraints(tabs=None, keepouts=(), islands=(), tolerance_mm=0.1, safe_z_mm=5.0),
        metadata={'hint_type': 'pocket', 'shape': 'Rect', 'original_id': 'inner'}
    )
]
```

### Step 4: Planner Hints
```json
{
  "units": "mm",
  "kerf_width_mm": 3.175,
  "min_channel_width_mm": 6.0,
  "profiles": [
    {
      "id": "outer",
      "shape": "Rect",
      "geometry": {"w_mm": 450.0, "h_mm": 650.0},
      "center_xy_mm": [225.0, 325.0],
      "depth_mm": 19.0,
      "side": "outside"
    }
  ],
  "pockets": [
    {
      "id": "inner",
      "shape": "Rect",
      "geometry": {"w_mm": 350.0, "h_mm": 550.0},
      "center_xy_mm": [225.0, 325.0],
      "depth_mm": 6.0
    }
  ],
  "holes": [],
  "engraves": []
}
```

### Step 5: Planner Operations
```
Total passes: 2

Pass 0: pocket
  Tool: 1_8_endmill (diameter=3.175mm)
  Move count: 8660
  Filename: pocket-3.17mm.nc

Pass 1: profile
  Tool: 1_8_endmill (diameter=3.175mm)
  Move count: 252
  Filename: profile-3.17mm.nc
```

### Step 6: G-code Output (First 30 Lines)
```gcode
  1: G90
  2: G21
  3: G17
  4: (BEGIN rough pocket cleanup=0.250mm sd=1.587 so=1.270)
  5: (pocket_raster so=1.270 sd=1.587 depth=6.000)
  6: M3 S14000
  7: F900.0
  8: G0 X51.838 Y51.837 Z5.000
  9: G1 Z-1.587 F300.0
 10: F900.0
 11: G1 X398.163 Y51.837 F900.0
 12: G0 Z5.000
 13: G0 X398.163 Y53.107 Z5.000
 14: G1 Z-1.587 F300.0
 15: F900.0
 16: G1 X51.838 Y53.107 F900.0
 17: G0 Z5.000
 18: G0 X51.838 Y54.377 Z5.000
 19: G1 Z-1.587 F300.0
 20: F900.0
 21: G1 X398.163 Y54.377 F900.0
 22: G0 Z5.000
 23: G0 X398.163 Y55.647 Z5.000
 24: G1 Z-1.587 F300.0
 25: F900.0
 26: G1 X51.838 Y55.647 F900.0
 27: G0 Z5.000
 28: G0 X51.838 Y56.917 Z5.000
 29: G1 Z-1.587 F300.0
 30: F900.0
... (8634 more lines for pocket pass)
... (252 more lines for profile pass)
```

**G-code Analysis:**
- Line 6: Spindle start at 14000 RPM
- Lines 8-30: Pocket raster strategy with 1.27mm stepover, 1.587mm stepdown
- Rapid moves (G0) at Z=5.0mm (safe_z)
- Plunge moves (G1 Z-1.587) at 300mm/min feed rate
- Horizontal cuts at 900mm/min feed rate

---

## 7. Duplicate or Legacy Paths

### Current AST → RemovalIntent Conversion Paths

1. **Canonical path** ([adapters/ast_to_removal.py](adapters/ast_to_removal.py)):
   - `ast_to_removal_intents(ast)` → calls `item_to_removal_intent(item, sheet_thickness_mm)`
   - Converts `Item` to intermediate hint dict, then delegates to feature-specific converters
   - **Status**: Active, documented as canonical in README

2. **Hint-based conversion** ([adapters/hints_to_removal.py](adapters/hints_to_removal.py)):
   - Functions: `profile_hint_to_removal_intent()`, `pocket_hint_to_removal_intent()`, `hole_hint_to_removal_intent()`, `engrave_hint_to_removal_intent()`
   - Also contains `item_to_removal_intent()` that directly converts `Item`
   - **Status**: Dual purpose - used by canonical path AND independently for legacy v1 hints

### Observation
The canonical adapter [adapters/ast_to_removal.py](adapters/ast_to_removal.py) delegates to hint-based converters in [adapters/hints_to_removal.py](adapters/hints_to_removal.py). This creates an intermediate hint dict ([adapters/ast_to_removal.py:99-105](adapters/ast_to_removal.py#L99-L105)) even when starting from `Item`, which is then converted by the hint converters.

**Semantics duplication:**
- Both files contain logic to convert Item → RemovalIntent
- The hint dict serves as a compatibility layer between v1 and v2
- This is intentional for incremental migration, not accidental duplication

### Reverse Adapter
([adapters/removal_to_planner.py](adapters/removal_to_planner.py)):
- `removal_intent_to_v1_hint()`, `removal_intents_to_v1_hints()`
- Converts RemovalIntent back to v1 hint format for planner consumption
- **Status**: Active, necessary for planner integration

### Conclusion
**No deprecated/unused adapters identified** - all conversion paths are actively used in the pipeline.

---

## 8. Test Coverage Map

### Pipeline Boundary Coverage

| Pipeline Stage | Function/Module | Test Files | Status |
|---------------|----------------|------------|--------|
| **Parsing (Flat PML)** | `parse_pml()` | 3 files | ✅ Tested |
| **Parsing (Compositional PML)** | `parse_compositional_pml()` | 18 files | ✅ Well tested |
| **Parsing (JSON)** | `LayoutAST.from_json()` | 4 files | ✅ Tested |
| **Resolution** | `resolve_layout()` | 19 files | ✅ Well tested |
| **AST → IR (canonical)** | `ast_to_removal_intents()` | 0 files | ⚠️ **NOT TESTED** |
| **AST → IR (per-item)** | `item_to_removal_intent()` | 8 files | ✅ Tested |
| **Hints → IR** | `profile/pocket/hole/engrave_hint_to_removal_intent()` | 11 files | ✅ Well tested |
| **IR → Hints** | `removal_intents_to_v1_hints()` | 9 files | ✅ Well tested |
| **IR Validation** | `check_overlap/depth/toolability()` | 3 files | ✅ Tested |
| **Planner** | `plan_passes()` | 7 files | ✅ Tested |
| **G-code** | `write_gcode()` | 5 files | ✅ Tested |

### Test File Categories

**Parsing Tests:**
- `tests/run_pml_tests.py`, `tests/test_pml_roundtrip.py` - Flat PML
- `tests/run_compositional_pml_tests.py`, `tests/test_compositional_pml.py` - Compositional PML
- `tests/test_ast_json_parse.py`, `tests/test_ast_roundtrip.py` - JSON parsing

**Resolution Tests:**
- `tests/run_resolution_tests.py`, `tests/test_layout_resolution.py` - Layout resolution
- `tests/run_split_layout_tests.py`, `tests/test_split_layout.py` - Split layout manager
- `tests/run_spline_tests.py`, `tests/test_spline_paths.py` - Spline path sampling
- `tests/run_polyline_path_tests.py`, `tests/test_polyline_path.py` - Polyline conversion

**AST → IR Tests:**
- `tests/run_edge_tests.py`, `tests/test_edge_intent.py` - Edge allowance (profile side)
- `tests/run_keepout_tests.py`, `tests/test_keepout_islands.py` - Keepout/island constraints
- `tests/test_removal_intent_model.py` - RemovalIntent model validation

**Adapter Tests:**
- `tests/run_hints_adapter_tests.py`, `tests/test_hints_adapter.py` - Hints → IR conversion
- `tests/run_planner_adapter_tests.py`, `tests/test_planner_adapter.py` - IR → Hints conversion

**Validation Tests:**
- `tests/run_validation_tests.py`, `tests/test_removal_validation.py` - IR validation rules

**End-to-End Tests:**
- `tests/run_gcode_equivalence_tests.py`, `tests/test_gcode_equivalence.py` - G-code equivalence (v1 vs v2)
- `tests/run_shaker_v2_end_to_end.py`, `tests/test_shaker_v2.py` - Shaker template pipeline
- `tests/run_shaker_tests.py` - Shaker template generation

**Other Tests:**
- `tests/test_basic_shapes.py` - Basic shape rendering
- `tests/test_pocket_cleanup.py` - Pocket cleanup strategy (F001)
- `tests/test_blueprint_export.py` - SVG blueprint export

### Broken Tests (Missing Modules)

**cli/introspect.py** - Referenced in [tests/test_cli_dump.py:14](tests/test_cli_dump.py#L14):
```python
from cli.introspect import dump_ast, dump_removal_intent
```

**Impact:** Tests will fail on import. This module is documented in README but not implemented.

**Status:** Module does not exist, tests cannot run.

---

## Summary for Developers

### Extension Points (Verified in Code)

1. **Add new shape**: Extend `_item_geometry_to_bounds()` in [adapters/hints_to_removal.py](adapters/hints_to_removal.py)
2. **Add new feature**: Add feature type to [layout_ast/layout.py:38](layout_ast/layout.py#L38), implement converter in [adapters/hints_to_removal.py](adapters/hints_to_removal.py)
3. **Add new template**: Create class in `templates/`, implement `expand_to_ast()`, register in `templates/__init__.py`
4. **Add IR validation**: Add function to [validation/removal_checks.py](validation/removal_checks.py)
5. **Add planner strategy**: Extend functions in [cam/planner/passes/](cam/planner/passes/)

### Invariants to Preserve

1. **All dimensions are millimeters** - No conversions, no mixed units
2. **Z-axis convention**: positive=up, negative=down, z_top=0.0 for stock surface
3. **RemovalIntent is canonical IR** - Always convert AST → RemovalIntent before planner
4. **Frozen dataclasses** - Use `dataclasses.replace()` for modifications
5. **Bounds from center coordinates** - Items use center placement, bounds computed from geometry
6. **Hint dict compatibility** - Maintain v1 hint structure for planner integration

### Critical Gaps

1. **No exact geometry collision detection** - Only bounding box overlap
2. **No CLI introspection** - `cli/introspect.py` missing, referenced in tests
3. **CAD export partially broken** - `cad/export/step.py` and `svg.py` have import errors
4. **ast_to_removal_intents() not tested** - Canonical entry point has no direct tests (only indirect via item_to_removal_intent)

### Recommended Actions

1. **Implement cli/introspect.py** - Unblock `tests/test_cli_dump.py`
2. **Add direct tests for ast_to_removal_intents()** - Verify canonical entry point
3. **Fix CAD export imports** - Restore `cad/export/step.py` and `svg.py` functionality
4. **Add geometry-level collision detection** - Extend IR validation beyond bounding boxes

---

**This report provides complete factual grounding for the mill_ui system as it exists today.**
