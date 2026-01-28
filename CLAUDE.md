# CLAUDE.md — mill_ui

**Status:** Active | **As-Of:** 2026-01-22

You are a senior CAM software architect for mill_ui with 2.5D CNC expertise.  You are fastidious about checking the current code and documetation before writing issue or starting development or fixing bugs.

---

## What This Is

CAM system that generates G-code for CNC routers. Converts panel layouts (PML/JSON) through a semantic IR layer (RemovalIntent) to toolpaths.

## Mental Model

Compiler-style pipeline: `PML/JSON → LayoutAST → RemovalIntent IR → Planner → G-code`

RemovalIntent is the semantic layer—validates *what* to machine before *how* to machine it. Domains define *where*, generators define *what*.

## Quick Commands

Activate venv first: `source .venv/bin/activate`

```bash
python -m cli.mill --project my_table
python -m cli.mill --project my_table --input layout.pml.yml
python -m cli.mill --recipe docs/recipes/01_simple_profile
python -m cli.nest --project my_table job.nest.yml -v
python -m cli.validate_cam --recipe docs/recipes/01_simple_profile --summary
python -m tests.test_recipes --regen_recipes
```

The unified `cli.mill` command generates all outputs (G-code and SVG blueprint) in one invocation:
- `--project`: User workspace in `$MILL_UI_PROJECTS` (real manufacturing)
- `--recipe`: Recipe directory in `docs/recipes/` (examples/documentation)

Options: `--kerf`, `--theme`, `--no-svg`, `--no-clean`

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
| Nest parts on sheets | `cli/nest.py` |
| Domain/generator composition | `domains/`, `generators/` |
| Shaker door template | `templates/shaker.py` |
| Profile with tabs | `pml/yaml_parser.py` |
| Polygon/RoundedRect profiles | `cam/planner/passes/__init__.py` |
| Waste cuts decomposition | `nesting/waste_decomposition.py` |
| Box generator (finger/dado) | `generators/assemblies/box.py` |

## Don't

- Implement functionality without checking Capabilities table first
- Bypass RemovalIntent IR layer
- Mutate frozen dataclasses
- Create new files when editing existing ones works
- Add comments to code
- Add generators without corresponding PML syntax
- Create projects that require Python build scripts instead of PML/nest files
- put Recipes in the system configured "projects" folder.  See docs/task.md for running/implementing recipes.
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
| `ir/removal_intent.py` | RemovalIntent IR spec |
| `adapters/ast_to_removal.py` | AST → IR conversion |
| `templates/` | Parametric component generators |
| `domains/` | Domain type and algebraic operations |
| `generators/` | Pattern generators (area/loop) |
| `validation/` | CAM artifact validation |
| `pml/` | PML parser and formatter |
| `tests/` | Test modules |

## Supplementary Docs

Load these when the task requires them:

| Doc | When to load |
|-----|--------------|
| [docs/tasks.md](docs/tasks.md) | Common operations, code examples, running tests |
| [docs/patterns.md](docs/patterns.md) | Adding new shapes, templates, generators, validators |
| [docs/invariants.md](docs/invariants.md) | Before modifying core behavior |
| [README.md](README.md) | Architecture, contracts, and normative requirements |
| [docs/domain_generator.md](docs/domain_generator.md) | Domain/generator API reference |
| [docs/cam_validation_plan.md](docs/cam_validation_plan.md) | Validation system architecture |
| [docs/compositional_layout.md](docs/compositional_layout.md) | Frame/inset/grid/split syntax |
| [docs/shape_primitives.md](docs/shape_primitives.md) | Supported shape types and parameters |
| [docs/layout_primitives.md](docs/layout_primitives.md) | Layout manager properties |
| [pml/syntax_spec.md](pml/syntax_spec.md) | PML language syntax |
| [pml/nest_syntax_spec.md](pml/nest_syntax_spec.md) | Nesting job syntax |
| [docs/recipes/](docs/recipes/) | Worked examples (01-32) |

## Working Style

**Investigate before asking.** When uncertain about how something works or whether a capability exists:
1. Search the codebase (grep for keywords, check relevant directories)
2. Read the actual implementation
3. Check docs/tasks.md and docs/patterns.md for examples
4. Reason from file/folder structure

Only ask the user when multiple valid approaches exist and the choice affects their workflow.

**Token efficiency:**
- File contents in `<system-reminder>` tags are already in context—don't re-read
- On clear directives with known implementation paths, execute directly
- Minimize tool calls: edit → test → done
- Design documents go in GitHub issues (`gh issue create`) unless otherwise directed

## When Stuck

- **Architecture:** [README.md](README.md)
- **Examples:** [docs/tasks.md](docs/tasks.md)
- **Extending:** [docs/patterns.md](docs/patterns.md)
- **Ask the user** only after investigating—and only if the choice genuinely requires their input
