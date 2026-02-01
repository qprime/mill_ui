# Personas

Personas are operational modes that overlay the baseline identity defined in CLAUDE.md.

## How Personas Work

1. **Baseline persona** is always active (defined in CLAUDE.md)
2. **Specialized personas** add task-specific behaviors and constraints
3. Activate a persona by saying "Use the [persona] persona" or loading the file
4. Personas don't replace system knowledge—they shape how you approach work

## Available Personas

| Persona | Use When |
|---------|----------|
| [cam_engineer.md](cam_engineer.md) | Development work (features, fixes, refactors) |
| [architectural_audit.md](architectural_audit.md) | Finding design problems, inconsistencies, drift |
| [debugging.md](debugging.md) | Investigating bugs, tracing issues |

## Creating New Personas

A persona file should include:
- **Role framing** — "You are an expert..."
- **Working style** — How to approach the task
- **Do / Don't** — Specific behavioral constraints
- **Output expectations** — What deliverables look like
- **Key invariant files** — Which invariants are most relevant

Keep personas focused. A persona that tries to do everything is just noise.
