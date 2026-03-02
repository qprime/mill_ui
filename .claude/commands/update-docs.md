---
description: Ensure documentation stays in sync with code changes. Use when modifying pipeline stages, data models, PML syntax, layout managers, shapes, validation, domain/generator APIs, capabilities, or CLI commands.
---

# Update Documentation

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
| New pattern/pitfall | docs/patterns.md |
| CLI commands | README.md Quick Commands |
