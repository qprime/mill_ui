# mill_ui

**Semantic CAM pipeline for CNC routing with clean separation between intent and execution.**

## What This Is

mill_ui is a Computer-Aided Manufacturing (CAM) system for CNC routers that generates G-code from high-level layout descriptions. Unlike traditional CAM systems that tightly couple geometry to machining strategy, mill_ui uses a semantic intermediate representation (RemovalIntent IR) to separate *what* material to remove from *how* to remove it.

**Pipeline:** `PML/JSON → LayoutAST → RemovalIntent IR → CAM Planner → G-code`

This architecture enables:
- **Extensibility**: Add new shapes, features, or machining strategies independently
- **Testability**: Validate semantics before geometric computation
- **AI-friendliness**: Both human-authored (PML) and AI-generated (JSON) inputs
- **Composability**: Hierarchical layouts with parametric templates

## Why This Architecture

### The Problem
Traditional CAM systems directly translate geometry (rectangles, circles, polylines) into toolpaths. This creates tight coupling:
- Adding a new shape requires understanding machining details
- Validating designs requires executing the planner
- Alternative machining strategies mean duplicating geometry logic

### The Solution: RemovalIntent IR
mill_ui inserts a semantic layer between geometry and machining:

```
Traditional:  Rectangle(w, h) → immediate toolpath generation → G-code
mill_ui:      Rectangle(w, h) → RemovalIntent(bounds, depth, allowances) → toolpath → G-code
```

**RemovalIntent** describes *what* to remove (3D region, depth, tolerances, constraints) without specifying *how*. The CAM planner then chooses strategies (pocket raster, profile offset, drilling) based on tool selection and material properties.

## Quick Start: Shaker Cabinet Door

Here's a complete example showing the pipeline in action.

### Option 1: Flat PML (Explicit Positioning)

**Flat PML** uses absolute coordinates for direct shape placement:

```pml
sheet 450mm 650mm 19mm

rect door:outer at 225mm,325mm size 400mm,600mm profile through outside
rect door:panel at 225mm,325mm size 300mm,500mm pocket 6mm
circle anchor:1 at 95mm,545mm diameter 10mm hole 8mm
circle anchor:2 at 355mm,545mm diameter 10mm hole 8mm
```

**Syntax:** `<shape> <id> at <x>mm,<y>mm size <w>mm,<h>mm <feature>`

**Note:** Flat PML doesn't have a standalone CLI parser. Use compositional PML CLI or parse programmatically:
```python
from skills.mill_ui.pml import parse_pml
ast = parse_pml(pml_text)
```

### Option 2: Compositional PML (Hierarchical Layout)

**Compositional PML** uses relative positioning with layout managers:

```pml
sheet 400.00mm 600.00mm 19.00mm

rect outer profile through outside
    inset 50.00mm
        rect inner pocket 6.00mm
```

**Layout Managers:**
- `frame <width>mm` - Inset border around parent region (auto-generates outer profile)
- `inset <amount>mm` - Uniform inset on all sides
- `place grid <rows> <cols> gap <gap>mm` - Grid-based component placement (requires `use <component>` children)

Run the compositional PML parser:
```bash
PYTHONPATH=/path/to/cliff_ai python3 -m skills.mill_ui.cli.parse_compositional_pml door.pml
PYTHONPATH=/path/to/cliff_ai python3 -m skills.mill_ui.cli.parse_compositional_pml door.pml --resolve --format pml
PYTHONPATH=/path/to/cliff_ai python3 -m skills.mill_ui.cli.parse_compositional_pml door.pml --resolve --format json
```

**Key Difference:** Flat PML requires explicit coordinates (`at X,Y`), compositional PML uses layout managers for relative positioning.

### Option 3: Python Template (Programmatic)

```python
from skills.mill_ui.templates import Shaker
from skills.mill_ui.adapters.ast_to_removal import ast_to_removal_intents

# Generate LayoutAST
ast = Shaker.expand_to_ast(
    params={
        "outer_w": 400.0,
        "outer_h": 600.0,
        "stile_w": 50.0,
        "rail_h": 50.0,
        "panel_recess": 6.0,
    },
    sheet_thickness_mm=19.0
)

# Convert to RemovalIntent IR (canonical AST → IR adapter)
intents = ast_to_removal_intents(ast)

# Generate CAM plan (requires v1 planner backend)
from skills.mill_ui.adapters.removal_to_planner import removal_intents_to_v1_hints
hints = removal_intents_to_v1_hints(
    intents,
    kerf_width_mm=3.175,  # 1/8" bit typical
    min_channel_width_mm=6.0
)
# ... pass hints to planner
```

