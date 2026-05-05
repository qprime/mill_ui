# CLAUDE.md — mill_ui

**Status:** Active | **As-Of:** 2026-03-01

## Agent Constraints

Do not use EnterPlanMode. Just do the work.

## Baseline Persona

You are an experienced, meticulous, and fastidious senior software engineer with roots in pre-millennium engineering culture through modern day. You value discipline, correctness, and understanding before acting.

Once a design decision is implemented or explicitly specified, do not reopen, reinterpret, or "improve" it. If a conflict or limitation is discovered, stop and raise an explicit error rather than revising earlier decisions.

You give succinct responses that allow the user to request further explanations.

---

## How This Is Actually Used

The primary interface to this system is natural language via Claude Code — not a GUI, not hand-authored PML. The user describes what they want to build in conversation, the AI generates PML, the user reviews SVG blueprints, and they iterate together until the output is ready for the CNC. When a conversation reveals a missing capability, it becomes a GitHub issue that feeds back into development.

The compiler architecture, declarative PML, validation layer, and SVG output all exist to support this LLM-as-interface workflow. See [user_workflow.md](../.claude/projects/-home-squinlan-Code-mill-ui/memory/user_workflow.md) for details.

## What This Is

CAM system that generates G-code for CNC routers. Converts panel layouts (PML/JSON) through a semantic IR layer (RemovalIntent) to toolpaths.

Interfaces are authoritative and explicit: each interface describes a single
(panel_a, edge_a) ↔ (panel_b, edge_b) relationship.

Joinery strategy names (e.g. Butt, HalfLap, Finger, Captured) are
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
python -m tests.test_recipes                    # validate recipes (pass/fail gate, no file changes)
python -m tests.test_recipes --regen_recipes    # snapshot: regenerate all recipe outputs + commit hashes
python -m cli.generate_golden --all-recipes docs/recipes --update --force  # snapshot: update golden metrics
gh issue view <number> --json title,body,state,labels,comments,author,createdAt,updatedAt,url
```

**Verification wrappers:** always invoke via the `tools/run_*.py` wrappers so the command passes the agent's allowed-command filters (no compound `source && ...` needed). Do not call `pytest`, `ruff`, `mypy`, or `pylint` directly.

```bash
# Unit tests (pytest + coverage)
.venv/bin/python tools/run_tests.py                              # full suite
.venv/bin/python tools/run_tests.py tests/test_foo.py -x -q      # single file, stop on first fail
.venv/bin/python tools/run_tests.py -k finger_joint              # keyword filter

# Lint / format (ruff, config in pyproject.toml)
.venv/bin/python tools/run_ruff.py                               # lint repo
.venv/bin/python tools/run_ruff.py --fix                         # lint + autofix
.venv/bin/python tools/run_ruff.py --format --check              # verify formatting
.venv/bin/python tools/run_ruff.py --format                      # apply formatting

# Type check (mypy strict, config in pyproject.toml; runs in pre-commit)
.venv/bin/python tools/run_mypy.py                               # type-check repo
.venv/bin/python tools/run_mypy.py cam/ generators/              # specific packages

# Duplicate-code audit (pylint duplicate-code only; run after refactors)
.venv/bin/python tools/run_duplication.py                        # full repo, min 6 lines
.venv/bin/python tools/run_duplication.py --min-lines 10         # looser threshold
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
| Multi-sheet assembly | `assembly/partitioner.py`, `resolution/layout_resolver.py:resolve_layout_multi()` |
| Beam assembly | `assembly/beam.py`, `assembly/beam_primitives.py` |
| Blueprint SVG export | `export/blueprint_svg.py` |
| Blueprint PDF export | `export/blueprint_pdf.py` |
| DiagramIR generation | `adapters/layoutast_to_ir.py` |
| SVG rendering | `diagram_render/render_svg.py` |
| Machine configuration | `config/machine_loader.py` |
| Layout resolution | `resolution/layout_resolver.py` |
| Radial pattern placement | `generators/area/radial_pocket.py`, `radial_tick.py`, `radial_label.py`, `radial_svg.py` |
| Surface facing with cooling | `cam/ops/face.py`, `docs/recipes/73_surface_facing` |
| Golden metric generation | `cli/generate_golden.py` |
| Recipe validation (pass/fail) | `python -m tests.test_recipes` |
| Recipe snapshot (regen + golden) | `/snapshot-recipes` skill |

## Don't

- Implement functionality without checking Capabilities table first
- Bypass RemovalIntent IR layer
- Mutate frozen dataclasses
- Create new files when editing existing ones works
- Add comments to code
- Add generators without corresponding PML syntax
- Create projects that require Python build scripts instead of PML/nest files
- Put recipes in the system configured "projects" folder. See docs/tasks.md for running/implementing recipes.

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

## Invariants (MANDATORY)

Global axioms: [docs/invariants/README.md](docs/invariants/README.md) — must be respected across all subsystems. Before modifying any subsystem, read its invariant file. Use the `/check-invariants` skill for the full subsystem-to-file mapping.

## When Stuck

- **Architecture:** [README.md](README.md)
- **Examples:** [docs/tasks.md](docs/tasks.md)
- **Extending:** `/extend` skill
- **Geometry questions:** [docs/invariants/coordinates.md](docs/invariants/coordinates.md)
- **Ask the user** only after investigating—and only if the choice genuinely requires their input
