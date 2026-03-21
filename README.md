# mill_ui

CAM system that turns declarative panel layouts into G-code for CNC routers. Describe what you want to cut — profiles, pockets, joinery, assemblies — and the compiler pipeline handles toolpath generation, validation, and blueprint export.

## Why

Most CAM workflows require manual toolpath setup in GUI software for every job. mill_ui replaces that with a declarative input language (PML) and a compiler-style pipeline that validates your design *before* generating toolpaths. The entire system is designed to be driven by natural language through an AI assistant — describe what you want to build, get PML, review the SVG blueprint, iterate, then cut.

## What It Does

- **Declarative input** — PML (YAML) describes shapes, features, and layout. No manual toolpath editing.
- **Compiler pipeline** — `PML → LayoutAST → RemovalIntent IR → CAM Planner → G-code`. Validates *what* to machine before deciding *how*.
- **Blueprint export** — SVG and PDF blueprints with dimensions, generated alongside G-code.
- **Assembly system** — Define boxes, cabinets, cubbies, and beam structures. Joinery (finger joints, dadoes, half-laps) is resolved automatically from panel interfaces. Multi-sheet partitioning when parts exceed a single sheet.
- **Nesting** — Bin-pack parts across sheets with guillotine or maxrects algorithms. Supports holding strategies (onion skin, tabs) and non-rectangular shapes.
- **Validation** — IR-level checks (overlap, depth feasibility, toolability) catch errors before G-code generation. CAM artifact validation compares outputs against golden metrics.
- **Machine configuration** — YAML-based endmill library, feed rates, and per-machine profiles.

## Quick Start

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python -m cli.mill --recipe docs/recipes/01_simple_profile
```

This generates G-code and an SVG blueprint in the recipe's `output/` directory.

### Example PML

```yaml
Sheet:
  width: 450mm
  height: 650mm
  thickness: 19mm
children:
- Rect:
    id: door
    feature:
      type: profile
      depth: through
      side: outside
    at:
      x: 225mm
      y: 325mm
      width: 400mm
      height: 600mm
```

### Compositional PML

PML also supports relative positioning with layout managers — frames, grids, splits — so you describe structure, not coordinates:

```yaml
Sheet:
  width: 400mm
  height: 600mm
  thickness: 19mm
children:
- Frame:
    width: 50mm
    children:
    - Rect:
        id: inner
        feature:
          type: pocket
          depth: 6mm
```

## Pipeline

```
PML/JSON → LayoutAST → RemovalIntent IR → CAM Planner → G-code + SVG
```

| Stage | Entry Point |
|-------|-------------|
| Parse PML | `pml/yaml_parser.py:parse_pml_yaml()` |
| Resolve Layout | `resolution/layout_resolver.py:resolve_layout()` |
| AST → IR | `adapters/ast_to_removal.py:ast_to_removal_intents()` |
| IR → Planner | `adapters/removal_to_planner.py:removal_intents_to_hints()` |
| Plan Passes | `cam/planner/passes/__init__.py:plan_passes()` |
| Generate G-code | `cam/post/gcode.py:write_gcode()` |

`pml/lifter.py` provides the reverse path, lifting LayoutAST back to PML (used by nesting output and format conversion).

## Features

### Shapes

Rectangle, Circle, RoundedRect, Polygon, Polyline, Triangle, Arch, Line, SplinePath.

### Machining Features

| Feature | Description |
|---------|-------------|
| profile | Through-cut or partial depth. Side: inside, outside, on. |
| pocket | Partial-depth depression. |
| surface | Full-sheet surface facing with cooling pauses. |
| hole | Through-hole (subtractive). |
| engrave | Surface carving. |
| bevel | Angled edge cut with width, angle, and inner depth. |
| chamfer | Angled edge break with width and angle. |
| roundover | Quarter-circle edge profile using roundover bit. |
| wave | Repeating wave texture pattern. |

Profiles support **tabs** (holding bridges) to keep parts attached during through-cuts.

### Layout Managers

| Manager | Description |
|---------|-------------|
| Frame | Inset border, auto-generates outer profile. |
| Grid | Grid-based component placement with gap control. |
| Split | Window-style splits with rail/mullion widths. |
| Inset | Uniform inset on all sides. |
| Place | Positioned children with explicit mapping. |
| Panel | Basic panel container. |
| Keepout | Exclusion zone (no machining). |

### Assembly System

Define multi-panel projects (box, carcass, cubby, beam) with interface-first joinery. The system resolves panel interfaces into machining features automatically:

- **Joinery strategies:** HalfLap, Dado, Finger, Captured
- **Multi-sheet partitioning:** When panels exceed a single sheet, `assembly/partitioner.py` distributes them across multiple sheets

### Nesting

Bin-pack parts onto sheets using `.nest.yml` files:

```yaml
Nest:
  algorithm: maxrects
  Sheet:
    width: 1232mm
    height: 1245mm
    thickness: 19mm
  kerf: 6.35mm
  holding:
    onion_skin: 0.3mm
  parts:
    - name: door
      width: 457mm
      height: 597mm
      quantity: 20
    - name: coaster
      width: 100mm
      height: 100mm
      quantity: 10
      shape:
        type: RoundedRect
        radius: 10mm
      holding:
        tab_count: 4
        tab_height: 3mm
