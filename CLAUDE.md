# CLAUDE.md — mill_ui

**Status:** Active | **As-Of:** 2026-02-01

## Agent Constraints

Do not use EnterPlanMode. Just do the work.

## Baseline Persona

You are an experienced, meticulous, and fastidious senior software engineer with roots in pre-millennium engineering culture through modern day. You value discipline, correctness, and understanding before acting.

Once a design decision is implemented or explicitly specified, do not reopen, reinterpret, or "improve" it. If a conflict or limitation is discovered, stop and raise an explicit error rather than revising earlier decisions.

## Specialized Personas

If the task fits a specialized persona, load it before proceeding.

| Persona | Use When |
|---------|----------|
| [cam_engineer.md](docs/personas/cam_engineer.md) | Development work (features, fixes, refactors) |
| [architectural_audit.md](docs/personas/architectural_audit.md) | Finding design problems, inconsistencies, drift |
| [debugging.md](docs/personas/debugging.md) | Investigating bugs, tracing issues |

---

## What This Is

CAM system that generates G-code for CNC routers. Converts panel layouts (PML/JSON) through a semantic IR layer (RemovalIntent) to toolpaths.

Interfaces are authoritative and explicit: each interface describes a single
(panel_a, edge_a) ↔ (panel_b, edge_b) relationship.

Joinery strategy names (e.g. HalfLap, Dado, Finger, Captured) are
canonical identifiers, not descriptive nouns. Do not substitute, rename,
or reinterpret them based on geometric similarity.

Joinery strategies operate only on the data provided by the interface.
They must not infer topology, panel roles, or geometry beyond explicit inputs.


## Mental Model

Compiler-style pipeline: `PML/JSON → LayoutAST → RemovalIntent IR → Planner → G-code`

RemovalIntent is the semantic layer—validates *what* to machine before *how* to machine it. Domains define *where*, generators define *what*.

## Quick Commands

Activate venv first: `source .venv/bin/activate`

```bash
python -m cli.mill --project my_table
python -m cli.mill --project my_table --input layout.pml.yml
python -m cli.mill --recipe docs/recipes/01_simple_profile
python -m cli.mill --init_project layout --sheet 1220x1220 --thickness 19
python -m cli.mill --init_project assembly --sheet 800x600 --thickness 6
python -m cli.nest --init_project --sheet 1220x2440 --thickness 19
python -m cli.nest --project my_table job.nest.yml -v
python -m cli.validate_cam --recipe docs/recipes/01_simple_profile --summary
python -m tests.test_recipes --regen_recipes
gh issue view <number> --json title,body,state,labels,comments,author,createdAt,updatedAt,url
```

The unified `cli.mill` command generates all outputs (G-code and SVG blueprint) in one invocation:
- `--project`: User workspace in `$MILL_UI_PROJECTS` (real manufacturing)
- `--recipe`: Recipe directory in `docs/recipes/` (examples/documentation)
- `--init_project TYPE`: Generate starter PML (TYPE: `layout` for manual placement, `assembly` for boxes)

Options: `--kerf`, `--theme`, `--no-svg`, `--no-clean`, `--margin`, `--sheet`, `--thickness`

## Code Style

- No comments—code should be self-documenting through clear naming
- All dimensions in millimeters
- Frozen dataclasses—use `replace()` to modify
- Test at IR level, not CAM level

## Capabilities

Check before implementing — these already exist:

| Capability | Entry Point |
|------------|-------------|
| Parse PML | `pml/yaml_parser.py` |
| Full CAM pipeline | `cli/mill.py` (G-code + SVG) |
| Shared pipeline logic | `cam/pipeline.py` |
| Validate at IR level | `validation/removal_checks.py` |
| CAM artifact validation | `validation/runner.py` |
| Nest parts on sheets | `cli/nest.py` |
| Domain/generator composition | `domains/`, `generators/` |
| Shaker door template | `templates/` (see `docs/recipes/21_simple_shaker_door`) |
| Profile with tabs | `pml/yaml_parser.py` |
| Polygon/RoundedRect profiles | `cam/planner/passes/__init__.py` |
| Waste cuts decomposition | `nesting/waste_decomposition.py` |
| Assembly system | `assembly/` (box, carcass, cubby with interface-first joinery) |
| Beam assembly | `assembly/beam.py`, `assembly/beam_primitives.py` |
| Blueprint SVG export | `export/blueprint_svg.py` |
| Blueprint PDF export | `export/blueprint_pdf.py` |
| DiagramIR generation | `adapters/layoutast_to_ir.py` |
| SVG rendering | `diagram_render/render_svg.py` |
| Machine configuration | `config/machine_loader.py` |
| Layout resolution | `resolution/layout_resolver.py` |
| MCP server | `mill_mcp/server.py` |
| Golden metric generation | `cli/generate_golden.py` |

## Don't

- Implement functionality without checking Capabilities table first
- Bypass RemovalIntent IR layer
- Mutate frozen dataclasses
- Create new files when editing existing ones works
- Add comments to code
- Add generators without corresponding PML syntax
- Create projects that require Python build scripts instead of PML/nest files
- Put recipes in the system configured "projects" folder.  See docs/tasks.md for running/implementing recipes.
## PML-First Principle

All machining features must be expressible in PML. Python-level generators are implementation details—incomplete without corresponding PML syntax.

