<!-- spec-style -->
# mill_ui

As-Of Date: 2026-01-19
Document Type: System Specification
Authority: This document is authoritative for architecture and usage described herein.

---

## Purpose

mill_ui transforms PML input into G-code output through a deterministic pipeline.
The system separates *what* to machine (RemovalIntent IR) from *how* to machine it (CAM planner).

---

## Non-Goals

The system does NOT:
- Perform unit conversion internally (all values are millimeters).
- Provide general-purpose CAD editing.
- Support full 3D toolpaths (2.5D only).
- Replace the CAM planner backend.

---

## Terminology

- **PML**: Plaintext language for specifying layouts and operations.
- **LayoutAST**: Flat AST with absolute coordinates. Canonical layout representation.
- **CompositionalLayoutAST**: Hierarchical AST with relative positioning.
- **RemovalIntent**: IR representing what volume to remove, independent of toolpath strategy.
- **Domain**: Bounded 2D region supporting algebraic operations (inset, offset, subtract).
- **Generator**: Deterministic function producing LayoutAST Items from a Domain.

---

## Canonical Pipeline

```
PML/JSON → LayoutAST → RemovalIntent IR → CAM Planner → G-code
```

| Stage | Entry Point | Input | Output |
|-------|-------------|-------|--------|
| 1. Parse Compositional PML | `pml/compositional_parser.py:parse_compositional_pml()` | PML text | CompositionalLayoutAST |
| 2. Resolve Layout | `resolution/layout_resolver.py:resolve_layout()` | CompositionalLayoutAST | LayoutAST |
| 3. AST → IR | `adapters/ast_to_removal.py:ast_to_removal_intents()` | LayoutAST | list[RemovalIntent] |
| 4. IR → Planner Hints | `adapters/removal_to_planner.py:removal_intents_to_v1_hints()` | list[RemovalIntent] | hints dict |
| 5. Plan Passes | `cam/planner/passes/__init__.py:plan_passes()` | hints dict | (pass_records, summary) |
| 6. Generate G-code | `cam/post/gcode.py:write_gcode()` | moves | G-code string |

---

## Input Formats

### Flat PML

Explicit absolute positioning.

```pml
sheet 450mm 650mm 19mm
rect door at 225mm,325mm size 400mm,600mm profile through outside
```

### Compositional PML

Relative positioning with layout managers.

```pml
sheet 400mm 600mm 19mm
rect outer profile through outside
    inset 50mm
        rect inner pocket 6mm
```

### JSON

Direct LayoutAST serialization.
Use `LayoutAST.to_json()` and `LayoutAST.from_json()`.

### Nest PML

Block-based nesting job specification.

```pml
nest maxrects
    sheet 1232mm 1245mm 19mm
    kerf 6.35mm
    parts
        door 457mm 597mm x20
```

---

## CLI Commands

| Command | Description |
|---------|-------------|
| `python -m cli.convert_layout --from pml --to json input.pml output.json` | Convert PML to JSON |
| `python -m cli.export_cad --input layout.pml --out output/ --kerf 6.35` | Export STL |
| `python -m cli.export_blueprint --input layout.pml --out output/ --theme dark` | Export SVG blueprint |
| `python -m cli.validate_cam --recipe docs/recipes/01_simple_profile --summary` | Validate CAM outputs |
| `python -m cli.nest job.nest -o output/ --export-stl --export-svg` | Run nesting |
| `python -m cli.parse_compositional_pml door.pml --resolve --format pml` | Parse compositional PML |

---

## Data Models

### LayoutAST (layout_ast/layout.py)

| Dataclass | Fields |
|-----------|--------|
| Sheet | width_mm, height_mm, thickness_mm |
| Placement | center_xy_mm: tuple[float, float] |
| Geometry | data: dict[str, Any] |
| Feature | type, depth, side, depth_mm, tab_count, tab_height_mm, tab_width_mm |
| Item | kind, type, geometry, placement, feature, params, shape_id, id |
| LayoutAST | sheet, items, config fields |

### RemovalIntent IR (ir/removal_intent.py)

| Dataclass | Fields |
|-----------|--------|
| Bounds2D | x_min, x_max, y_min, y_max |
| RemovalIntent | region_id, bounds, z_top, z_bottom, allowance, constraints, metadata |

**Invariants:**
- Bounds2D: x_max >= x_min AND y_max >= y_min MUST hold.
- RemovalIntent: z_bottom <= z_top MUST hold.

---

## Coordinate Conventions

- All internal values MUST be millimeters.
- XY: center-based coordinates. Stock origin is lower-left.
- Z: Positive away from material, negative into material.
- z_top typically 0.0 at stock surface.
- z_bottom MUST be negative for material removal.

