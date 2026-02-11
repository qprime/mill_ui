<!-- spec-style -->
# mill_ui

**As-Of:** 2026-02-11
**Document Type:** System Specification
**Authority:** This document is authoritative for architecture and behavior described herein.

**Specification Rules:**
- Statements containing MUST / MUST NOT / SHOULD / MAY are normative.
- If a behavior is not specified, do not assume it.
- If any requirement is ambiguous, ask before changing code.

---

## Purpose

mill_ui transforms PML input into G-code output through a deterministic pipeline.
The system separates *what* to machine (RemovalIntent IR) from *how* to machine it (CAM planner).

---

## Non-Goals

The system does NOT:
- Perform unit conversion internally (all values are millimeters).
- Infer missing geometry or feature parameters.
- Provide exact geometric collision detection at IR level.
- Validate feeds/speeds against material/tool compatibility.
- Perform fixture/clamp interference analysis beyond explicit keepouts.

---

## Terminology

| Term | Definition |
|------|------------|
| PML | Plaintext language for specifying layouts and operations. |
| LayoutAST | Flat AST with absolute coordinates. Canonical layout representation. |
| CompositionalLayoutAST | Hierarchical AST with relative positioning. |
| RemovalIntent | IR representing what volume to remove, independent of toolpath strategy. |
| Planner Hints | Dict structures consumed by the planner pass generator. |
| Domain | Bounded 2D region supporting algebraic operations (inset, offset, subtract). |
| Generator | Deterministic function producing LayoutAST Items from a Domain. |
| Safe Z | Z height used for rapid (G0) moves to avoid collisions with stock. |

---

## Canonical Pipeline

```
PML/JSON → LayoutAST → RemovalIntent IR → CAM Planner → G-code
```

| Stage | Entry Point | Input | Output |
|-------|-------------|-------|--------|
| 1. Parse PML (YAML) | `pml/yaml_parser.py:parse_pml_yaml()` | PML YAML text | CompositionalLayoutAST |
| 2. Resolve Layout | `resolution/layout_resolver.py:resolve_layout()` | CompositionalLayoutAST | LayoutAST |
| 3. AST → IR | `adapters/ast_to_removal.py:ast_to_removal_intents()` | LayoutAST | list[RemovalIntent] |
| 4. IR → Planner Hints | `adapters/removal_to_planner.py:removal_intents_to_hints()` | list[RemovalIntent] | hints dict |
| 5. Plan Passes | `cam/planner/passes/__init__.py:plan_passes()` | hints dict | (pass_records, summary) |
| 6. Generate G-code | `cam/post/gcode.py:write_gcode()` | moves | G-code string |

---

## Input Formats

### PML (YAML)

Explicit absolute positioning with YAML syntax.

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

### Compositional PML (YAML)

Relative positioning with layout managers.

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

### JSON

Direct LayoutAST serialization.
Use `LayoutAST.to_json()` and `LayoutAST.from_json()`.

### Nest (YAML)

Multi-part nesting job specification.

```yaml
Nest:
  algorithm: maxrects
  Sheet:
    width: 1232mm
    height: 1245mm
    thickness: 19mm
  kerf: 6.35mm
  parts:
    - name: door
      width: 457mm
      height: 597mm
      quantity: 20
```

---

## CLI Commands

| Command | Description |
|---------|-------------|
| `python -m cli.convert_layout --from pml --to json input.pml.yml output.json` | Convert PML to JSON |
| `python -m cli.mill --project my_project --no-clean` | Generate G-code and SVG blueprint |
| `python -m cli.validate_cam --recipe docs/recipes/01_simple_profile --summary` | Validate CAM outputs |
| `python -m cli.nest job.nest.yml -o output/ --export-svg` | Run nesting |
| `python -m cli.parse_compositional_pml door.pml.yml --resolve --format pml` | Parse compositional PML |

---

## Data Models

### LayoutAST (layout_ast/layout.py)

| Dataclass | Fields |
|-----------|--------|
| Sheet | width_mm, height_mm, thickness_mm |
| Placement | center_xy_mm: tuple[float, float] |
| Geometry | data: dict[str, Any] |
| Feature | type, depth_mm, side, is_through, corner_cleanup_tool_diameter_mm, tab_count, tab_height_mm, tab_width_mm, bevel_width_mm, bevel_angle_deg, bevel_inner_depth_mm, chamfer_width_mm, chamfer_angle_deg |
| Item | kind, type, geometry, placement, feature, params, shape_id, id |
| LayoutAST | sheet, items, config fields |

**Rule:** No separate classes for Rect/Circle/etc. Shape identity is `Item.type`. Parameters live in `Geometry.data`.

### RemovalIntent IR (ir/removal_intent.py)

| Dataclass | Fields |
|-----------|--------|
| DepthProfile | mode, z_top, z_bottom, gradient_direction_deg, v_angle_deg |
| Bounds2D | x_min, x_max, y_min, y_max |
| Allowance | inside, outside, on, kerf_compensation |
| Constraints | tabs, keepouts, islands, edge_treatment, tolerance_mm, safe_z_mm |
| RemovalIntent | region_id, bounds, depth_profile, allowance, constraints, metadata |

**Invariants:**
- Bounds2D: x_max >= x_min AND y_max >= y_min MUST hold.
- DepthProfile: z_bottom <= z_top MUST hold.

---

## Planner Hint Schema

Planner hints MUST follow this top-level schema:

```json
{
    "units": "mm",
    "kerf_width_mm": float,
    "min_channel_width_mm": float,
    "profiles": [<profile hint dict>],
    "pockets": [<pocket hint dict>],
    "holes": [<hole hint dict>],
    "engraves": [<engrave hint dict>]
}
```

**Profile hint required keys:** id, shape, geometry, center_xy_mm, depth_mm, side
**Profile hint optional keys:** tabs

**Pocket hint required keys:** id, shape, geometry, center_xy_mm, depth_mm
**Pocket hint optional keys:** start_depth_mm (only if z_top != 0)

**Planner consumption:**
- Profiles: reads geometry, center_xy_mm, depth_mm, side, tabs
- Pockets: reads shape, geometry, depth_mm, start_depth_mm
- Holes: reads geometry.diameter_mm, center_xy_mm, depth_mm

---

## Coordinate Conventions

- All internal values MUST be millimeters.
- XY: center-based coordinates. Stock origin is lower-left.
- Z: Positive away from material, negative into material.
- z_top typically 0.0 at stock surface.
- z_bottom MUST be negative for material removal.
- Compositional AST uses normalized coordinates (0.0–1.0) relative to parent region. MUST be resolved to absolute coordinates during layout resolution.

---

## Shapes and Features

### Supported Shapes

Rectangle, Circle, RoundedRect, Polygon, Polyline, Triangle, Arch, Line, SplinePath.

### Supported Features

| Feature | Description |
|---------|-------------|
| profile | Through-cut or partial depth. Side: inside, outside, on. |
| pocket | Partial-depth depression. |
| hole | Through-hole (subtractive). |
| engrave | Surface carving. |
| bevel | Angled edge cut with width, angle, and inner depth. |
| chamfer | Angled edge break with width and angle. |
| wave | Repeating wave texture pattern. |

### Tabs (Profile Feature)

```yaml
- Rect:
    id: cutout
    feature:
      type: profile
      depth: through
      side: outside
      tab_count: 4
      tab_height: 3mm
      tab_width: 12mm
    at:
      x: 300mm
      y: 200mm
      width: 400mm
      height: 250mm
```

---

## Layout Managers (Compositional PML)

| Manager | Parameters | Description |
|---------|------------|-------------|
| Frame | width | Inset border, auto-generates outer profile. |
| Inset | amount | Uniform inset on all sides. |
| Grid | rows, cols, gap | Grid-based component placement. |
| Cell | inset | Grid cell with optional inset. |
| Split | rows, cols, rail, mullion | Window-style split layout with rail/mullion widths. |
| Place | layout | Positioned children with explicit mapping. |
| Panel | id | Basic panel container. |
| Keepout | id | Exclusion zone (no machining). |

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

- One `.pml.yml` file per sheet with explicit part placements.
- `manifest.json` with utilization metrics.

---

## Validation

### IR-Level Validation (Implemented)

| Check | Description |
|-------|-------------|
| check_overlap() | 3D bounding-box intersection. |
| check_depth_feasibility() | z_top >= z_bottom, warns on depth vs thickness. |
| check_toolability() | Feature size vs tool diameter. |

### IR-Level Validation (Not Implemented)

The system MUST NOT claim these validations exist at IR level:
- Exact geometry intersection testing
- Pocket-corner reachability vs tool diameter
- Stepdown suitability vs material/tool
- Feed/speed validation
- Fixture/clamp interference beyond keepouts
- Tab placement feasibility
- Toolpath continuity optimization
- Exact kerf compensation validation

### CAM Artifact Validation

| Artifact | Metrics |
|----------|---------|
| SVG | Dimensions, layers, path counts, element breakdown. |
| G-code | Motion counts, distances, Z-profile, feeds, tools. |

---

## Directory Structure

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
├── mill_mcp/           # MCP server for IDE integration
├── nesting/            # Bin-packing algorithms (guillotine, maxrects)
├── pml/                # PML YAML parser and formatter
├── resolution/         # Compositional → Flat layout resolution
├── templates/          # Parametric component templates
├── validation/         # IR and CAM artifact validation
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

## Test Coverage

| Function | Coverage |
|----------|----------|
| parse_compositional_pml() | Well tested |
| resolve_layout() | Well tested |
| ast_to_removal_intents() | Tested (test_ast_to_removal.py) |
| item_to_removal_intent() | Tested |
| removal_intents_to_hints() | Well tested |
| IR validation functions | Tested |
| plan_passes() | Tested |
| write_gcode() | Tested |

---

## Known Issues

1. `frame` auto-generates outer profile. Using `rect outer profile` + `frame` creates two profiles.

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
python -m pytest tests/ -x                  # All tests
python -m pytest tests/test_pml_yaml.py     # PML parser tests
python -m pytest tests/test_ast_to_removal.py  # IR tests
python -m tests.test_recipes                # Recipe verification
```

---

## Adapter Modules

- `adapters/ast_to_removal.py` is the canonical AST→IR adapter.
- `adapters/hints_to_removal.py` contains shared converters for hint dict ↔ RemovalIntent transformations.
- `adapters/removal_to_planner.py` converts RemovalIntent → hint dict for the planner.

---

## AI Instructions

When modifying this repository:
- Treat this document as authoritative for described behaviors.
- Preserve all stated invariants (units, coordinate conventions, IR semantics).
- Do not change planner hint dict structure unless the planner interface changes.
- Do not infer unspecified behavior.
- If a change affects the canonical pipeline stages, update this document in the same commit.