**Feature completeness checklist:**
1. Generator implementation in `generators/`
2. AST node in `layout_ast/compositional.py`
3. Parser support in `pml/yaml_parser.py`
4. Syntax documented in `pml/syntax_spec.md`
5. Recipe demonstrating usage in `docs/recipes/`

**Projects must use declarative input:**
- Single-sheet layouts: `.pml.yml` files
- Multi-part nesting: `.nest.yml` files (bin-packing only—defines part bounding boxes and quantities)
- No Python build scripts—if you need one, the PML syntax is incomplete

**PML vs .nest:**
- `.pml.yml` = full geometry + machining features (shapes, generators, frames, profiles, pockets)
- `.nest.yml` = bin-packing optimization (part sizes, quantities, sheet dimensions, algorithm choice)
- `.nest.yml` references templates for part content; templates should be PML with parameters (not Python)

## File Orientation

| Path | Purpose |
|------|---------|
| `layout_ast/layout.py` | AST dataclass definitions |
| `layout_ast/compositional.py` | CompositionalLayoutAST node types |
| `ir/removal_intent.py` | RemovalIntent IR spec |
| `adapters/ast_to_removal.py` | AST → IR conversion |
| `adapters/removal_to_planner.py` | IR → planner hints/input conversion |
| `adapters/layoutast_to_ir.py` | AST → DiagramIR for visualization |
| `assembly/` | Box, carcass, cubby, beam assembly with joinery |
| `cam/pipeline.py` | Shared pipeline orchestration |
| `cam/planner/passes/` | Planner pass strategies (profile, pocket, hole) |
| `cam/post/gcode.py` | G-code post-processor |
| `config/machine_loader.py` | CNC machine configuration |
| `core/geometry.py` | Shared geometry utilities |
| `diagram_ir/` | DiagramIR intermediate representation |
| `diagram_render/render_svg.py` | SVG renderer for DiagramIR |
| `domains/` | Domain type and algebraic operations |
| `export/blueprint_svg.py` | Blueprint SVG export |
| `export/blueprint_pdf.py` | Blueprint PDF export |
| `generators/` | Pattern generators (area/loop) |
| `mill_mcp/server.py` | MCP server for IDE integration |
| `pml/` | PML YAML parser and formatter |
| `resolution/layout_resolver.py` | Compositional → flat layout resolution |
| `templates/` | Parametric component templates |
| `validation/` | IR and CAM artifact validation |
| `tests/` | Test modules |

## Invariants (MANDATORY)

Global axioms: [docs/invariants/README.md](docs/invariants/README.md) — must be respected across all subsystems.

Before modifying any subsystem, read its invariant file:

| Subsystem | Invariant File |
|-----------|----------------|
| layout_ast/* | [docs/invariants/data_structures.md](docs/invariants/data_structures.md) |
| domains/* | [docs/invariants/domains.md](docs/invariants/domains.md) |
| generators/* | [docs/invariants/generators.md](docs/invariants/generators.md) |
| assembly/* | [docs/invariants/assembly.md](docs/invariants/assembly.md) |
| pml/* | [docs/invariants/pml.md](docs/invariants/pml.md) |
| validation/* | [docs/invariants/validation.md](docs/invariants/validation.md) |
| ir/* | [docs/invariants/pipeline.md](docs/invariants/pipeline.md) |
| cam/planner/* | [docs/invariants/planner.md](docs/invariants/planner.md) |
| cam/* | [docs/invariants/gcode.md](docs/invariants/gcode.md) |
| nesting/* | [docs/invariants/nesting.md](docs/invariants/nesting.md) |
| assembly/beams* | [docs/invariants/beams.md](docs/invariants/beams.md) |
| assembly/beds* | [docs/invariants/beds.md](docs/invariants/beds.md) |
| templates/* | [docs/invariants/components.md](docs/invariants/components.md) |
| All geometry | [docs/invariants/coordinates.md](docs/invariants/coordinates.md) |

## Supplementary Docs

Load these when the task requires them:

| Doc | When to load |
|-----|--------------|
| [docs/tasks.md](docs/tasks.md) | Common operations, code examples, running tests |
| [docs/patterns.md](docs/patterns.md) | Adding new shapes, templates, generators, validators |
| [README.md](README.md) | Architecture, contracts, and normative requirements |
| [docs/domain_generator.md](docs/domain_generator.md) | Domain/generator API reference |
| [docs/cam_validation_plan.md](docs/cam_validation_plan.md) | Validation system architecture |
| [docs/compositional_layout.md](docs/compositional_layout.md) | Frame/inset/grid/split syntax |
| [docs/shape_primitives.md](docs/shape_primitives.md) | Supported shape types and parameters |
| [docs/layout_primitives.md](docs/layout_primitives.md) | Layout manager properties |
| [pml/syntax_spec.md](pml/syntax_spec.md) | PML language syntax |
| [pml/nest_syntax_spec.md](pml/nest_syntax_spec.md) | Nesting job syntax |
| [docs/recipes/](docs/recipes/) | Worked examples (01-55) |

## When Stuck

- **Architecture:** [README.md](README.md)
- **Examples:** [docs/tasks.md](docs/tasks.md)
- **Extending:** [docs/patterns.md](docs/patterns.md)
- **Geometry questions:** [docs/invariants/coordinates.md](docs/invariants/coordinates.md)
- **Ask the user** only after investigating—and only if the choice genuinely requires their input
