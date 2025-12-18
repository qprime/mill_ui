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

### Option 1: PML (Human-Authored)

```pml
sheet 450mm 650mm 19mm

component door
  rect 400mm 600mm profile outside through
  rect 300mm 500mm pocket 6mm

place door at 225mm 325mm
```

Run the PML parser:
```bash
PYTHONPATH=/path/to/cliff_ai python3 -m skills.mill_ui.cli.parse_compositional_pml < door.pml
```

### Option 2: Python Template (Programmatic)

```python
from skills.mill_ui.templates import Shaker

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

# Convert to RemovalIntent IR
from skills.mill_ui.adapters.ast_to_removal import ast_to_removal_intents
intents = ast_to_removal_intents(ast)

# Generate CAM plan (requires native backend or adapters)
from skills.mill_ui.adapters.removal_to_planner import removal_intent_to_hint
hints = [removal_intent_to_hint(intent, ast.sheet.thickness_mm) for intent in intents]
# ... pass to planner
```

### What This Produces

**LayoutAST** (semantic structure):
- Sheet: 450×650×19mm
- Item 1: Rectangle, profile feature (outside, through-cut)
- Item 2: Rectangle, pocket feature (6mm depth)

**RemovalIntent IR** (machining semantics):
- Intent 1: Remove region (bounds, z_top=19mm, z_bottom=0mm, allowance=outside)
- Intent 2: Remove region (bounds, z_top=19mm, z_bottom=13mm, allowance=inside)

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

**Compositional semantics** allow hierarchical layouts (not yet exposed in PML but available programmatically).

### 3. PML vs JSON

**PML (Panel Markup Language)**: Indentation-based DSL for human authoring
- Declarative, concise syntax
- Hierarchical components with relative positioning
- Compiles to LayoutAST

**JSON**: Direct LayoutAST serialization for AI/programmatic generation
- Verbose but explicit
- 1:1 mapping to AST dataclasses
- Skip parsing, go straight to AST

Both compile to the same LayoutAST, ensuring semantic equivalence.

### 4. CAM Backend Integration

mill_ui retains the v1 CAM planner (proven, stable) as the backend:

```
RemovalIntent IR → v1 planner hints → CAM planner → Move IR → G-code
```

The `adapters/` module bridges RemovalIntent to the planner's hint format. This allows:
- Incremental migration (v1 planner works, no need to replace it)
- IR validation before planner execution
- Future: Multiple planner backends targeting the same IR

## Architecture Principles

### 1. Separation of Concerns
- **Parsing** (PML/JSON → AST): Syntax and structure
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
│   ├── ast_to_removal.py       # LayoutAST → RemovalIntent
│   ├── hints_to_removal.py     # v1 hints → RemovalIntent (legacy)
│   └── removal_to_planner.py   # RemovalIntent → v1 planner hints
├── layout_ast/         # LayoutAST dataclasses and parsers
│   ├── layout.py               # Core AST types (Sheet, Item, Feature)
│   └── compositional.py        # Compositional layout extensions
├── cli/                # Command-line tools
│   ├── parse_compositional_pml.py  # PML parser CLI
│   └── convert_layout.py           # JSON ↔ AST converter
├── ir/                 # RemovalIntent IR
│   ├── removal_intent.py       # Core IR dataclass
│   └── bounds.py               # 2D/3D bounding boxes
├── pml/                # PML parser and formatter
│   ├── parser.py               # Indentation-based parser
│   └── formatter.py            # Canonical PML output
├── resolution/         # Layout resolution (components, placement)
├── templates/          # Parametric templates (Shaker, etc.)
├── validation/         # IR validation (overlaps, constraints)
├── export/             # SVG visualization (debug)
├── tests/              # Test suite
├── cam/                # CAM planner backend (retained v1)
│   ├── planner/                # Pass planning, toolpath generation
│   ├── ops/                    # Operations (profile, pocket, drill)
│   ├── path/                   # Path strategies
│   ├── post/                   # G-code generation
│   ├── types.py                # Vec2, Bounds, Transform2D
│   ├── config.py               # Config management
│   ├── shape.py                # Shape2D polyline
│   ├── primitives.py           # rectangle, circle helpers
│   └── transforms.py           # Geometric transformations
└── cad/
    └── export/         # STEP/STL/SVG export (future integration)
```

## Extension Points

### Adding a New Shape

1. **Add AST geometry type** in `layout_ast/layout.py`:
   ```python
   # Already exists: Rect, Circle, RoundedRect, Line, SplinePath
   ```

2. **Add RemovalIntent conversion** in `adapters/ast_to_removal.py`:
   ```python
   def item_to_removal_intent(item: Item, sheet_thickness_mm: float) -> RemovalIntent:
       bounds = calculate_bounds(item.geometry, item.placement)
       # ... compute z_top, z_bottom, allowance
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

2. **Convert to RemovalIntent** in `adapters/ast_to_removal.py`
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

## Development

### Running Tests

```bash
# Core IR tests
PYTHONPATH=/path/to/cliff_ai python3 -m skills.mill_ui.tests.run_edge_tests
PYTHONPATH=/path/to/cliff_ai python3 -m skills.mill_ui.tests.run_spline_tests
PYTHONPATH=/path/to/cliff_ai python3 -m skills.mill_ui.tests.run_keepout_tests

# PML parser tests
PYTHONPATH=/path/to/cliff_ai python3 -m skills.mill_ui.tests.run_compositional_pml_tests

# Resolution tests (component placement)
PYTHONPATH=/path/to/cliff_ai python3 -m skills.mill_ui.tests.run_resolution_tests

# G-code equivalence (requires native CAM backend)
PYTHONPATH=/path/to/cliff_ai python3 -m skills.mill_ui.tests.run_gcode_equivalence_tests
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

### Why Two Input Formats (PML + JSON)?
- **PML**: Human-friendly, concise, hierarchical (for manual authoring)
- **JSON**: AI-friendly, explicit, no parsing ambiguity (for programmatic generation)

Both compile to identical AST, so tools work with either format.

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

These are acceptable tradeoffs for the target domain (panel-based CNC routing).

## What's Next

Potential extensions (not roadmap, just possibilities):

- **More shapes**: Polygon, Bezier curves, imported SVG paths
- **Advanced features**: Chamfers, fillets at IR level
- **Simulation**: RemovalIntent → 3D volumetric preview
- **Alternative planners**: Adaptive toolpaths, trochoidal milling
- **Multi-material**: Different RemovalIntent per material layer
- **CAD export**: RemovalIntent → STEP solid model (inverse operation)

The IR foundation supports all of these without architectural changes.

## License

(Add license here)

## Contributing

(Add contribution guidelines here)
