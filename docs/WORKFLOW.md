# mill_ui Workflow: PML to G-code

## Complete Pipeline Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                               INPUT FORMATS                                          │
├────────────────┬──────────────────┬─────────────────────┬────────────────────────────┤
│  Flat PML      │ Compositional PML│ JSON/Python Template│  Nest PML (.nest)      │
│  (explicit xy) │ (layout managers)│ (programmatic)      │  (bin-packing jobs)        │
└───────┬────────┴────────┬─────────┴─────────┬───────────┴────────────┬───────────────┘
        │                 │                   │                        │
        │ pml.parser      │ pml.comp_parser   │ layout_ast.parsers     │ pml.nest_parser
        │ parse_pml()     │ parse_comp_pml()  │ LayoutAST.from_json()  │ parse_nest_pml()
        │                 │                   │ Template.expand_to_ast()│
        ▼                 ▼                   │                        ▼
    ┌────────────────────────────────────────┐         │      ┌─────────────────────────┐
    │   CompositionalLayoutAST               │         │      │       NestJob           │
    │   (hierarchical, relative positioning) │         │      │   (parts, quantities,   │
    └────────────────┬───────────────────────┘         │      │    sheet, algorithm)    │
                     │                                 │      └───────────┬─────────────┘
                     │ resolution.layout_resolver      │                  │
                     │ resolve_layout()                │                  │ nesting.api
                     ▼                                 │                  │ nest_and_generate()
                                                       │                  │
                                                       │      ┌───────────▼─────────────┐
                                                       │      │    Nesting Algorithms   │
                                                       │      │  • guillotine (fast)    │
                                                       │      │  • maxrects (better)    │
                                                       │      └───────────┬─────────────┘
                                                       │                  │
         ┌───────────────────────────────────┐         │                  │
         │       LayoutAST (FLAT)            │◄────────┴──────────────────┘
         │  Canonical semantic structure     │   (multiple LayoutASTs from nesting)
         │  - Sheet (dimensions)             │
         │  - Items (shapes, features)       │
         │  - Placement (absolute xy)        │
         └───────────────┬───────────────────┘
                         │
         ┌───────────────┼───────────────────┐
         │               │                   │
         │               │                   │ (side outputs)
         │               │                   │
         ▼               ▼                   ▼
    ┌─────────┐   ┌─────────────┐    ┌──────────────────┐
    │ PML     │   │ JSON        │    │ SVG Visualization│
    │ Emitter │   │ Emitter     │    │ (layout preview) │
    └─────────┘   └─────────────┘    └──────────────────┘
         │               │                   │
         │               │                   │
         ▼               ▼                   ▼
      .pml           .json          layout_debug.svg
    (flat)         (serialized)     (export/svg_removal.py)

                         │
                         │ adapters.ast_to_removal
                         │ ast_to_removal_intents()
                         ▼
         ┌───────────────────────────────────┐
         │      RemovalIntent IR             │◄─── Validation Layer
         │  Semantic machining operations    │     (validation/removal_checks.py)
         │  - region_id, bounds (x,y)        │     • Overlap detection
         │  - z_top, z_bottom (depth)        │     • Depth feasibility
         │  - allowance (inside/outside/on)  │     • Toolability checks
         │  - constraints (tabs, keepouts)   │     • Constraint validation
         │  - metadata (source tracking)     │
         └───────────────┬───────────────────┘
                         │
         ┌───────────────┼───────────────────┬────────────────┐
         │               │                   │                │
         │ (future)      │                   │ (future)       │ (partially broken)
         │               │                   │                │
         ▼               ▼                   ▼                ▼
    ┌─────────┐   ┌─────────────┐    ┌──────────┐    ┌──────────────┐
    │ STL     │   │ STEP        │    │ DXF      │    │ DWG          │
    │ Export  │   │ Export      │    │ Export   │    │ Export       │
    │         │   │             │    │          │    │              │
    │ (3D     │   │ (3D CAD)    │    │ (2D CAD) │    │ (2D CAD)     │
    │ mesh)   │   │             │    │          │    │              │
    └─────────┘   └─────────────┘    └──────────┘    └──────────────┘
         │               │                   │                │
         ▼               ▼                   ▼                ▼
      .stl           .step/.stp          .dxf             .dwg
         │               │                   │                │
         │               │                   │                │
    (cad/export/    (cad/export/        (future)         (future)
     panel_stl.py)   step.py)
     [PARTIAL]       [BROKEN: needs
                      cad.native fix]
                         │
                         │ adapters.removal_to_planner
                         │ removal_intents_to_v1_hints()
                         ▼
         ┌───────────────────────────────────┐
         │      Planner Hint Dicts           │
         │  CAM planner input format         │
         │  - geometry, feature type         │
         │  - depth, allowance               │
         │  - tool selection hints           │
         └───────────────┬───────────────────┘
                         │
                         │ cam.planner
                         │ plan_all_passes()
                         ▼
         ┌───────────────────────────────────┐
         │      CAM Execution Plan           │
         │  Ordered machining passes         │
         │  - Profile passes (outside/inside)│
         │  - Pocket passes (raster+finish)  │
         │  - Hole/drill passes              │
         │  - Engrave passes                 │
         └───────────────┬───────────────────┘
                         │
         ┌───────────────┼───────────────────┐
         │               │                   │
         │ (strategies)  │ (native backend)  │
         ▼               ▼                   │
    ┌──────────┐   ┌─────────────┐          │
    │ Path     │   │ Native CAM  │          │
    │ Strate-  │   │ Core (C++)  │          │
    │ gies     │──▶│ pybind11    │          │
    │          │   │             │          │
    │ • pocket │   │ • pocket    │          │
    │   raster │   │   raster    │          │
    │ • profile│   │ • profile   │          │
    │   offset │   │   outline   │          │
    │ • drill  │   │ • arc       │          │
    │          │   │   fitting   │          │
    └──────────┘   └─────────────┘          │
         │               │                   │
         └───────────────┴───────────────────┘
                         │
                         │ cam.ops (operation implementations)
                         │ • profile_outline()
                         │ • pocket_raster()
                         │ • pocket_then_finish_profile()
                         │ • drill_pattern()
                         ▼
         ┌───────────────────────────────────┐
         │      Toolpath Moves               │
         │  Low-level move sequences         │
         │  - move_rapid(x, y, z)            │
         │  - move_cut(x, y, z, feed)        │
         │  - move_comment(text)             │
         │  - arc moves (optional)           │
         └───────────────┬───────────────────┘
                         │
                         │ cam.post
                         │ post_gcode()
                         ▼
         ┌───────────────────────────────────┐
         │          G-CODE                   │
         │  Machine-executable output        │
         │  - G0/G1 (rapid/feed moves)       │
         │  - G2/G3 (arc moves)              │
         │  - M commands (spindle, coolant)  │
         │  - Comments for debugging         │
         └───────────────────────────────────┘
                         │
                         ▼
                    output.nc
                    output.gcode
                    (CNC machine ready)
