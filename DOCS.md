# Documentation Rules

When code changes, update affected documentation in the same commit.

## Algorithm

1. **What changed?** → Update docs that describe it
2. **New capability?** → CLAUDE.md Capabilities table
3. **User-visible change?** → README.md
4. **New pattern or pitfall?** → CLAUDE.md
5. **Syntax change?** → pml/syntax_spec.md + affected recipes
6. **Pipeline change?** → docs/WORKFLOW.md

## Validation

```bash
python scripts/check_doc_links.py
```

CI fails on broken links or invalid code examples.
