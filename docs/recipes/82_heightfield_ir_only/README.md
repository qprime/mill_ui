# 82 — Heightfield IR Only

Demonstrates the `Heightfield` PML node and its passage through the pipeline down to `RemovalIntent` + blueprint preview.

This recipe is **IR-only**: no G-code is generated for the heightfield. The planner pass for relief carving is tracked in issue #3 (finish) and #2 (rough).

## What this exercises

- `Heightfield` PML node parsing + formatting round-trip
- `HeightfieldGen` AST node → `HeightfieldParams` → flat `Item` with `feature.type=heightfield` and `Geometry.data` carrying the image reference
- `RemovalIntent.depth_profile.mode == "heightfield"` with `image_path` + `white_is_high`
- Strict validation: 16-bit single-channel PNG, square-pixel check (ε=1e-4), depth ≤ sheet thickness
- Blueprint SVG overlay on `HEIGHTFIELD_OVERLAYS` layer — base64 PNG embedded for deterministic output

## Scope exclusions

- No G-code output — heightfield intents are skipped at `removal_intents_to_planner_input` with a structured warning
- Golden metrics stubbed; the recipe runner prints a stderr banner when it detects a `HeightfieldGen` node

## Assets

`input/relief_dome.png` — 128×128 16-bit grayscale synthetic radial gradient. Committed alongside the PML per the `generators/svg/` precedent of referenced-asset recipes.
