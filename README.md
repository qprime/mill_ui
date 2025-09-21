# Mill UI Skill

Owner path: skills/mill_ui/

## 1. What this is

Mill UI is the manufacturing nucleus for sheet-based CAD/CAM planning.
It orchestrates templates, planners, and native accelerators to produce toolpaths and exports.

## 2. When to use it

- Generate toolpaths or exports for panelised sheet layouts.
- Prototype new CAM operations or composition templates.
- Run regression tests for the milling stack before shipping changes.

## 3. How to run

Use the compose_cam CLI for end-to-end jobs or invoke APIs during testing.

```bash
python run.py compose_cam demo_vine_border --stl
python run.py mill_ui_tests
python -m tools.context_builder skills.mill_ui --output skills/mill_ui/code_context.txt
```

The CLI exposes configuration-driven overrides:

```bash
python apps/compose_cam.py layouts/demo.json --tool-db ./tool_db.json --material MDF --safe-z 6 --z-ref top
CAM_TOOL_DB=./tool_db.json CAM_SAFE_Z=8 python apps/compose_cam.py layouts/demo.json
python apps/compose_cam.py layouts/demo.json --config configs/cam_defaults.json --merge-eps 0.02
```

## 4. Inputs & outputs (for AI & humans)

- `memories/cam_projects/sheet_layouts/<slug>/sheet.json` — sheet layout definitions consumed by compose_cam.
- `skills/mill_ui/cam/tools/tool_db.json` — tool library looked up by planners.
- `skills/mill_ui/compositions/` — template registries that expand layout items.
- `skills/mill_ui/cad/native/` — native CAD exporter for STL/STEP outputs.
- `skills/mill_ui/cam/native/` — native CAM backend for pocket/profile planners.

## 5. Public surface

- `skills.mill_ui.apps.compose_cam.main()` — CLI entrypoint for sheet layouts.
- `skills.mill_ui.api.cam.write_gcode(moves, ...)` — emit G-code via the native backend.
- `skills.mill_ui.api.cad.render_svg_with_dims(panel, path)` — generate dimensional SVG previews.
- `skills.mill_ui.cam.planner.passes.plan_passes(project)` — orchestrate planner pipeline stages.
- `skills.mill_ui.api.io.save_json(path, obj)` — persist canonical project artifacts.

## 6. Invariants & guardrails

- All linear dimensions are in millimetres; default safe-Z is 6.0 mm unless overridden by config/env/CLI.
- Tool database entries must include required tool IDs; compose_cam fails fast otherwise.
- Native CAD backends are optional. When unavailable, compose_cam emits a heightfield STL and skips STEP export with a clear demo-mode message.
- Layouts honour clearance/kerf conventions declared in composition templates.

## 7. Extension points

- Add templates under `skills/mill_ui/compositions/` and import them in `apps.compose_cam`.
- Register new CAM operations under `skills/mill_ui/cam/ops/` and expose them via `api.cam`.
- Extend native bindings by adding pybind11 code under `skills/mill_ui/cam/native/cpp/`.
- Document new planners or exporters here and in the sweeper specification.

## 8. AI reading order

- `skills/mill_ui/apps/compose_cam.py` — CLI orchestrator for sheet jobs.
- `skills/mill_ui/api/cam.py` — Public CAM API surface and registrations.
- `skills/mill_ui/cam/planner/passes/__init__.py` — High-level pass planning logic assembled from modular passes.
- `skills/mill_ui/cam/native/core.py` — Python shims for the native planner.
- `skills/mill_ui/cad/export/svg_dims.py` — Dimensional drawing exporter.

## 9. Configuration & Capabilities

- Configuration precedence is **CLI > environment > config.json > built-ins** via `skills.mill_ui.core.load_config`.
- Canonical CAD modules live under `skills.mill_ui.cad.*`; public consumers import via `skills.mill_ui.api` re-exports.
- `skills.mill_ui.core.capabilities.get_capabilities()` reports native backend availability so apps can enter demo mode without failing.
