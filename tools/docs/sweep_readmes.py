from __future__ import annotations

import argparse
import datetime as _dt
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from textwrap import dedent
from typing import Dict, Iterable, List, Sequence, Tuple


@dataclass(frozen=True)
class ReadmeSpec:
    path: str
    title: str
    owner: str
    what: str
    when: Sequence[str]
    how_text: str
    how_commands: Sequence[str]
    inputs: Sequence[str]
    surface: Sequence[str]
    invariants: Sequence[str]
    extensions: Sequence[str]
    ai_reading_order: Sequence[Tuple[str, str]]
    allow_long: bool = False
    extras: Sequence[str] = field(default_factory=tuple)


@dataclass(frozen=True)
class ValidationIssue:
    path: Path
    reason: str


README_SPECS: Dict[str, ReadmeSpec] = {
    "README.md": ReadmeSpec(
        path="README.md",
        title="cliff_ai",
        owner=".",
        what=dedent("""
            cliff_ai is an AI-first operations stack that unifies documentation, machining, and service orchestration.
            The root package holds the shared entrypoints, metadata rules, and automation all other modules rely on.
        """).strip(),
        when=[
            "Bring up the full cliff stack locally (web UI, skills, background services).",
            "Generate AI-ready project snapshots or dependency graphs before a change.",
            "Execute CAM jobs or living-document workflows from a single dispatcher.",
        ],
        how_text="Install in editable mode and invoke the run.py dispatcher from the repository root.",
        how_commands=[
            "python -m pip install -e .",
            "python run.py web",
            "python run.py compose_cam demo_vine_border --stl",
            "python run.py services list",
        ],
        inputs=[
            "`memories/index.jsonl` — append-only memory ledger secured by SHA-256 chain.",
            "`memories/cam_projects/` — project manifests, sheet layouts, and generated CAM artifacts.",
            "`living_docs/` — LTD source docs, export history, and persona prompts.",
            "`services/service_registry.json` — declared systemd units consumed by the services CLI.",
            "`docs/_reports/readme_sweep.json` — machine-readable report emitted by the README sweeper.",
        ],
        surface=[
            "`python run.py web` — start the TLS-enabled Flask interface defined in `interfaces.app`.",
            "`python run.py compose_cam <sheet_slug> [--stl]` — generate toolpaths and exports for a sheet layout.",
            "`python run.py services <command>` — proxy into `services.cli` for systemd operations.",
            "`python run.py tests` — execute curated repo tests via `tools.test_runner`.",
        ],
        invariants=[
            "Always run commands from the repository root so metadata headers resolve correctly.",
            "`memories/index.jsonl` is append-only; never rewrite or reorder entries.",
            "Default execution assumes `OFFLINE=1`; external calls must be whitelisted explicitly.",
            "Source files and READMEs must retain their top-of-file metadata headers for tooling.",
        ],
        extensions=[
            "Add new CLI entrypoints by extending the `ENTRYPOINTS` map in `run.py`.",
            "Register additional skills under `skills/` with metadata headers and update their README.",
            "Wire new web modules by creating an app manifest under `interfaces/apps/` and updating `app_registry`.",
            "Teach the doc sweeper about new modules by adding specs in `tools/docs/sweep_readmes.py`.",
        ],
        ai_reading_order=[
            ("run.py", "Dispatch table for all CLI entrypoints."),
            ("continuum/project_graph.py", "Builds module graph metadata and token stats."),
            ("memories/memory_manager.py", "High-level helpers for ledger access and chat logs."),
            ("interfaces/app_registry.py", "Registers Flask blueprints and UI modules."),
            ("services/cli.py", "Systemd-aware service manager CLI."),
            ("skills/mill_ui/apps/compose_cam.py", "Sheet layout CAM pipeline."),
            ("tools/context_builder.py", "Generates cleaned context snapshots for AI."),
        ],
    ),
    "continuum/README.md": ReadmeSpec(
        path="continuum/README.md",
        title="Continuum Toolkit",
        owner="continuum/",
        what=dedent("""
            Continuum collects graph, context, and metadata utilities that keep the repository AI-legible.
            It powers code snapshots, dependency maps, and metadata regeneration for downstream tools.
        """).strip(),
        when=[
            "Need an up-to-date dependency graph before planning a refactor.",
            "Generate stripped code or metadata blocks for LLM prompts.",
            "Refresh metadata headers after adding new files or moving modules.",
        ],
        how_text="Run the modules directly with `python -m` so outputs land in the working directory.",
        how_commands=[
            "python -m continuum.project_graph --out project_graph.json",
            "python -m continuum.code_context . --mode metadata --output metadata_headers.md",
            "python -m continuum.regen_metadata_headers --root . --dry-run",
        ],
        inputs=[
            "`continuum/file_crawl.py` — canonical file walker shared by project graph and context tools.",
            "`project_graph.json` — optional JSON snapshot of modules, files, and dependencies.",
            "`metadata_headers.md` — metadata-only stream produced by `code_context` in metadata mode.",
            "`continuum/stats.py` — helpers used when printing token budgets.",
        ],
        surface=[
            "`continuum.project_graph.build_project_graph(root_dir='.', model_name='gpt-4.1')` — return graph data and token stats.",
            "`continuum.code_context.generate_code_context(root_dir, mode='code')` — emit stripped code or header blocks.",
            "`continuum.regen_metadata_headers.update_metadata_headers(root='.', file_path=None, dry_run=False)` — rebuild metadata headers.",
            "`continuum.diff_tools.apply_patch(patch)` — utility for applying unified patches in automation flows.",
        ],
        invariants=[
            "Metadata headers follow the `# key: value` format with path/type/tags/owner/depends_on/description.",
            "Exclude lists in `file_crawl` prevent noisy directories; prefer extending them over replacing.",
            "`regen_metadata_headers` never overwrites file bodies; run with `--dry-run` before committing changes.",
            "Token counts assume UTF-8 and the GPT-4.1 tokenizer with a stable cl100k fallback.",
        ],
        extensions=[
            "Add extra module roots by editing `MODULE_DIRS` in `project_graph.py`.",
            "Teach `find_files` about new extensions when asset types expand.",
            "Expose additional summary metrics by extending `stats.py` and the CLI output.",
        ],
        ai_reading_order=[
            ("continuum/project_graph.py", "Builds module graphs and token statistics."),
            ("continuum/code_context.py", "Extracts stripped code and metadata blocks."),
            ("continuum/file_crawl.py", "Shared filesystem traversal and exclusion logic."),
            ("continuum/regen_metadata_headers.py", "Regenerates metadata headers via the LLM client."),
            ("continuum/diff_tools.py", "Patch application helpers used by automation."),
        ],
    ),
    "cortex/README.md": ReadmeSpec(
        path="cortex/README.md",
        title="Cortex Router",
        owner="cortex/",
        what=dedent("""
            Cortex routes chat, embedding, and image calls through a thin provider abstraction.
            It centralises API credentials, persona lookups, and client fallbacks for the rest of the stack.
        """).strip(),
        when=[
            "Request embeddings or chat completions from the configured LLM provider.",
            "Generate persona-styled prompts or images for CAM and documentation flows.",
            "Extend the stack with new model providers or offline routing strategies.",
        ],
        how_text="Provide OpenAI credentials, then exercise the router or run its tests directly.",
        how_commands=[
            "export OPENAI_API_KEY=sk-your-key # replace with a valid token",
            dedent("""
                python - <<'PY'
                from cortex.ai_router import get_router
                router = get_router()
                print(router.embed([\"ping\"])[0][:4])
                print(router.chat([{\"role\": \"user\", \"content\": \"ping\"}]))
                PY
            """).strip(),
            "pytest -q cortex/tests/test_client_api.py",
        ],
        inputs=[
            "`OPENAI_API_KEY` — environment variable consumed by `cortex.client`.",
            "`cortex/personas/` — persona and style metadata used to assemble prompts.",
            "`cortex/client.py` — provider bindings wrapping SDK and HTTP calls.",
            "`memories/` — optional transcripts and artifacts referenced by higher-level callers.",
        ],
        surface=[
            "`cortex.ai_router.get_router(source='openai')` — return the active `AIRouter` implementation.",
            "`AIRouter.embed(inputs, model='text-embedding-3-small')` — fetch embeddings for a list of strings.",
            "`AIRouter.chat(messages, model='gpt-4.1-mini')` — produce a chat completion response.",
            "`cortex.client.get_image_generation(prompt, model='gpt-image-1')` — request base64 PNG payloads.",
        ],
        invariants=[
            "The router currently supports only the `openai` backend; add new identifiers deliberately.",
            "`OPENAI_API_KEY` must be set; helpers raise `RuntimeError` when credentials are missing.",
            "Persona and style metadata stay deterministic; avoid mutating the loaded dictionaries at runtime.",
            "Downstream callers must sanitize user content before invoking the client helpers.",
        ],
        extensions=[
            "Register new providers by extending `get_router` and supplying compatible client functions.",
            "Drop additional persona/style packs under `cortex/personas/` for new verticals.",
            "Wrap `AIRouter` methods with rate limiting or caching if deployments require it.",
        ],
        ai_reading_order=[
            ("cortex/ai_router.py", "Router facade for chat and embeddings."),
            ("cortex/client.py", "OpenAI client bindings and HTTP fallbacks."),
            ("cortex/context_manager.py", "Context assembly helpers for prompts."),
            ("cortex/distill.py", "Document distillation utilities used by living docs."),
            ("cortex/personas/personas_manager.py", "Loads persona and style metadata."),
        ],
    ),
    "interfaces/README.md": ReadmeSpec(
        path="interfaces/README.md",
        title="Interfaces Layer",
        owner="interfaces/",
        what=dedent("""
            Interfaces hosts the Flask surface that stitches chat, tasks, and living-doc UIs together.
            It registers modular blueprints, serves HTMX fragments, and exposes JSON adapters.
        """).strip(),
        when=[
            "Start the operator-facing web UI during development or demos.",
            "Expose JSON APIs that downstream automation can call.",
            "Add a new app module or blueprint to the interface shell.",
        ],
        how_text="Run via `run.py` or the Flask module while pointing at the bundled TLS certificates.",
        how_commands=[
            "python run.py web",
            "FLASK_APP=interfaces.app:create_app flask run --port 8080",
            "python -m interfaces.app",
        ],
        inputs=[
            "`interfaces/apps/<app>/manifest.py` — blueprint registration for each module.",
            "`interfaces/templates/` — shared Jinja layouts and HTMX fragments.",
            "`interfaces/static/` — static assets served by Flask (HTMX, CSS, icons).",
            "`interfaces/cert/` — development TLS certificates referenced by the runner.",
        ],
        surface=[
            "`interfaces.app.create_app()` — build the Flask application with registered blueprints.",
            "`interfaces.app_registry.register_all_apps(app)` — attach module manifests to the shell.",
            "`interfaces/adapters/api/*.py` — JSON API adapters mirrored by the UI.",
            "`interfaces/adapters/web/*.py` — HTMX endpoints returning partial templates.",
        ],
        invariants=[
            "Each app manifest must expose `register(app)` and attach its blueprints idempotently.",
            "TLS defaults to `interfaces/cert`; rotate certificates without changing the path.",
            "Adapters normalize payloads before calling services; keep translation logic minimal.",
            "Template fragments stay small (<100 lines) and rely on HTMX instead of custom JS.",
        ],
        extensions=[
            "Create a new module under `interfaces/apps/<name>/` with a manifest and adapters.",
            "Expose new APIs by adding modules under `interfaces/adapters/api/`.",
            "Share reusable UI fragments by extending `interfaces/templates/_shared/`.",
            "Document additional modules here and include them in the sweeper specification.",
        ],
        ai_reading_order=[
            ("interfaces/app.py", "Flask app factory and TLS runner."),
            ("interfaces/app_registry.py", "Central manifest loader wiring modules."),
            ("interfaces/apps/chat/manifest.py", "Example chat blueprint registration."),
            ("interfaces/adapters/api/chat_api.py", "JSON API surface for chat traffic."),
            ("interfaces/templates/base.html.jinja", "Base layout that loads shared assets."),
        ],
    ),
    "living_docs/README.md": ReadmeSpec(
        path="living_docs/README.md",
        title="Living Docs",
        owner="living_docs/",
        what=dedent("""
            Living Docs orchestrates the Living Truth Partner workflow for LTD documents.
            It manages slugs, artifacts, prompts, and exports for AI-guided writing sessions.
        """).strip(),
        when=[
            "Create or revise LTD documents with guardrails, personas, and action tracking.",
            "Inspect generated prompts, sections, and action items for a specific document.",
            "Export LTD artifacts (PDF, DOCX) for review or handoff.",
        ],
        how_text="Drive the workflow through the `ltp` CLI exposed by `run.py`.",
        how_commands=[
            "python run.py ltp sections test_document",
            "python run.py ltp prompts test_document",
            "python run.py ltp revise test_document --apply",
        ],
        inputs=[
            "`living_docs/docs/<slug>.ltd.md` — ground-truth LTD source documents.",
            "`living_docs/artifacts/<slug>/` — summaries, prompts, history, and exports per document.",
            "`living_docs/templates/` — Pandoc templates for PDF/DOCX outputs.",
            "`skills/living_truth_partner/config.py` — config wiring storage locations for the CLI.",
        ],
        surface=[
            "`python run.py ltp new <title>` — create a document slug and scaffold storage.",
            "`python run.py ltp sections <slug>` — list sections with word counts and guardrails.",
            "`python run.py ltp revise <slug> --apply` — apply AI-guided revision patches.",
            "`python run.py ltp persona <slug> --name ...` — append persona context to a document.",
        ],
        invariants=[
            "Slugs are normalized to lowercase kebab-case; the CLI enforces naming.",
            "Artifacts live under `living_docs/artifacts/<slug>` and should be committed for audit trails.",
            "Audio ingestion (voice capture) requires explicit file paths; recording is optional.",
            "Exports must remain reproducible offline; avoid network lookups in exporters.",
        ],
        extensions=[
            "Add export formats by extending `skills.living_truth_partner.export_doc`.",
            "Introduce additional guardrails in `skills.living_truth_partner.guardrails`.",
            "Seed new templates under `living_docs/templates/` and reference them in exporters.",
            "Document new CLI verbs here and teach the sweeper how to validate them.",
        ],
        ai_reading_order=[
            ("skills/living_truth_partner/cli.py", "CLI verbs and argparse surface for the workflow."),
            ("skills/living_truth_partner/project_store.py", "Slug normalization and storage layout."),
            ("living_docs/docs/test_document.ltd.md", "Sample LTD source structure."),
            ("living_docs/artifacts/test_document/context_summary.json", "Distilled context payload for the sample."),
            ("living_docs/templates/pdf/default.latex", "Pandoc template used for PDF exports."),
        ],
    ),
    "memories/README.md": ReadmeSpec(
        path="memories/README.md",
        title="Memories Ledger",
        owner="memories/",
        what=dedent("""
            Memories is the canonical ledger for every action, policy, and artifact.
            It stores typed memories under an append-only chain referenced by the rest of the stack.
        """).strip(),
        when=[
            "Append new actions, policies, artifacts, or decisions produced by skills.",
            "Audit ledger integrity or decision coverage during CI.",
            "Query historical context for chat, CAM, or documentation workflows.",
        ],
        how_text="Use the provided CI helpers to validate ledger integrity before shipping.",
        how_commands=[
            "python scripts/ci_registry_integrity.py",
            "python scripts/ci_decision_coverage.py",
            "python scripts/ci_reproduce_sample.py",
        ],
        inputs=[
            "`memories/index.jsonl` — hash-chained ledger of Memory envelopes.",
            "`memories/actions/` — executor manifests with captured environments.",
            "`memories/artifacts/` — generated assets such as G-code, patches, and exports.",
            "`memories/policies/` — JSON guardrails loaded by policy evaluators.",
            "`memories/living_truths/` — historical guidance documents kept for reference.",
        ],
        surface=[
            "`memories.framework.registry.MemoryRegistry` — append or query typed memories with integrity checks.",
            "`memories.memory_manager.get_known_contexts()` — enumerate available memory domains.",
            "`memories.memory_manager.add_to_domain(domain, text, source)` — append narrative or note entries.",
            "`memories.memory_graph.scan_memory()` — build a JSON summary of memory domains.",
        ],
        invariants=[
            "Ledger entries must be canonical JSON with stable key ordering.",
            "Registry status transitions follow staged → registered → referenced → archived.",
            "Artifact hashes recorded in manifests must match on-disk contents.",
            "All workflows run with `OFFLINE=1`; remote fetches are disallowed by default.",
        ],
        extensions=[
            "Create new domains by adding folders under `memories/` and documenting them here.",
            "Add policy schemas under `memories/policies/` and wire them into guardrails.",
            "Extend the registry by implementing companion models in `memories/framework/models.py`.",
            "Record additional CI checks under `scripts/` and reference them in this README.",
        ],
        ai_reading_order=[
            ("memories/framework/registry.py", "Implements MemoryRegistry and chain logic."),
            ("memories/memory_manager.py", "Helpers for chat logs and domain access."),
            ("memories/memory_graph.py", "Generates memory domain summaries."),
            ("memories/index.jsonl", "Append-only ledger file (inspect tail entries)."),
            ("scripts/ci_registry_integrity.py", "Validates ledger integrity in CI."),
        ],
    ),
    "services/README.md": ReadmeSpec(
        path="services/README.md",
        title="Services CLI",
        owner="services/",
        what=dedent("""
            Services manages systemd integration for the cliff stack, bundling unit files and a CLI to control them.
            It centralises how background daemons are installed, started, and inspected.
        """).strip(),
        when=[
            "List or control cliff services on a development or production host.",
            "Install or update systemd unit files after changing service configurations.",
            "Add new long-running processes to the deployment footprint.",
        ],
        how_text="Call the `services` CLI through `run.py` (or invoke the module directly) with explicit scopes.",
        how_commands=[
            "python run.py services list",
            "python run.py services install web --scope system",
            "python run.py services restart web",
            "sudo ./services/install_system_service.sh web",
        ],
        inputs=[
            "`services/service_registry.json` — declared services, unit filenames, and scopes.",
            "`services/*.service` — templated systemd unit files synced by the CLI.",
            "`services/cli_archiver/` — helper code referenced by service units.",
            "`interfaces/cert/` — TLS assets consumed by the web service unit.",
        ],
        surface=[
            "`services.cli.api(argv=None)` — command dispatcher returning systemd exit codes.",
            "`services.registry.load(path=None)` — load and validate the service registry JSON.",
            "`services.cli._install(service, scope)` — copy unit files and reload systemd daemons.",
            "`services.install_system_service.sh` — shell helper for manual installs.",
        ],
        invariants=[
            "Registry IDs must stay unique and match the `ServiceRegistry` lookup keys.",
            "Unit files live under `services/` and are copied verbatim; keep them deterministic.",
            "System-level installs require root privileges; respect the `scope` declared in the registry.",
            "CLI commands forward exit codes from `systemctl`; do not swallow failures.",
        ],
        extensions=[
            "Add new services by dropping a unit file and extending `service_registry.json`.",
            "Augment helper code under `services/cli_archiver` when the CLI needs new behaviour.",
            "Document new operations here and update the sweeper specification.",
            "Wire monitoring or health checks by adding custom `systemctl` subcommands to the CLI.",
        ],
        ai_reading_order=[
            ("services/cli.py", "CLI implementation over systemctl."),
            ("services/registry.py", "Registry dataclasses and loader."),
            ("services/service_registry.json", "Declared service inventory."),
            ("services/install_system_service.sh", "Convenience wrapper for installing units."),
            ("services/cliff-web-server.service", "Example unit wiring for the Flask app."),
        ],
    ),
    "skills/README.md": ReadmeSpec(
        path="skills/README.md",
        title="Skills Library",
        owner="skills/",
        what=dedent("""
            Skills houses domain-specific automation modules spanning CAM, image generation, and living documents.
            It standardises entrypoints and metadata for capabilities beyond the core platform.
        """).strip(),
        when=[
            "Invoke specialised pipelines such as CAM planning or persona-driven image generation.",
            "Wire new skills into CLI entrypoints or background services.",
            "Share reusable domain code across interfaces, memories, and services.",
        ],
        how_text="Run packaged CLIs through `run.py` or import the skill APIs directly.",
        how_commands=[
            "python run.py compose_cam demo_vine_border --stl",
            "python -m skills.image_pipeline.generate_image demo_vine_border",
            "python run.py ltp sections test_document",
            "python run.py mill_ui_tests",
        ],
        inputs=[
            "`skills/mill_ui/` — primary CAD/CAM modules, planners, and native bindings.",
            "`skills/image_pipeline/` — persona and style aware image generation pipeline.",
            "`skills/living_truth_partner/` — living-doc orchestration for LTD workflows.",
            "`memories/cam_projects/` — project inputs consumed by CAM skills.",
            "`cortex/personas/` — shared persona/style metadata consumed across skills.",
        ],
        surface=[
            "`skills.mill_ui.apps.compose_cam` — CLI entrypoint for sheet CAM generation.",
            "`skills.mill_ui.api` — Python API facade for CAM, CAD, and IO modules.",
            "`skills.image_pipeline.generate_image.generate_dalle_image(project)` — persona image generator.",
            "`skills.living_truth_partner.cli.api(argv)` — manage living-doc workflows.",
        ],
        invariants=[
            "Each skill module exposes a single public API symbol and metadata header.",
            "CAM operations assume millimetres and safe-Z defaults defined in `compose_cam`.",
            "Image pipeline requires valid personas/styles; keep configs in sync with cortex metadata.",
            "Skills should remain pure where possible; external side effects land under `memories/`.",
        ],
        extensions=[
            "Add new CAM strategies under `skills/mill_ui/cam/ops` and expose them via `api.cam`.",
            "Drop new persona/style packs under `skills/image_pipeline/` and extend loaders accordingly.",
            "Compose additional CLIs by exposing `api()` functions and wiring `run.py` to them.",
            "Document new skills here and add their specs to the sweeper configuration.",
        ],
        ai_reading_order=[
            ("skills/mill_ui/apps/compose_cam.py", "CLI orchestrator for sheet layout CAM."),
            ("skills/mill_ui/api/cam.py", "Public CAM API surface."),
            ("skills/image_pipeline/generate_image.py", "Persona-aware image generator."),
            ("skills/living_truth_partner/cli.py", "Living Truth Partner command routing."),
            ("skills/cam_engine/cli.py", "Alternate CAM engine CLI wrapper."),
        ],
    ),
    "skills/mill_ui/README.md": ReadmeSpec(
        path="skills/mill_ui/README.md",
        title="Mill UI Skill",
        owner="skills/mill_ui/",
        what=dedent("""
            Mill UI is the manufacturing nucleus for sheet-based CAD/CAM planning.
            It orchestrates templates, planners, and native accelerators to produce toolpaths and exports.
        """).strip(),
        when=[
            "Generate toolpaths or exports for panelised sheet layouts.",
            "Prototype new CAM operations or composition templates.",
            "Run regression tests for the milling stack before shipping changes.",
        ],
        how_text="Use the compose_cam CLI for end-to-end jobs or invoke APIs during testing.",
        how_commands=[
            "python run.py compose_cam demo_vine_border --stl",
            "python run.py mill_ui_tests",
            "python -m tools.context_builder skills.mill_ui --output skills/mill_ui/code_context.txt",
        ],
        inputs=[
            "`memories/cam_projects/sheet_layouts/<slug>/sheet.json` — sheet layout definitions consumed by compose_cam.",
            "`skills/mill_ui/cam/tools/tool_db.json` — tool library looked up by planners.",
            "`skills/mill_ui/compositions/` — template registries that expand layout items.",
            "`skills/mill_ui/cad/native/` — native CAD exporter for STL/STEP outputs.",
            "`skills/mill_ui/cam/native/` — native CAM backend for pocket/profile planners.",
        ],
        surface=[
            "`skills.mill_ui.apps.compose_cam.main()` — CLI entrypoint for sheet layouts.",
            "`skills.mill_ui.api.cam.write_gcode(moves, ...)` — emit G-code via the native backend.",
            "`skills.mill_ui.api.cad.render_svg_with_dims(panel, path)` — generate dimensional SVG previews.",
            "`skills.mill_ui.cam.planner.passes.plan_passes(project)` — orchestrate planner pipeline stages.",
            "`skills.mill_ui.api.io.save_json(path, obj)` — persist canonical project artifacts.",
        ],
        invariants=[
            "All linear dimensions are in millimetres; default safe-Z is 6.0 mm.",
            "Tool database entries must include required tool IDs; compose_cam fails fast otherwise.",
            "Native backends must import successfully; fallback stubs raise `RuntimeError`.",
            "Layouts honour clearance/kerf conventions declared in composition templates.",
        ],
        extensions=[
            "Add templates under `skills/mill_ui/compositions/` and import them in `apps.compose_cam`.",
            "Register new CAM operations under `skills/mill_ui/cam/ops/` and expose them via `api.cam`.",
            "Extend native bindings by adding pybind11 code under `skills/mill_ui/cam/native/cpp/`.",
            "Document new planners or exporters here and in the sweeper specification.",
        ],
        ai_reading_order=[
            ("skills/mill_ui/apps/compose_cam.py", "CLI orchestrator for sheet jobs."),
            ("skills/mill_ui/api/cam.py", "Public CAM API surface and registrations."),
            ("skills/mill_ui/cam/planner/passes.py", "High-level pass planning logic."),
            ("skills/mill_ui/cam/native/core.py", "Python shims for the native planner."),
            ("skills/mill_ui/cad/export/svg_dims.py", "Dimensional drawing exporter."),
        ],
    ),
    "skills/mill_ui/cam/native/README.md": ReadmeSpec(
        path="skills/mill_ui/cam/native/README.md",
        title="Native CAM Core",
        owner="skills/mill_ui/cam/native/",
        what=dedent("""
            The native CAM core provides the C++17 planners compiled via pybind11 for heavy operations.
            Python shims map project data structures into the compiled engine for deterministic toolpaths.
        """).strip(),
        when=[
            "Produce performant pocket, profile, drilling, or bore toolpaths.",
            "Validate native builds on a new platform or toolchain.",
            "Extend the CAM kernel with additional geometry primitives or optimisations.",
        ],
        how_text="Build through the project install; use explicit CMake invocations when debugging.",
        how_commands=[
            "python -m pip install --upgrade pip",
            "pip install .",
            "cmake -S skills/mill_ui/cam/native/cpp -B build/native_cam && cmake --build build/native_cam",
        ],
        inputs=[
            "`skills/mill_ui/cam/native/cpp/` — CMake project for the native CAM engine.",
            "`skills/mill_ui/cam/native/core.py` — Python shims gating native access.",
            "`skills/mill_ui/cam/model/` — dataclasses converted before hitting the native bindings.",
            "`skills/mill_ui/cam/ops/` — callers that delegate heavy work to the native layer.",
            "`pyproject.toml` — scikit-build-core configuration that builds the extension during install.",
        ],
        surface=[
            "`skills.mill_ui.cam.native.core.is_native_available()` — detect whether the extension loaded.",
            "`skills.mill_ui.cam.native.core.pocket_raster(...)` — plan raster pockets via the native engine.",
            "`skills.mill_ui.cam.native.core.profile_outline(...)` — generate profile passes.",
            "`skills.mill_ui.cam.native.core.post_gcode(moves, ...)` — emit G-code strings natively.",
            "`skills.mill_ui.cam.native.core.fit_arcs(paths, tol_mm)` — smooth moves with arc fitting.",
        ],
        invariants=[
            "Requires a modern C++17 compiler and pybind11 headers.",
            "Native API raises `RuntimeError` when accessed before a successful build; callers must guard with `is_native_available()`.",
            "All geometry uses millimetres and matches the winding expected by composition templates.",
            "Bindings remain deterministic; avoid introducing randomised behaviour inside C++ code.",
        ],
        extensions=[
            "Add planners by implementing pybind11 bindings under `cpp/bindings` and exposing them in `core.py`.",
            "Vendor extra geometry helpers under `cpp/geom2d` and wire them into Python wrappers.",
            "Surface additional configuration by extending dataclasses in `skills.mill_ui.cam.model`.",
        ],
        ai_reading_order=[
            ("skills/mill_ui/cam/native/core.py", "Python facade around the native engine."),
            ("skills/mill_ui/cam/native/cpp/src/facade.cpp", "C++ entry point that bridges planners."),
            ("skills/mill_ui/cam/native/cpp/algo/plan_2d.cpp", "Core pocket/profile planning logic."),
            ("skills/mill_ui/cam/native/cpp/algo/post_gcode.cpp", "Native G-code emitter implementation."),
            ("skills/mill_ui/cam/native/cpp/CMakeLists.txt", "Build configuration for the CAM extension."),
        ],
    ),
    "skills/mill_ui/cad/native/README.md": ReadmeSpec(
        path="skills/mill_ui/cad/native/README.md",
        title="Native CAD Exporter",
        owner="skills/mill_ui/cad/native/",
        what=dedent("""
            The native CAD exporter provides C++ helpers that summarise sheet geometry and emit STEP/STL data.
            Python shims wrap the compiled module so compose_cam can produce previews without extra dependencies.
        """).strip(),
        when=[
            "Export lightweight geometry summaries for downstream CAD tools.",
            "Generate STEP or STL previews directly from sheet templates.",
            "Extend CAD coverage with OCCT-backed operations or richer tessellation.",
        ],
        how_text="Build via the project install; use explicit CMake builds when diagnosing toolchain issues.",
        how_commands=[
            "python -m pip install --upgrade pip",
            "pip install .",
            "cmake -S skills/mill_ui/cad/native/cpp -B build/native_cad && cmake --build build/native_cad",
        ],
        inputs=[
            "`skills/mill_ui/cad/native/cpp/` — CMake project for the CAD exporter.",
            "`skills/mill_ui/cad/native/core.py` — Python dataclasses and wrapper API.",
            "`skills/mill_ui/api/cad.py` — Public CAD API that relies on the native exporter.",
            "`memories/cam_projects/` — panel definitions used when exporting geometry.",
            "`pyproject.toml` — scikit-build-core configuration used during installation.",
        ],
        surface=[
            "`skills.mill_ui.cad.native.core.is_native_available()` — detect whether the CAD extension loaded.",
            "`skills.mill_ui.cad.native.core.build_model(sheet, shapes)` — summarise sheet, parts, and pockets.",
            "`skills.mill_ui.cad.native.core.export_stl(sheet, shapes, output_path)` — write STL meshes.",
            "`skills.mill_ui.cad.native.core.export_step(sheet, shapes, output_path)` — emit STEP manifests.",
            "`skills.mill_ui.cad.native.core.Model` — dataclass capturing sheet, parts, and pockets.",
        ],
        invariants=[
            "Requires C++17 plus pybind11; exporters raise `RuntimeError` when missing.",
            "All lengths are millimetres so CAD and CAM outputs stay aligned.",
            "Native exporter writes files under the requested output directory only.",
            "Model summaries remain deterministic; maintain stable dataclass field ordering.",
        ],
        extensions=[
            "Add exporters by binding new C++ functions under `cpp/bindings` and exposing them in `core.py`.",
            "Augment geometry shims by extending dataclasses or helper conversions.",
            "Integrate OCCT features by linking against system libraries in the CMake project.",
        ],
        ai_reading_order=[
            ("skills/mill_ui/cad/native/core.py", "Python shims over the native exporter."),
            ("skills/mill_ui/cad/native/cpp/bindings/cad_native_pybind.cpp", "pybind11 binding layer."),
            ("skills/mill_ui/cad/native/cpp/CMakeLists.txt", "Build configuration for the CAD extension."),
            ("skills/mill_ui/cad/export/step.py", "High-level STEP/STL helpers hitting the native core."),
            ("skills/mill_ui/api/cad.py", "Public API exposing CAD exporters to callers."),
        ],
    ),
    "tools/README.md": ReadmeSpec(
        path="tools/README.md",
        title="Tooling Utilities",
        owner="tools/",
        what=dedent("""
            The tools package bundles repo-level utilities such as context builders, test runners, and the README sweeper.
            These scripts keep the project AI-ready and enforce documentation hygiene.
        """).strip(),
        when=[
            "Generate trimmed code context for prompts or offline analysis.",
            "Run the project-defined test harness across modules.",
            "Sweep and validate READMEs before committing documentation changes.",
        ],
        how_text="Invoke the utilities with `python -m` from the repository root.",
        how_commands=[
            "python -m tools.context_builder continuum --output continuum/code_context.txt",
            "python run.py tests",
            "python tools/docs/sweep_readmes.py --dry-run",
        ],
        inputs=[
            "`tools/context_builder.py` — generates deduplicated code snapshots.",
            "`tools/test_runner.py` — curated pytest runner for the repository.",
            "`tools/docs/sweep_readmes.py` — README sweeper and validator.",
            "`docs/AI_README_GUIDE.md` — canonical README guidance consumed by the sweeper.",
            "`docs/_reports/` — output folder for sweeper JSON reports.",
        ],
        surface=[
            "`tools.context_builder.build_context(target, output=None)` — produce code context archives.",
            "`tools.context_builder.main(argv=None)` — CLI entry for the context builder.",
            "`tools.test_runner.main()` — run the curated pytest selection.",
            "`tools.docs.sweep_readmes.main(argv=None)` — sweep and validate READMEs.",
        ],
        invariants=[
            "Context builder strips docstrings/comments but preserves metadata headers.",
            "Test runner expects the repo root on `sys.path`; run from the repository root.",
            "Sweeper must not mutate files unless `--apply` is passed.",
            "All tools operate offline; avoid adding network dependencies.",
        ],
        extensions=[
            "Add new CLI utilities under `tools/` and expose them via `run.py` if needed.",
            "Expand sweeper specs by editing `tools/docs/sweep_readmes.py`.",
            "Capture additional machine-readable reports under `docs/_reports/`.",
            "Document any new tooling here so the sweeper can keep it in sync.",
        ],
        ai_reading_order=[
            ("tools/context_builder.py", "Context snapshot generator."),
            ("tools/test_runner.py", "Pytest harness wrapper."),
            ("tools/docs/sweep_readmes.py", "README sweeper and validator."),
            ("docs/AI_README_GUIDE.md", "Canonical README structure and rules."),
            ("run.py", "Dispatcher integrating the tooling entrypoints."),
        ],
    ),
}