### What This Produces

**LayoutAST** (semantic structure):
- Sheet: 450×650×19mm
- Item 1: Rectangle, profile feature (outside, through-cut)
- Item 2: Rectangle, pocket feature (6mm depth)

**RemovalIntent IR** (machining semantics):
- Intent 1: Remove region (bounds, z_top=0mm, z_bottom=-19mm, allowance=outside)
- Intent 2: Remove region (bounds, z_top=0mm, z_bottom=-6mm, allowance=inside)

**CAM Plan** (execution strategy):
- Pass 1: Profile outside perimeter with 6mm end mill, multiple depths
- Pass 2: Pocket interior with raster strategy, 6mm depth

## Core Concepts

### 1. RemovalIntent IR

The key innovation. A `RemovalIntent` describes a volumetric removal operation:

```python
@dataclass(frozen=True)
class RemovalIntent:
    region_id: str              # Unique identifier
    bounds: Bounds2D            # XY bounding box
    z_top: float                # Top of material removal (mm)
    z_bottom: float             # Bottom of material removal (mm)
    allowance: Allowance        # Inside/outside/on the geometry
    constraints: Constraints    # Tabs, keepouts, islands, tolerances
    metadata: dict              # Source tracking, debugging info
```

**Why this matters:**
- Validates geometry before expensive path planning
- Enables collision detection at IR level
- Allows multiple planners to share the same IR
- Testable without CAM backend

### 2. LayoutAST

Compositional abstract syntax tree for panel layouts:

```python
@dataclass(frozen=True)
class LayoutAST:
    sheet: Sheet                    # Material dimensions
    items: tuple[Item, ...]         # Shapes, features, placements
```

**Items** can be:
- **Shapes**: Rectangle, Circle, RoundedRect, Line, SplinePath
- **Features**: Profile (inside/outside/on), Pocket, Hole, Engrave
- **Placement**: Absolute positioning (center_xy_mm)

**Compositional semantics** allow hierarchical layouts (see CompositionalLayoutAST below).

### 2.5 CompositionalLayoutAST (Hierarchical Layouts)

For complex layouts, mill_ui provides compositional AST types that enable relative positioning:

**Layout Managers:**
- `Panel` - Root panel node
- `Frame` - Border/frame with inset (auto-generates outer profile)
- `Inset` - Uniform inset on all sides
- `Grid` - Grid layout (rows/cols/gap)
- `Split` - Region subdivision with rails (horizontal bars) and mullions (vertical bars)

**Component System:**
- `ComponentDef` - Define reusable components with parameters
- `UseComponent` - Instantiate components (currently no args, just `use <name>`)
- `Place` - Grid-based component placement (`place grid <rows> <cols>` with `use <component>` children)

**Resolution:**
Compositional AST → Flat LayoutAST via `resolution/layout_resolver.py`, which computes absolute positions from relative layout constraints.

**Files:**
- `layout_ast/compositional.py` - Compositional AST types
- `resolution/layout_resolver.py` - Resolver that flattens hierarchical layouts

**Example with `inset` (manual profile control):**
```pml
rect outer profile through outside
    inset 50.00mm              # Inset 50mm from outer bounds
        rect inner pocket 6mm   # Inner pocket automatically positioned
```

**Example with `frame` (auto-generates profile):**
```pml
rect outer                     # Just the outer bounds (no profile feature)
    frame 50.00mm              # Frame auto-generates outer profile + insets region
        rect inner pocket 6mm   # Inner pocket automatically positioned
```

**Note:** `frame` auto-generates an outer profile, so using `rect outer profile through outside` + `frame` would create two profiles. Use either `rect outer` + `frame`, or `rect outer profile` + `inset`.

### 3. PML: Two Dialects

**Flat PML**: Explicit absolute positioning
```pml
rect outer at 225mm,325mm size 400mm,600mm profile through outside
```

