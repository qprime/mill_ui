# cliff_ai

Owner path: .

## 1. What this is

cliff_ai is an AI-first operations stack that unifies documentation, machining, and service orchestration.
The root package holds the shared entrypoints, metadata rules, and automation all other modules rely on.

## 2. When to use it

- Bring up the full cliff stack locally (web UI, skills, background services).
- Generate AI-ready project snapshots or dependency graphs before a change.
- Execute CAM jobs or living-document workflows from a single dispatcher.

## 3. How to run

Install in editable mode and invoke the run.py dispatcher from the repository root.

```bash
python -m pip install -e .
python run.py web
python run.py compose_cam demo_vine_border --stl
python run.py services list
```

## 4. Inputs & outputs (for AI & humans)

- `memories/index.jsonl` — append-only memory ledger secured by SHA-256 chain.
- `memories/cam_projects/` — project manifests, sheet layouts, and generated CAM artifacts.
- `skills/living_truth_partner/living_docs/` — LTD source docs, export history, and persona prompts.
- `services/service_registry.json` — declared systemd units consumed by the services CLI.
- `docs/_reports/readme_sweep.json` — machine-readable report emitted by the README sweeper.

## 5. Public surface

- `python run.py web` — start the TLS-enabled Flask interface defined in `interfaces.app`.
- `python run.py compose_cam <sheet_slug> [--stl]` — generate toolpaths and exports for a sheet layout.
- `python run.py services <command>` — proxy into `services.cli` for systemd operations.
- `python run.py tests` — execute curated repo tests via `tools.test_runner`.
- `python run.py context_bundle --root .` — assemble persona-aware project context bundle.
- `python run.py watch_context --root .` — watch source and rebuild context bundle on change.
- `python run.py context_cache --root .` — rebuild deterministic context caches (file tree, deps, symbols, docs, tests).
  (AceControl and related endpoints have been removed in favor of a stateless chat flow.)

## 6. Invariants & guardrails

- Always run commands from the repository root so metadata headers resolve correctly.
- `memories/index.jsonl` is append-only; never rewrite or reorder entries.
- Default execution assumes `OFFLINE=1`; external calls must be whitelisted explicitly.
- Source files and READMEs must retain their top-of-file metadata headers for tooling.

## 7. Extension points

- Add new CLI entrypoints by extending the `ENTRYPOINTS` map in `run.py`.
- Register additional skills under `skills/` with metadata headers and update their README.
- Wire new web modules by creating an app manifest under `interfaces/apps/` and updating `app_registry`.
- Teach the doc sweeper about new modules by adding specs in `tools/docs/sweep_readmes.py`.

## 8. AI reading order

- `run.py` — Dispatch table for all CLI entrypoints.
- `continuum/project_graph.py` — Builds module graph metadata and token stats.
- `memories/memory_manager.py` — High-level helpers for ledger access and chat logs.
- `interfaces/app_registry.py` — Registers Flask blueprints and UI modules.
- `services/cli.py` — Systemd-aware service manager CLI.
- `skills/mill_ui/apps/compose_cam.py` — Sheet layout CAM pipeline.
- `tools/context_builder.py` — Generates cleaned context snapshots for AI.