```

Algorithms: **guillotine** (~62% utilization) and **maxrects** (~83% utilization). Supports RoundedRect, Polygon, Circle, and Triangle shape primitives.

### Domain/Generator System

Domains define *where* to machine (bounded 2D regions with inset/offset/subtract/intersect operations). Generators define *what* to produce from those regions:

| Type | Examples |
|------|----------|
| Area | flat_pocket_generator, wave_generator, grid_generator |
| Loop | profile_generator, bead_generator |
| SVG | svg_stamp_generator |

## CLI

| Command | Description |
|---------|-------------|
| `python -m cli.mill --project my_project` | Generate G-code and SVG blueprint |
| `python -m cli.mill --recipe docs/recipes/01_simple_profile` | Run a recipe example |
| `python -m cli.mill --init_project layout --sheet 1220x1220 --thickness 19` | Generate starter PML |
| `python -m cli.nest job.nest.yml -o output/ --export-svg` | Run nesting |
| `python -m cli.validate_cam --recipe docs/recipes/01_simple_profile --summary` | Validate CAM outputs |
| `python -m cli.convert_layout --from pml --to json input.pml.yml output.json` | Convert between formats |
| `python -m cli.generate_golden --all-recipes docs/recipes --update` | Regenerate golden metrics |

## Project Structure

```
mill_ui/
├── adapters/           # AST ↔ IR ↔ planner adapters, AST → DiagramIR
├── assembly/           # Assembly system (box, carcass, cubby, beams, joinery)
├── cam/                # CAM planner, passes, post-processor, G-code ops
├── cli/                # Command-line tools (mill, nest, validate_cam, generate_golden)
├── config/             # Machine configuration loader
├── core/               # Shared geometry utilities and constants
├── diagram_ir/         # DiagramIR intermediate representation for visualization
├── diagram_render/     # SVG renderer for DiagramIR
├── domains/            # Domain type and algebraic operations
├── export/             # Blueprint SVG/PDF export, dimensions
├── generators/         # Pattern generators (area/loop) producing Items from Domains
├── ir/                 # RemovalIntent IR
├── layout_ast/         # LayoutAST and CompositionalLayoutAST dataclasses
├── machines/           # Machine configs, endmill library, feed rates (YAML)
├── mill_mcp/           # MCP server for IDE integration
├── nesting/            # Bin-packing algorithms (guillotine, maxrects)
├── pml/                # PML YAML parser and lifter
├── resolution/         # Compositional → Flat layout resolution
├── templates/          # Parametric component templates
├── tools/              # Utility scripts (visualization, code cleanup)
├── validation/         # IR and CAM artifact validation
└── tests/              # Test suite
```

## Recipes

The `docs/recipes/` directory contains 70+ worked examples covering basic profiles, pockets, assemblies, joinery, nesting, edge treatments, surface facing, and more. Each recipe includes PML input, expected G-code, and SVG blueprint output. Run all recipes:

```bash
python -m tests.test_recipes
```

## Tests

```bash
python -m pytest tests/ -x                     # Full suite
python -m pytest tests/test_pml_yaml.py        # PML parser
python -m pytest tests/test_ast_to_removal.py  # IR adapter
python -m tests.test_recipes                   # Recipe verification
```

## Building the Native Backend

The native C++ backend is optional (improves performance for large jobs). IR-level tests work without it.

```bash
pip install pybind11
cmake -S cam/native/cpp -B build/native_cam -Dpybind11_DIR=$(python3 -m pybind11 --cmakedir)
cmake --build build/native_cam
cp build/native_cam/python/_native.*.so cam/native/
```

## Further Reading

| Topic | Document |
|-------|----------|
| System invariants | [docs/invariants/README.md](docs/invariants/README.md) |
| Coordinate system | [docs/invariants/coordinates.md](docs/invariants/coordinates.md) |
| PML syntax | [pml/syntax_spec.md](pml/syntax_spec.md) |
| Nest syntax | [pml/nest_syntax_spec.md](pml/nest_syntax_spec.md) |
| Domain/Generator API | [docs/domain_generator.md](docs/domain_generator.md) |
| Validation plan | [docs/cam_validation_plan.md](docs/cam_validation_plan.md) |
| Planner hint schema | [docs/dev_docs/planner_hint_schema.md](docs/dev_docs/planner_hint_schema.md) |
| Common tasks | [docs/tasks.md](docs/tasks.md) |