ARCHIVE_PLAN: Dict[str, str] = {
    "memories/README_memories.md": "Merged into memories/README.md per AI_README_GUIDE.md",
    "memories/living_truths/python.guidance.md": "Superseded by AI_README_GUIDE.md",
    "memories/living_truths/modular.app.framework.design.md": "Superseded by AI_README_GUIDE.md",
    "memories/living_truths/app.stack.guidance.md": "Superseded by AI_README_GUIDE.md",
}

GUIDE_CONTENT = dedent("""
# AI README Guidance

## Purpose
Design every README as an onboarding surface for humans and LLMs. Each document must describe the real
entrypoints, APIs, guardrails, and extension seams so the repository stays self-narrating.

## Canonical Structure
1. **What this is** *(1–2 sentences)* – concise purpose plus the primary entrypoints.
2. **When to use it** *(3–5 bullets)* – concrete scenarios or jobs-to-be-done.
3. **How to run** – short paragraph followed by an executable `bash` block with working commands.
4. **Inputs & outputs (for AI & humans)** – list canonical files, schemas, and generated artifacts.
5. **Public surface** – enumerate CLI flags, APIs, or classes with terse descriptions.
6. **Invariants & guardrails** – constraints, safety rails, units, or policies that cannot be broken.
7. **Extension points** – where to plug in new behaviour, configs, or modules.
8. **AI reading order** – 5–8 follow-up files (code or docs) with one-line descriptions; root README must
   spotlight the project’s anchor files.

Keep headings verbatim so automation can parse them. Additional sections may follow section 8 when absolutely
necessary, but only after the required structure.

## Owner & Metadata
- Every README starts with an H1 title followed immediately by `Owner path: <relative path>`.
- The owner path points at the canonical folder or module documented by the file.
- Optional HTML comment `<!-- ai-readme: allow-long -->` may appear after the owner line to extend length limits.

## Length & Formatting
- Target **300–800 words** per README. The sweeper enforces an 800-word cap unless the long-read override comment
  is present.
- Prefer bullet lists over long prose. Keep command blocks minimal and runnable as written.
- Use backticks for file names, commands, and literal sections.

## AI Reading Order
- The root README lists **5–8 anchor files** that give an AI the fastest ramp (entrypoints, planners, configs,
  representative tests).
- Module READMEs should link the most relevant code or docs (typically 4–6 items).
- Order anchors by importance so agents can short-circuit once they have enough context.

## Validation Rules
The sweeper (`python tools/docs/sweep_readmes.py`) enforces the following:
- Sections 1–5 must exist with non-empty content; sections 6–8 must be present unless genuinely N/A.
- Owner line must match the declared path and appear immediately after the H1 heading.
- Command examples must map to real scripts/flags and provide required positional arguments.
- README length ≤800 words unless `<!-- ai-readme: allow-long -->` is present.
- Duplicate `What this is` copy across READMEs is forbidden (two-line shared tagline is the maximum overlap).
- README updates must ship in the same PR that changes a CLI flag or public API surface.
- JSON report is written to `docs/_reports/readme_sweep.json` when `--apply` is used.

## Maintenance Workflow
1. Update code or CLI behaviour.
2. Regenerate affected README(s) manually or run the sweeper with `--apply`.
3. Review the diff, ensure commands stay correct, and commit together with the code change.
4. Run `python tools/docs/sweep_readmes.py --check` before merging; CI mirrors this step.

## Example Skeleton
```
# Module Name
Owner path: path/to/module

## 1. What this is
One-liner purpose.

## 2. When to use it
- Scenario A
- Scenario B

## 3. How to run
Install dependencies, then:
```bash
python -m package.cli --flag value
```

...
```
""").strip() + "\n"


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def normalise_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _owner_line(spec: ReadmeSpec) -> str:
    return f"Owner path: {spec.owner}"


