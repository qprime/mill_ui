# Interfaces Layer

Owner path: interfaces/

## 1. What this is

Interfaces hosts the Flask surface that stitches chat, tasks, and living-doc UIs together.
It registers modular blueprints, serves HTMX fragments, and exposes JSON adapters.

## 2. When to use it

- Start the operator-facing web UI during development or demos.
- Expose JSON APIs that downstream automation can call.
- Add a new app module or blueprint to the interface shell.

## 3. How to run

Run via `run.py` or the Flask module while pointing at the bundled TLS certificates.

```bash
python run.py web
FLASK_APP=interfaces.app:create_app flask run --port 8080
python -m interfaces.app
```

## 4. Inputs & outputs (for AI & humans)

- `interfaces/apps/<app>/manifest.py` — blueprint registration for each module.
- `interfaces/templates/` — shared Jinja layouts and HTMX fragments.
- `interfaces/static/` — static assets served by Flask (HTMX, CSS, icons).
- `interfaces/cert/` — development TLS certificates referenced by the runner.

## 5. Public surface

- `interfaces.app.create_app()` — build the Flask application with registered blueprints.
- `interfaces.app_registry.register_all_apps(app)` — attach module manifests to the shell.
- `interfaces/adapters/api/*.py` — JSON API adapters mirrored by the UI (includes AceControl v1).
- `interfaces/adapters/web/*.py` — HTMX endpoints returning partial templates.

## 6. Invariants & guardrails

- Each app manifest must expose `register(app)` and attach its blueprints idempotently.
- TLS defaults to `interfaces/cert`; rotate certificates without changing the path.
- Adapters normalize payloads before calling services; keep translation logic minimal.
- Template fragments stay small (<100 lines) and rely on HTMX instead of custom JS.

## 7. Extension points

- Create a new module under `interfaces/apps/<name>/` with a manifest and adapters.
- Expose new APIs by adding modules under `interfaces/adapters/api/`.
- Share reusable UI fragments by extending `interfaces/templates/_shared/`.
- Document additional modules here and include them in the sweeper specification.

## 8. AI reading order

- `interfaces/app.py` — Flask app factory and TLS runner.
- `interfaces/app_registry.py` — Central manifest loader wiring modules.
- `interfaces/apps/ace/manifest.py` — Registers the AceControl API + UI blueprints.
- `interfaces/apps/ace/routes.py` — Serves the `/ace/` mobile-first interface.
- `interfaces/templates/ace/index.html` — AceControl layout with compose/run/history views.
- `interfaces/static/ace.js` — Client orchestration (voice capture, live polling, artifacts).
- `interfaces/adapters/api/ace_api.py` — AceControl v1 runs, plan, machine, and operate endpoints.
- `interfaces/apps/chat/manifest.py` — Example chat blueprint registration.
- `interfaces/adapters/api/chat_api.py` — JSON API surface for chat traffic.
- `interfaces/templates/base.html.jinja` — Base layout that loads shared assets.