```

---

## Pipeline Stages Explained

### Stage 1: Input Parsing
**Purpose:** Convert human/AI-authored formats into LayoutAST

**Inputs:**
- **Flat PML**: Explicit absolute positioning (`rect outer at 225mm,325mm size 400mm,600mm`)
- **Compositional PML**: Relative positioning with layout managers (`inset 50mm`, `frame 50mm`)
- **JSON**: Direct AST serialization
- **Python Templates**: Programmatic generation (`Shaker.expand_to_ast()`)
- **Nest PML**: Bin-packing job specification (`.nest` files)

**Outputs:**
- `CompositionalLayoutAST` (if using compositional PML)
- `LayoutAST` (flat, canonical form)
- `NestJob` (if using nest PML, then processed through nesting algorithms)

**Key Files:**
- `pml/parser.py` - Flat PML parser
- `pml/compositional_parser.py` - Compositional PML parser
- `pml/nest_parser.py` - Nest PML parser for `.nest` files
- `layout_ast/parsers.py` - JSON parser
- `templates/*.py` - Template generators

---

### Stage 1B: Domain/Generator Composition (Alternative Input Path)
**Purpose:** Programmatically generate complex designs using math-based composition

**Process:**
- Create Domain instances from parameters or polygon vertices
- Apply domain operations (inset, offset, subtract, intersect)
- Invoke generators on domains to produce LayoutAST Items
- Combine Items into LayoutAST

**Pipeline:**
```
Domain Composition → Generators → LayoutAST → (standard pipeline continues)
```

**Inputs:**
- Domain dimensions and positions (programmatic)
- Generator parameters (typed dataclasses)

**Outputs:**
- `list[Item]` from each generator
- Combined into `LayoutAST`

**Key Functions:**
```python
from domains import Domain
from generators import profile_generator, flat_pocket_generator, ProfileParams, FlatPocketParams

# Create domains
outer = Domain.from_rectangle(400, 600, center=(200, 300))
panel = outer.inset(50).domains[0]

# Generate items
profile_items = profile_generator(outer, ProfileParams(side="outside", depth="through"))
pocket_items = flat_pocket_generator(panel, FlatPocketParams(depth_mm=6.0))

# Build AST
from layout_ast.layout import LayoutAST, Sheet
ast = LayoutAST(
    sheet=Sheet(width_mm=450, height_mm=650, thickness_mm=19.0),
    items=tuple(profile_items + pocket_items),
)
```

**Available Generators:**
- **Area generators**: `flat_pocket_generator`, `wave_generator`, `grid_generator`
- **Loop generators**: `profile_generator`, `bead_generator`
- **SVG generators**: `svg_stamp_generator`

**Key Files:**
- `domains/domain.py` - Domain and MultiDomain types
- `domains/transforms.py` - Coordinate transforms
- `generators/base.py` - Generator protocol, parameter classes
- `generators/area/` - Area generator implementations
- `generators/loop/` - Loop generator implementations
- `generators/svg/` - SVG parsing and stamping

**See:** [docs/domain_generator_design.md](domain_generator_design.md) for complete architecture.

---

### Stage 2: Layout Resolution
**Purpose:** Flatten hierarchical layouts into absolute positioning

**Process:**
- Resolve layout managers (frame, inset, grid, split)
- Expand components with parameter substitution
- Sample spline paths (Catmull-Rom curves)
- Compute absolute xy coordinates for all items

**Inputs:** `CompositionalLayoutAST`
**Outputs:** `LayoutAST` (flat)

**Key Files:**
- `resolution/layout_resolver.py`

---

### Stage 2B: Nesting (Alternative Path)
**Purpose:** Optimize part placement for production runs

**Process:**
- Parse `.nest` files specifying parts, quantities, and sheet specifications
- Run bin-packing algorithm (guillotine or maxrects)
- Expand templates (e.g., Shaker) to full geometry
- Generate one `LayoutAST` per sheet

**Inputs:** `NestJob` from nest PML parser
**Outputs:** `list[LayoutAST]` (one per sheet)

**Algorithms:**
- **Guillotine**: Fast, simple guillotine cuts. Best for uniform parts.
- **MaxRects**: Higher utilization with free rectangle tracking. Best for mixed sizes.

**Key Files:**
- `nesting/api.py` - High-level `nest_parts()` and `nest_and_generate()` functions
- `nesting/guillotine.py` - Guillotine bin-packing algorithm
- `nesting/maxrects.py` - MaxRects bin-packing algorithm
- `nesting/sheet_packer.py` - Multi-sheet packing orchestration
- `nesting/template_expander.py` - Expand templates to Items
- `nesting/layout_generator.py` - Convert nesting results to LayoutAST/PML
- `nesting/validation.py` - Nesting-specific validation

**Example Usage:**
```bash
# CLI tool
PYTHONPATH=. python3 tools/nest.py cabinet_job.nest -o output/

# Programmatic
from pml.nest_parser import parse_nest_pml, nest_job_to_api_params
from nesting import nest_and_generate

job = parse_nest_pml(open("job.nest").read())
result = nest_and_generate(**nest_job_to_api_params(job), output_format="ast")
# result["output"] is list[LayoutAST], one per sheet
```

---

### Stage 3: Semantic IR Conversion
**Purpose:** Convert design intent into machining semantics

**Process:**
- Extract geometric bounds from shapes
- Map feature types to removal operations
- Compute depth ranges (z_top, z_bottom)
- Determine allowances (inside/outside/on geometry)
- Attach constraints (tabs, keepouts, tolerances)

**Inputs:** `LayoutAST`
**Outputs:** `RemovalIntent[]` (IR list)

**Key Files:**
- `adapters/ast_to_removal.py` - Main conversion
- `ir/removal_intent.py` - IR dataclass definition

**Validation at IR Level:**
- Overlap detection between intents
- Depth feasibility (not deeper than stock)
- Toolability checks (minimum feature sizes)
- Constraint validation

---

### Stage 4A: CAD Export (Side Path)
**Purpose:** Generate 3D/2D CAD files for visualization or external tools

**Available Formats:**
- **STL**: 3D triangle mesh (panel_stl.py) - PARTIALLY WORKING
- **STEP**: 3D CAD solid model (step.py) - BROKEN (needs import path fixes)
- **SVG**: 2D layout visualization (svg_removal.py) - WORKING
- **DXF**: 2D CAD format - FUTURE
- **DWG**: 2D CAD format - FUTURE

**Note:** CAD export happens from `LayoutAST` or `RemovalIntent` level, not from G-code.

**Key Files:**
- `cad/export/panel_stl.py` - STL mesh generation
- `cad/export/step.py` - STEP solid export (broken imports)
- `export/svg_removal.py` - SVG debug visualization

---

### Stage 4B: CAM Planning (Main Path)
**Purpose:** Convert RemovalIntent into executable toolpaths

**Process:**
1. **Hint Conversion**: RemovalIntent → planner hint dicts
2. **Pass Planning**: Group operations, determine ordering
3. **Strategy Selection**: Choose pocket/profile/drill strategies
4. **Toolpath Generation**:
   - Pocket raster (zigzag pattern with stepdown)
   - Profile outline (offset from boundary)
   - Finish perimeter (cleanup pass for pockets)
   - Drill patterns (hole centers)
5. **Native Backend**: Performance-critical ops in C++ (optional)

**Inputs:** `RemovalIntent[]`
**Outputs:** Move sequences (list of dict)

**Key Files:**
- `adapters/removal_to_planner.py` - IR → hints
- `cam/planner/plan.py` - Pass orchestration
- `cam/planner/passes/*.py` - Pass planners (profile, pocket, hole, engrave)
- `cam/path/strategies.py` - Toolpath strategies
- `cam/ops/*.py` - Low-level operation implementations
- `cam/native/` - C++ native backend (pybind11)

**Configuration:**
- `cam/config.py` - Tool parameters, feeds/speeds, finish settings
- `pocket_finish_perimeter: bool` - Enable/disable cleanup pass (F001)

---

### Stage 5: G-code Post-Processing
**Purpose:** Convert move sequences into machine-executable G-code

**Process:**
- Translate move dicts to G-code commands
- Apply feed rates and spindle speeds
- Insert safety moves (rapids, safe Z)
- Add comments for debugging
- Optimize arc fitting (optional)

**Inputs:** Move sequences
**Outputs:** G-code text (.nc, .gcode)

**Key Files:**
- `cam/post/gcode.py` - G-code emitter
- `cam/native/core.py` - Native post_gcode() (optional)

---

## Key Decision Points

### ✅ When to Use Each Input Format?

| Format | Use Case | Best For |
|--------|----------|----------|
| **Flat PML** | Simple layouts, explicit control | Manual authoring, one-off designs |
| **Compositional PML** | Complex layouts, reusable components | Parametric designs, grid layouts |
| **JSON** | Programmatic generation | AI/tool output, data-driven designs |
| **Python Templates** | Standardized components | Shaker doors, mounting plates, etc. |
| **Nest PML** | Production runs, multi-sheet jobs | Cutting many parts from stock sheets |
| **Domain/Generator** | Complex programmatic designs | Decorative patterns, custom shapes, SKU variation |

### ✅ When to Export CAD vs G-code?

| Format | Purpose | Workflow |
|--------|---------|----------|
| **STL** | 3D visualization, external CAM | LayoutAST → STL (preview before machining) |
| **STEP** | 3D CAD interop, assemblies | RemovalIntent → STEP (design handoff) |
| **SVG** | 2D layout debugging | LayoutAST+IR → SVG overlay (validation) |
| **G-code** | CNC machining execution | RemovalIntent → CAM → G-code (production) |

### ✅ Native Backend: When is it Required?

| Task | Native Required? | Reason |
|------|------------------|--------|
| Parse PML → LayoutAST | ❌ No | Pure Python parsing |
| AST → RemovalIntent IR | ❌ No | Dataclass transformation |
| IR validation | ❌ No | Bounds/constraint checks |
| Toolpath generation | ✅ YES | Performance-critical geometry ops |
| G-code output | ✅ YES | Arc fitting, optimizations |

**Build native backend:** See README "Building the Native CAM Backend" section.

---

## Example Flow: Shaker Door

```
1. Template Input (Python)
   Shaker.expand_to_ast(params)
   → LayoutAST with 2 items (outer profile, inner pocket)

2. IR Conversion
   ast_to_removal_intents(ast)
   → 2 RemovalIntents:
     - Profile: outside, z_bottom=-19mm (through-cut)
     - Pocket: inside, z_bottom=-6mm (panel recess)

3. Validation
   check_overlap(intents) → OK
   check_depth_feasibility() → OK

4. CAM Planning
   plan_all_passes(intents, config)
   → Profile pass (multi-depth outside boundary)
   → Pocket pass (raster + finish perimeter if enabled)

5. Toolpath Execution
   pocket_then_finish_profile(shape, setup, finish_perimeter=True)
   → Rough pocket (shrunk by cleanup_offset)
   → Finish profile (full perimeter at final depth)

6. G-code Output
   post_gcode(moves, config)
   → output.nc (820 moves with finish, 844 without)
```

---

## File Path Reference

### Input Processing
- `pml/parser.py` - Flat PML → LayoutAST
- `pml/compositional_parser.py` - Compositional PML → CompositionalLayoutAST
- `pml/nest_parser.py` - Nest PML → NestJob
- `resolution/layout_resolver.py` - CompositionalLayoutAST → LayoutAST
- `templates/shaker.py` - Parametric template example

### Nesting Module
- `nesting/api.py` - High-level nesting API
- `nesting/types.py` - Nesting data structures (PartSpec, SheetSpec, NestingResult)
- `nesting/guillotine.py` - Guillotine bin-packing algorithm
- `nesting/maxrects.py` - MaxRects bin-packing algorithm
- `nesting/sheet_packer.py` - Multi-sheet packing
- `nesting/template_expander.py` - Template expansion for nested parts
- `nesting/layout_generator.py` - NestingResult → LayoutAST/PML
- `nesting/validation.py` - Nesting validation
- `tools/nest.py` - CLI tool for nesting

### Core Pipeline
- `adapters/ast_to_removal.py` - LayoutAST → RemovalIntent (canonical)
- `adapters/removal_to_planner.py` - RemovalIntent → planner hints
- `cam/planner/plan.py` - Pass orchestration
- `cam/post/gcode.py` - Moves → G-code

### CAD Export (Side Outputs)
- `export/svg_removal.py` - SVG visualization (working)
- `cad/export/panel_stl.py` - STL mesh generation (partial)
- `cad/export/step.py` - STEP export (broken imports)
- `cad/export/svg.py` - SVG export (broken imports)

### Validation
- `validation/removal_checks.py` - IR validation (overlap, depth, toolability)
- `validation/results.py` - ValidationResult dataclass

---

## Status: Current vs Future

### ✅ Production Ready
- PML → LayoutAST → RemovalIntent → G-code
- All core pipeline stages working
- Native backend compiled and tested
- Pocket cleanup pass (F001) implemented
- Nesting module with guillotine and maxrects algorithms
- Profile cuts with holding tabs (F004)

### 🟡 Partially Working
- STL export (panel_stl.py functional, undocumented)
- SVG visualization (working but debug-focused)

### ❌ Broken / Needs Fixing
- STEP export (import path references non-existent `cad.native`)
- CAD SVG export (import path references non-existent `cad.layout`)

### 🔵 Future Work
- DXF export (2D CAD format)
- DWG export (AutoCAD format)
- STEP import (CAD → RemovalIntent reverse path)
- Advanced CAM strategies (adaptive toolpaths, trochoidal milling)

---

## Performance Notes

**Bottlenecks:**
- Pocket raster planning (mitigated by C++ native backend)
- Profile offset computation (native backend)
- Arc fitting (native backend optional optimization)

**Optimization Strategy:**
- Keep IR-level validation fast (pure Python, no geometry)
- Offload heavy geometry ops to native backend
- Mock native backend in unit tests for fast CI

**Typical Performance:**
- Parse PML: <10ms
- AST → IR: <5ms
- IR validation: <5ms
- Toolpath generation: 50-500ms (depends on complexity, native backend)
- G-code output: <50ms

---

Last Updated: 2026-01-17
