# Skills Library

Owner path: skills/

## 1. What this is

Skills houses domain-specific automation modules spanning CAM, image generation, and living documents.
It standardises entrypoints and metadata for capabilities beyond the core platform.

## 2. When to use it

- Invoke specialised pipelines such as CAM planning or persona-driven image generation.
- Wire new skills into CLI entrypoints or background services.
- Share reusable domain code across interfaces, memories, and services.

## 3. How to run

Run packaged CLIs through `run.py` or import the skill APIs directly.

```bash
python run.py compose_cam demo_vine_border --stl
python -m skills.image_pipeline.generate_image demo_vine_border
python run.py ltp sections test_document
python run.py mill_ui_tests
```

## 4. Inputs & outputs (for AI & humans)

- `skills/mill_ui/` — primary CAD/CAM modules, planners, and native bindings.
- `skills/image_pipeline/` — persona and style aware image generation pipeline.
- `skills/living_truth_partner/` — living-doc orchestration for LTD workflows.
- `memories/cam_projects/` — project inputs consumed by CAM skills.
- `cortex/personas/` — shared persona/style metadata consumed across skills.

## 5. Public surface

- `skills.mill_ui.apps.compose_cam` — CLI entrypoint for sheet CAM generation.
- `skills.mill_ui.api` — Python API facade for CAM, CAD, and IO modules.
- `skills.image_pipeline.generate_image.generate_dalle_image(project)` — persona image generator.
- `skills.living_truth_partner.cli.api(argv)` — manage living-doc workflows.

## 6. Invariants & guardrails

- Each skill module exposes a single public API symbol and metadata header.
- CAM operations assume millimetres and safe-Z defaults defined in `compose_cam`.
- Image pipeline requires valid personas/styles; keep configs in sync with cortex metadata.
- Skills should remain pure where possible; external side effects land under `memories/`.

## 7. Extension points

- Add new CAM strategies under `skills/mill_ui/cam/ops` and expose them via `api.cam`.
- Drop new persona/style packs under `skills/image_pipeline/` and extend loaders accordingly.
- Compose additional CLIs by exposing `api()` functions and wiring `run.py` to them.
- Document new skills here and add their specs to the sweeper configuration.

## 8. AI reading order

- `skills/mill_ui/apps/compose_cam.py` — CLI orchestrator for sheet layout CAM.
- `skills/mill_ui/api/cam.py` — Public CAM API surface.
- `skills/image_pipeline/generate_image.py` — Persona-aware image generator.
- `skills/living_truth_partner/cli.py` — Living Truth Partner command routing.
- `skills/cam_engine/cli.py` — Alternate CAM engine CLI wrapper.