**Compositional PML**: Relative positioning with layout managers
```pml
rect outer profile through outside
    inset 50mm
        rect inner pocket 6mm
```

**JSON**: Direct LayoutAST serialization for AI/programmatic generation
- Verbose but explicit
- 1:1 mapping to AST dataclasses
- Skip parsing, go straight to AST

All three compile to the same LayoutAST, ensuring semantic equivalence.

### 4. CAM Backend Integration

mill_ui retains the v1 CAM planner (proven, stable) as the backend:

```
Current Implementation:
1. LayoutAST.Item → intermediate hint dict (manual conversion)
2. hint dict → RemovalIntent (via profile_hint_to_removal_intent/pocket_hint_to_removal_intent)
3. RemovalIntent → v1 planner hints (via removal_intent_to_v1_hint)
4. v1 hints → CAM planner → G-code
```

The `adapters/` module bridges RemovalIntent to the planner's hint format. This allows:
- Incremental migration (v1 planner works, no need to replace it)
- IR validation before planner execution
- Future: Multiple planner backends targeting the same IR

**Note:** The canonical AST → IR adapter is now available in `adapters/ast_to_removal.py` as `ast_to_removal_intents()`.

## Architecture Principles

### 1. Separation of Concerns
- **Parsing** (PML/JSON → AST): Syntax and structure
- **Resolution** (Compositional AST → Flat AST): Layout computation
- **Semantics** (AST → IR): What to remove, constraints
- **Planning** (IR → CAM): How to remove (toolpaths, strategies)
- **Execution** (CAM → G-code): Machine-specific output

### 2. Semantic Before Geometric
Validate intent (overlaps, invalid depths, constraint violations) before computing expensive geometry (offsets, pockets, toolpaths).

### 3. Test at IR Boundary
Most tests validate AST → IR transformation. This catches errors early without requiring:
- Full CAM planner execution
- Native C++ backends
- G-code parsing

Example: Edge allowance tests verify that `profile outside` produces correct offset allowances in RemovalIntent.

### 4. AI-Friendly Primitives
- **Composable**: Small, orthogonal operations (rect, profile, pocket)
- **Declarative**: Describe *what*, not *how*
- **Validatable**: Check RemovalIntent for physical impossibilities
- **Extensible**: Add shapes without understanding planner internals

## Directory Structure

```
mill_ui/
├── adapters/           # RemovalIntent ↔ planner adapters
│   ├── ast_to_removal.py       # LayoutAST → RemovalIntent (canonical)
│   │   └── ast_to_removal_intents()    # Main entry point
│   │   └── item_to_removal_intent()    # Per-item conversion
│   ├── hints_to_removal.py     # Item/v1 hints → RemovalIntent
│   │   └── profile_hint_to_removal_intent()
│   │   └── pocket_hint_to_removal_intent()
│   │   └── hole_hint_to_removal_intent()
│   │   └── engrave_hint_to_removal_intent()
│   └── removal_to_planner.py   # RemovalIntent → v1 planner hints
├── layout_ast/         # LayoutAST dataclasses and parsers
│   ├── layout.py               # Core AST types (Sheet, Item, Feature)
│   ├── compositional.py        # Compositional layout extensions
│   ├── parsers.py              # JSON parser
│   ├── emitters.py             # JSON emitter
│   └── canonicalize.py         # AST canonicalization
├── pml/                # PML parser and formatter
│   ├── parser.py               # Flat PML parser (explicit positioning)
│   ├── formatter.py            # Flat PML formatter
│   ├── compositional_parser.py # Compositional PML parser (layout managers)
│   └── compositional_formatter.py  # Compositional PML formatter
├── cli/                # Command-line tools
│   ├── parse_compositional_pml.py  # PML parser CLI
│   └── convert_layout.py           # JSON ↔ AST converter
│   # Note: cli/introspect.py (dump-ast, dump-removal-intent) not implemented
│   #       Tests import it (test_cli_dump.py) and will fail until created
├── resolution/         # Compositional → Flat layout resolution
│   └── layout_resolver.py      # Resolves hierarchical AST to flat LayoutAST
│       ├── Handles frame, inset, grid layout managers
│       ├── Component expansion with parameter substitution
│       └── Spline path sampling (Catmull-Rom curves)
├── ir/                 # RemovalIntent IR
│   └── removal_intent.py       # Core IR dataclass (includes Bounds2D, Allowance, Constraints)
├── templates/          # Parametric templates
│   └── shaker.py               # Shaker cabinet door (only template currently implemented)
├── validation/         # IR validation (overlaps, constraints)
│   ├── removal_checks.py       # Overlap, depth, toolability checks
│   └── results.py              # ValidationResult dataclass
├── export/             # Debugging visualizations
│   └── svg_removal.py          # Render LayoutAST + RemovalIntent as SVG overlay
├── tests/              # Comprehensive test suite
├── cam/                # CAM planner backend (retained v1)
│   ├── planner/                # Pass planning, toolpath generation
│   ├── ops/                    # Operations (profile, pocket, drill)
│   ├── path/                   # Path strategies
│   ├── post/                   # G-code generation
│   ├── native/                 # C++ native backend (OCCT-based)
│   │   ├── core.py             # Python interface to native backend
│   │   └── cpp/                # Full OCCT C++ implementation with pybind11
│   ├── types.py                # Vec2, Bounds, Transform2D
│   ├── config.py               # Config management
│   ├── shape.py                # Shape2D polyline
│   ├── primitives.py           # rectangle, circle helpers
│   └── transforms.py           # Geometric transformations
└── cad/
    └── export/         # CAD export formats (mixed status)
        ├── step.py     # STEP export (imports missing skills.mill_ui.cad.native - broken)
        ├── svg.py      # SVG export (imports missing skills.mill_ui.cad.layout.* - broken)
        ├── stl.py      # STL stub (1 line, non-functional)
        ├── svg_dims.py # SVG dimensioned drawings (496 lines, may be functional)
        └── panel_stl.py # Panel STL export (251 lines, may be functional)
        # Note: step.py and svg.py require fixing import paths before use
```