---

## Shapes and Features

### Supported Shapes

Rectangle, Circle, RoundedRect, Line, SplinePath.

### Supported Features

| Feature | Description |
|---------|-------------|
| profile | Through-cut or partial depth. Side: inside, outside, on. |
| pocket | Partial-depth depression. |
| hole | Through-hole (subtractive). |
| engrave | Surface carving. |

### Tabs (Profile Feature)

```pml
rect cutout at 300mm,200mm size 400mm,250mm profile through outside tabs 4 height 3mm width 12mm
```

Required: `tabs <count> height <height>mm`. Optional: `width <width>mm`.

---

## Layout Managers (Compositional PML)

| Manager | Description |
|---------|-------------|
| frame \<width\>mm | Inset border, auto-generates outer profile. |
| inset \<amount\>mm | Uniform inset on all sides. |
| place grid \<rows\> \<cols\> gap \<gap\>mm | Grid-based component placement. |

---

## Domain/Generator System

Domains define *where* to machine. Generators define *what* to produce.

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

---

## Nesting

### Algorithms

| Algorithm | Characteristics |
|-----------|-----------------|
| guillotine | Fast, simple guillotine cuts. ~62% utilization. |
| maxrects | Better utilization with free rectangle tracking. ~83% utilization. |

### Output

- One `.pml` file per sheet with explicit part placements.
- `manifest.json` with utilization metrics.

---

## Validation

### IR-Level Validation

| Check | Description |
|-------|-------------|
| check_overlap() | 3D bounding-box intersection. |
| check_depth_feasibility() | z_top >= z_bottom, warns on depth vs thickness. |
| check_toolability() | Feature size vs tool diameter. |

### CAM Artifact Validation

| Artifact | Metrics |
|----------|---------|
| SVG | Dimensions, layers, path counts, element breakdown. |
| STL | Vertex/face counts, watertight, manifold, volume. |
| G-code | Motion counts, distances, Z-profile, feeds, tools. |

---

## Directory Structure

```
mill_ui/
├── adapters/           # RemovalIntent ↔ planner adapters
├── layout_ast/         # LayoutAST dataclasses and parsers
├── pml/                # PML parser and formatter
├── cli/                # Command-line tools
├── resolution/         # Compositional → Flat layout resolution
├── ir/                 # RemovalIntent IR
├── domains/            # Domain type and operations
├── generators/         # Generators producing Items from Domains
├── templates/          # Parametric templates (Shaker)
├── nesting/            # Bin-packing module
├── validation/         # IR and CAM validation
├── export/             # Blueprint SVG, debugging visualizations
├── cam/                # CAM planner backend
├── cad/export/         # CAD export (STL, SVG dims)
└── tests/              # Test suite
```

---

## Extension Points

| Extension | Location |
|-----------|----------|
| Add new shape | `adapters/hints_to_removal.py:_item_geometry_to_bounds()` |
| Add new feature | `layout_ast/layout.py:Feature`, `adapters/hints_to_removal.py` |
| Add new template | `templates/__init__.py`, implement `expand_to_ast()` |
| Add IR validation | `validation/removal_checks.py` |
| Add planner strategy | `cam/planner/passes/` |
| Add generator | `generators/area/` or `generators/loop/` |
| Add domain operation | `domains/domain.py:Domain` class |

---

## Known Issues

1. `cad/export/step.py`, `svg.py`: Import paths reference non-existent modules.
2. `cli/introspect.py`: Referenced in tests but not implemented.
3. `frame` auto-generates outer profile. Using `rect outer profile` + `frame` creates two profiles.

---

## Building the Native Backend

Prerequisites: CMake 3.10+, C++17 compiler, pybind11.

```bash
python3 -m venv venv && source venv/bin/activate
pip install pybind11
cmake -S cam/native/cpp -B build/native_cam -Dpybind11_DIR=$(python3 -m pybind11 --cmakedir)
cmake --build build/native_cam
cp build/native_cam/python/_native.*.so cam/native/
```

The native backend is optional. IR-level tests work without it.

---

## Running Tests

```bash
./run_tests.sh                              # All core tests
./run_tests.sh run_pml_tests                # PML parser tests
./run_tests.sh run_edge_tests               # Edge case tests
PYTHONPATH=. python3 -m tests.run_removal_intent_tests  # IR tests
```

---

## AI Instructions

When modifying this repository:
- Treat this document as authoritative for described behaviors.
- Preserve all stated invariants.
- Do not infer unspecified behavior.
- If a change affects the canonical pipeline stages, update this document in the same commit.
