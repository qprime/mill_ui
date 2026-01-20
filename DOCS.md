# Documentation Rules

When code changes, update affected documentation in the same commit.

## Update Triggers

| When you change... | Update these |
|-------------------|--------------|
| Pipeline stages | README.md, docs/WORKFLOW.md |
| Data models (LayoutAST, RemovalIntent) | README.md |
| PML syntax | pml/syntax_spec.md, affected recipes |
| Layout managers | docs/compositional_layout.md, docs/layout_primitives.md |
| Shapes | docs/shape_primitives.md |
| Validation logic | docs/cam_validation_plan.md |
| Domain/generator API | docs/domain_generator.md |
| New capability | CLAUDE.md Capabilities table |
| New pattern/pitfall | CLAUDE.md, docs/patterns.md |
| CLI commands | README.md Quick Commands |

## Validation

```bash
python scripts/check_doc_links.py       # Broken links
python scripts/validate_pml_examples.py # PML code blocks
```

CI fails on broken links or invalid code examples.