## Extension Points

### Adding a New Shape

1. **Add AST geometry type** in `layout_ast/layout.py`:
   ```python
   # Already exists: Rect, Circle, RoundedRect, Line, SplinePath
   ```

2. **Add RemovalIntent conversion** in `adapters/hints_to_removal.py`:
   ```python
   def _item_geometry_to_bounds(item_type: str, geometry_data: dict, cx: float, cy: float) -> Bounds2D:
       if item_type == "NewShape":
           # ... compute bounds from geometry_data
   ```

3. **Add tests** in `tests/`:
   ```python
   def test_new_shape_to_removal_intent():
       item = Item(kind="shape", type="NewShape", ...)
       intent = item_to_removal_intent(item, 19.0)
       assert intent.bounds == expected_bounds
   ```

### Adding a New Feature

Example: Chamfer edges

1. **Add feature type** in `layout_ast/layout.py`:
   ```python
   @dataclass(frozen=True)
   class Feature:
       type: str  # "profile", "pocket", "hole", "engrave", "chamfer"
       # ... existing fields
       chamfer_angle_deg: float | None = None
   ```

2. **Convert to RemovalIntent** in `adapters/hints_to_removal.py`
3. **Add planner support** (or use existing profile with angle metadata)

### Creating a Template

Templates expand parameters to LayoutAST. Example from `templates/shaker.py`:

```python
class Shaker:
    @staticmethod
    def expand_to_ast(params: dict, sheet_thickness_mm: float) -> LayoutAST:
        # Parse params
        outer_w = params["outer_w"]
        outer_h = params["outer_h"]
        panel_recess = params.get("panel_recess", 0.0)

        # Build items
        items = [
            Item(type="Rect", geometry=..., feature=Feature(type="profile", ...)),
            Item(type="Rect", geometry=..., feature=Feature(type="pocket", ...)),
        ]

        return LayoutAST(sheet=Sheet(...), items=tuple(items))
```

Register in `templates/__init__.py`:
```python
from .shaker import Shaker
__all__ = ["Shaker"]
```

**Note:** Currently only the Shaker template is implemented. The template framework is designed for extensibility, but other templates need to be created.

## Development

### Running Tests

