---
description: Write PML (.pml.yml) and nest (.nest.yml) files. Use when the user asks you to create or modify PML layouts, assemblies, nesting jobs, or any declarative machining input.
---

# PML Author

You are writing PML — declarative YAML input files for a CNC CAM system. You are NOT writing Python code. Your output is `.pml.yml` or `.nest.yml` files.

## Before Writing

1. Read the full PML syntax specification: `pml/syntax_spec.md`
2. If the user's request involves a pattern you haven't seen, scan relevant recipes in `docs/recipes/` for working examples
3. For nest files, check `docs/recipes/17_nesting_guillotine/cabinet_job.nest.yml` or `docs/recipes/18_nesting_maxrects/cabinet_job.nest.yml`

## Critical Rules

- All dimensions use `mm` suffix: `100mm`, `50.5mm`
- `at.x` and `at.y` specify part **center**, not edge
- Coordinates are in **working-area space** — (0,0) is the corner of the cuttable zone, not the physical sheet
- `depth: through` is the keyword for full-thickness cuts
- Keep part edges ~10mm from working area boundaries for outside profiles
- Use `physical_width`/`physical_height` for sheet size, or `working_width`/`working_height` for direct working-area specification
- Features can be inline (`feature:` block on a shape) or as generator children (`children:` list with Profile, Pocket, etc.)
- Profiles default to no tabs — add `tab_count`, `tab_height` explicitly if needed

## Validation

After writing a PML file, validate it by running:

```bash
source .venv/bin/activate
python -m cli.mill --recipe <path> --no-svg
```

Or for project files:
```bash
python -m cli.mill --project <name>
```

For nest files:
```bash
python -m cli.nest --project <name> <nest_file>
```

Fix any errors before presenting the result to the user.

## Output

- Write the file directly — don't show it and ask for approval
- Run validation
- If validation fails, fix and re-run
- Report success with a brief description of what was generated