def _render_section(title: str, body: str) -> str:
    body = body.strip()
    return f"## {title}\n\n{body}\n"


def _render_bullets(items: Sequence[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


def _render_code_block(lines: Sequence[str]) -> str:
    if not lines:
        return ""
    joined = "\n".join(lines)
    return f"```bash\n{joined}\n```"


def render_readme(spec: ReadmeSpec) -> str:
    sections: List[str] = []
    sections.append(f"# {spec.title}\n")
    sections.append(_owner_line(spec) + "\n")
    sections.append(_render_section("1. What this is", spec.what))

    when_block = _render_bullets(spec.when)
    sections.append(_render_section("2. When to use it", when_block))

    how_parts: List[str] = []
    if spec.how_text.strip():
        how_parts.append(spec.how_text.strip())
    if spec.how_commands:
        how_parts.append(_render_code_block(spec.how_commands))
    sections.append(_render_section("3. How to run", "\n\n".join(part for part in how_parts if part)))

    sections.append(_render_section("4. Inputs & outputs (for AI & humans)", _render_bullets(spec.inputs)))
    sections.append(_render_section("5. Public surface", _render_bullets(spec.surface)))

    invariants = _render_bullets(spec.invariants) if spec.invariants else ""
    sections.append(_render_section("6. Invariants & guardrails", invariants))

    extensions = _render_bullets(spec.extensions) if spec.extensions else ""
    sections.append(_render_section("7. Extension points", extensions))

    reading_lines = [f"`{path}` — {desc}" for path, desc in spec.ai_reading_order]
    sections.append(_render_section("8. AI reading order", _render_bullets(reading_lines)))

    for extra in spec.extras:
        sections.append(extra.strip() + "\n")

    rendered = "\n".join(sections)
    rendered = normalise_newlines(rendered)
    rendered = re.sub(r"\n{3,}", "\n\n", rendered)
    return rendered.strip() + "\n"


def parse_sections(text: str) -> Dict[str, str]:
    pattern = re.compile(r"^##\s*(\d+\.\s*[^\n]+)\n", re.MULTILINE)
    matches = list(pattern.finditer(text))
    sections: Dict[str, str] = {}
    for idx, match in enumerate(matches):
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        heading = match.group(1).strip()
        body = text[start:end].strip()
        sections[heading] = body
    return sections


def _word_count(text: str) -> int:
    words = re.findall(r"\b\w+\b", text)
    return len(words)


def validate_readme_text(text: str, spec: ReadmeSpec) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    owner_line = _owner_line(spec)
    first_line = next((line.strip() for line in text.splitlines() if line.strip() and not line.startswith("#")), "")
    if first_line != owner_line:
        issues.append(ValidationIssue(Path(spec.path), f"owner line mismatch (expected '{owner_line}')"))

    sections = parse_sections(text)
    required_headings = [
        "1. What this is",
        "2. When to use it",
        "3. How to run",
        "4. Inputs & outputs (for AI & humans)",
        "5. Public surface",
    ]
    for heading in required_headings:
        if heading not in sections or not sections[heading].strip():
            issues.append(ValidationIssue(Path(spec.path), f"missing or empty section '{heading}'"))

    ai_heading = "8. AI reading order"
    if ai_heading in sections:
        lines = [line for line in sections[ai_heading].splitlines() if line.strip()]
        if len(lines) != len(spec.ai_reading_order):
            issues.append(ValidationIssue(Path(spec.path), "AI reading order count mismatch"))
    else:
        issues.append(ValidationIssue(Path(spec.path), "missing AI reading order section"))

    text_body = text
    count = _word_count(text_body)
    limit = 800
    allow_long = spec.allow_long or "<!-- ai-readme: allow-long -->" in text
    if count > limit and not allow_long:
        issues.append(ValidationIssue(Path(spec.path), f"word count {count} exceeds limit {limit}"))

    return issues


def archive_document(src: Path, dst: Path, reason: str) -> None:
    ensure_directory(dst.parent)
    today = _dt.date.today().isoformat()
    original = src.read_text(encoding="utf-8")
    header = dedent(
        f"""---\narchived: true\nreason: \"{reason}\"\ndate: {today}\n---\n\n"""
    )
    dst.write_text(header + original, encoding="utf-8")
    src.unlink()


def make_report(issues: Sequence[ValidationIssue], generated: Sequence[str], archived: Sequence[str]) -> Dict[str, object]:
    return {
        "generated": list(generated),
        "archived": list(archived),
        "issues": [
            {
                "path": str(item.path),
                "reason": item.reason,
            }
            for item in issues
        ],
    }


class ReadmeSweeper:
    def __init__(self, root: Path, specs: Dict[str, ReadmeSpec], archive_plan: Dict[str, str], guide_content: str) -> None:
        self.root = root
        self.specs = specs
        self.archive_plan = archive_plan
        self.guide_content = guide_content
        self.report_path = self.root / "docs/_reports/readme_sweep.json"

    def _abs(self, relative: str) -> Path:
        return self.root / relative

    def render_all(self) -> Dict[str, str]:
        return {path: render_readme(spec) for path, spec in self.specs.items()}

    def validate_all(self) -> List[ValidationIssue]:
        issues: List[ValidationIssue] = []
        for rel, spec in self.specs.items():
            target = self._abs(rel)
            if not target.exists():
                issues.append(ValidationIssue(target, "missing README"))
                continue
            text = target.read_text(encoding="utf-8")
            issues.extend(validate_readme_text(text, spec))
        return issues

    def apply(self) -> Tuple[List[ValidationIssue], List[str], List[str]]:
        generated: List[str] = []
        archived: List[str] = []
        rendered = self.render_all()
        for rel, content in rendered.items():
            target = self._abs(rel)
            ensure_directory(target.parent)
            current = target.read_text(encoding="utf-8") if target.exists() else ""
            if current != content:
                target.write_text(content, encoding="utf-8")
                generated.append(rel)
        guide_target = self._abs("docs/AI_README_GUIDE.md")
        ensure_directory(guide_target.parent)
        if guide_target.read_text(encoding="utf-8") if guide_target.exists() else "" != self.guide_content:
            guide_target.write_text(self.guide_content, encoding="utf-8")
            generated.append("docs/AI_README_GUIDE.md")
        for rel, reason in self.archive_plan.items():
            src = self._abs(rel)
            if src.exists():
                dst = self._abs("docs/_archive") / rel
                archive_document(src, dst, reason)
                archived.append(rel)
        issues = self.validate_all()
        ensure_directory(self.report_path.parent)
        report = make_report(issues, generated, archived)
        self.report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        return issues, generated, archived

    def dry_run(self) -> Tuple[List[ValidationIssue], List[str], List[str]]:
        issues = self.validate_all()
        return issues, [], []

    def write_report(self, issues: Sequence[ValidationIssue], generated: Sequence[str], archived: Sequence[str], apply: bool) -> None:
        report = make_report(issues, generated, archived)
        if apply:
            ensure_directory(self.report_path.parent)
            self.report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        if generated:
            print("[WRITE] " + ", ".join(generated))
        if archived:
            print("[ARCHIVE] " + ", ".join(archived))
        if issues:
            for issue in issues:
                print(f"[ISSUE] {issue.path}: {issue.reason}")
        else:
            print("[OK] All READMEs comply with the guide.")
        if apply:
            print(f"[REPORT] Wrote {self.report_path}")
        else:
            print("[INFO] Dry run; report not written.")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sweep and normalise repository READMEs.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true", help="Rewrite READMEs, archive stale docs, emit report")
    mode.add_argument("--check", action="store_true", help="Exit 1 if any README violates the guide")
    mode.add_argument("--dry-run", action="store_true", help="Report issues without writing changes (default).")
    parser.add_argument("--root", default=str(repo_root()), help="Repository root (default: autodetect)")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    root = Path(args.root).resolve()
    sweeper = ReadmeSweeper(root, README_SPECS, ARCHIVE_PLAN, GUIDE_CONTENT)
    if args.apply:
        issues, generated, archived = sweeper.apply()
        sweeper.write_report(issues, generated, archived, apply=True)
        return 1 if issues else 0
    issues, _, _ = sweeper.dry_run()
    sweeper.write_report(issues, [], [], apply=False)
    if args.check:
        return 1 if issues else 0
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