```bash
# Core IR tests
PYTHONPATH=/path/to/cliff_ai python3 -m skills.mill_ui.tests.run_removal_intent_tests

# PML parser tests
PYTHONPATH=/path/to/cliff_ai python3 -m skills.mill_ui.tests.run_pml_tests

# Resolution tests (component placement)
PYTHONPATH=/path/to/cliff_ai python3 -m skills.mill_ui.tests.run_resolution_tests

# G-code equivalence (requires native CAM backend)
PYTHONPATH=/path/to/cliff_ai python3 -m skills.mill_ui.tests.run_gcode_equivalence_tests

# Note: test_cli_dump.py will fail due to missing cli/introspect.py
# Note: test_cli_parse_compositional_pml.py requires pytest (pytest-based, not standalone runner)
```

### Validation Strategy

1. **AST level**: Parse PML/JSON, validate structure
2. **IR level**: Convert to RemovalIntent, check bounds/depths/constraints
3. **CAM level**: Generate toolpaths, verify G-code output
4. **Equivalence**: Ensure new pipeline produces identical G-code to legacy path

Most development happens at **IR level** - fast, no native dependencies, high signal.

## Design Tradeoffs

### Why Keep v1 CAM Planner?
The planner works correctly and handles complex cases (tab insertion, seam merging, multi-depth passes). Replacing it would be:
- High risk (G-code generation is safety-critical)
- Low value (planner quality is good)
- Large effort (pocket raster, profile offset, tool selection)

Instead: Invest in better *input* (RemovalIntent IR) and let proven planner do its job.

### Why Two PML Dialects (Flat + Compositional)?
- **Flat PML**: Simple, explicit, good for direct manual authoring
- **Compositional PML**: Powerful, relative positioning, good for complex layouts with reusable components

Both compile to identical flat LayoutAST after resolution, so tools work with either format.

### Why Not Use Standard Formats (STEP, SVG, DXF)?
Standard CAD formats describe *geometry*, not *manufacturing intent*:
- STEP: 3D solid model (no concept of "profile outside" vs "pocket 6mm deep")
- SVG: 2D curves (no depth, no features, no constraints)
- DXF: 2D geometry (better, but still no semantics)

RemovalIntent explicitly encodes *what to machine*, not just *what shape*.

Future: Import STEP/DXF → infer intent → generate RemovalIntent.

## Current Limitations

1. **Native CAM backend optional**: Some tests require C++ planner (not required for IR validation)
2. **2.5D only**: No full 3D toolpaths (acceptable for sheet-based CNC routing)
3. **Single tool per pass**: No automatic tool changes mid-operation
4. **Limited shape library**: Rectangle, Circle, RoundedRect, Line, SplinePath (extensible)
5. **Single template**: Only Shaker template implemented, framework ready for more
6. **CAD export partially broken**: step.py and svg.py have broken imports; svg_dims.py and panel_stl.py may work
7. **CLI introspection incomplete**: dump-ast/dump-removal-intent referenced in tests but not implemented

These are acceptable tradeoffs for the target domain (panel-based CNC routing).

## What's Next

Potential extensions (not roadmap, just possibilities):

- **More shapes**: Polygon, Bezier curves, imported SVG paths
- **More templates**: Dovetail boxes, finger joints, grid patterns
- **Advanced features**: Chamfers, fillets at IR level
- **Simulation**: RemovalIntent → 3D volumetric preview
- **Alternative planners**: Adaptive toolpaths, trochoidal milling
- **Multi-material**: Different RemovalIntent per material layer
- **CAD export**: Fix import paths, enable RemovalIntent → STEP solid model (inverse operation)
- **CLI introspection**: Implement dump-ast, dump-removal-intent commands

The IR foundation supports all of these without architectural changes.

## Known Issues

1. **cad/export/step.py, svg.py**: Import paths reference non-existent modules (`skills.mill_ui.cad.native`, `skills.mill_ui.cad.layout.*`). Needs refactoring before use. `stl.py` is a 1-line stub. `svg_dims.py` and `panel_stl.py` may be functional but undocumented.
2. **cli/introspect.py**: Referenced in `test_cli_dump.py` (line 14) but not implemented. Tests will fail on import.
3. **Limited validation**: IR-level validation covers overlap/depth/toolability but not full geometry-level collision detection.
4. **frame behavior**: `frame` auto-generates outer profile. Using `rect outer profile` + `frame` creates two profiles. Use `inset` if you want manual profile control.

## License

(Add license here)

## Contributing

(Add contribution guidelines here)
