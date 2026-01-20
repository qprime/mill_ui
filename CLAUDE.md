# CLAUDE.md — mill_ui

**Status:** Active | **As-Of:** 2026-01-19

---

## What This Is

CAM system that generates G-code for CNC routers. Converts panel layouts (PML/JSON) through a semantic IR layer (RemovalIntent) to toolpaths.

**User projects:** `/home/squinlan/cliff_ai/memories/cam_projects/mill_ui`

## Mental Model

Compiler-style pipeline: `PML/JSON → LayoutAST → RemovalIntent IR → Planner → G-code`

RemovalIntent is the semantic layer—validates *what* to machine before *how* to machine it. Domains define *where*, generators define *what*.

## Quick Commands

```bash
python -m cli.convert_layout --from pml --to json input.pml output.json
python -m cli.export_cad --input layout.pml --out output/ --kerf 6.35 --quality high
python -m cli.export_blueprint --input layout.pml --out output/ --theme dark
python -m cli.validate_cam --recipe docs/recipes/01_simple_profile --summary
python -m cli.nest job.nest -o output/ -v
```

Add `--compositional` for frame/inset/grid syntax.

## Code Style

- No comments—code should be self-documenting through clear naming
- All dimensions in millimeters
- Frozen dataclasses—use `replace()` to modify
- Test at IR level, not CAM level

## Don't

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

## Token Efficiency

- File contents in `<system-reminder>` tags are already in context—don't re-read
- On clear directives, execute directly rather than exploring first
- Minimize tool calls: edit → test → done

## When Stuck

- **Architecture:** [README.md](README.md)
- **Examples:** [docs/tasks.md](docs/tasks.md)
- **Extending:** [docs/patterns.md](docs/patterns.md)
- **Ask the user** if multiple valid approaches exist or requirements are unclear
