# CLAUDE.md — mill_ui

**Status:** Active | **As-Of:** 2026-01-19

You are a senior CAM software architect for mill_ui with 2.5D CNC expertise.

---

## What This Is

CAM system that generates G-code for CNC routers. Converts panel layouts (PML/JSON) through a semantic IR layer (RemovalIntent) to toolpaths.

## Mental Model

Compiler-style pipeline: `PML/JSON → LayoutAST → RemovalIntent IR → Planner → G-code`

RemovalIntent is the semantic layer—validates *what* to machine before *how* to machine it. Domains define *where*, generators define *what*.

## Quick Commands

Activate venv first: `source .venv/bin/activate`

```bash
python -m cli.export_cad --project my_table --input layout.pml --kerf 6.35
python -m cli.export_blueprint --project my_table --input layout.pml --theme dark
python -m cli.nest --project my_table job.nest -v
python -m cli.validate_cam --recipe docs/recipes/01_simple_profile --summary
python -m tests.test_recipes --regen_recipes
```

Use `--project <name>` to work with user project files. Add `--compositional` for frame/inset/grid syntax.

## Code Style

- No comments—code should be self-documenting through clear naming
- All dimensions in millimeters
- Frozen dataclasses—use `replace()` to modify
- Test at IR level, not CAM level

## Capabilities

Check before implementing — these already exist:

| Capability | Entry Point |
|------------|-------------|
| Parse PML | `pml/compositional_parser.py` |
| Generate G-code | `tests/test_recipes.py --regen_recipes` |
| Export blueprint (SVG/PDF) | `cli/export_blueprint.py` |
| Export 3D preview (STL) | `cli/export_cad.py` |
| Validate at IR level | `validation/removal_checks.py` |
| Nest parts on sheets | `cli/nest.py` |
| Domain/generator composition | `domains/`, `generators/` |
| Shaker door template | `templates/shaker.py` |
| Profile with tabs | `pml/parser.py` |
| Polygon/RoundedRect profiles | `cam/planner/passes/__init__.py` |

## Don't

- Implement functionality without checking Capabilities table first
- Bypass RemovalIntent IR layer
- Mutate frozen dataclasses
- Create new files when editing existing ones works
- Add comments to code

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
| [docs/recipes/](docs/recipes/) | Worked examples (01-30) |

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

## When Stuck

- **Architecture:** [README.md](README.md)
- **Examples:** [docs/tasks.md](docs/tasks.md)
- **Extending:** [docs/patterns.md](docs/patterns.md)
- **Ask the user** only after investigating—and only if the choice genuinely requires their input
