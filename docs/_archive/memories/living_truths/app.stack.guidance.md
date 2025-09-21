---
archived: true
reason: "Superseded by AI_README_GUIDE.md"
date: 2025-09-21
---

# path: docs/app.stack.guidance.md
# desc: Stack rules for Flask + HTMX + Shoelace UI
# api: app_stack_guidance
# tags: stack,flask,htmx,ui

# GLOBAL PRINCIPLES
# - One file, one job; one public symbol.
# - Small functions; flat control flow; early returns.
# - Intent lives in the header + names; no comments beyond headers.
# - Deterministic outputs; explicit config.
# - Uniform layout: imports → types → constants → helpers → api.
# - Module manifests describe capabilities, dependencies, and entry points.

---

## BACKEND

### Framework
- **Flask** for all backend routing and REST APIs.
- Use blueprints: one blueprint per domain, located in `interfaces/<domain>/api.py`.
- REST endpoints return JSON only; no templates in API routes.
- JSON response shape:
  ```json
  { "ok": true, "data": ..., "error": null }
  ```
- Prefer Pydantic (optional) for request/response schema validation.

### API Structure
- `/api/<domain>/<resource>` for REST.
- `/app/<module>/<page>` for server-rendered UI pages.
- Keep logic separate from routing; views call pure helpers.

---

## UI

### Mode
- **Server-driven HTML** using Jinja2 templates + HTMX.
- No Node, no JS bundling. All UI logic is in Python and small HTML fragments.
- Templates live in `/interfaces/<module>/templates/`.
- Base shell: `base.html.jinja` with `<head>` imports for HTMX, Hyperscript, and Shoelace (CDN).
- Dark mode by default using CSS variables.

### Fragments
- Each UI fragment ≤ ~100 lines; one responsibility (list, row, form).
- Routes returning fragments named `render_<thing>()` and kept in a single public function per file.
- Use HTMX attributes:
  - `hx-get`, `hx-post`, `hx-trigger`
  - `hx-target`, `hx-swap="innerHTML"`
- Use Hyperscript for small behaviors instead of custom JS.

### Components / Styling
- Use **Shoelace** web components via CDN for buttons, inputs, dialogs.
- All shared CSS in `/interfaces/_shared/styles/vars.css`.
- No inline styles except quick prototypes.

---

## PWA (OPTIONAL)
- Add `public/manifest.webmanifest` + `public/sw.js` for installable app on Android.
- Keep service worker minimal (cache shell + icons).
- Enable `display: standalone` and dark theme colors.

---

## MODULE MANIFEST

Example for a UI + API module:

```json
{
  "id": "reviewer",
  "name": "Reviewer",
  "entry": "routes.py",
  "ground_truth": "ground_truth.md",
  "requires": ["auth", "user"],
  "provides": ["reviewList", "reviewEditor"],
  "schema_version": "1.0.0"
}
```

Rules:
- `entry` points to the Flask blueprint file.
- `templates/` contains HTML fragments referenced by routes.
- `ground_truth.md` documents module purpose, APIs, and UI components.
- Dependencies (`requires`) and exports (`provides`) are explicit.
- The loader discovers and mounts modules based on this manifest.

---

## TESTING
- API: pytest + HTTP client for REST endpoints.
- UI: snapshot test rendered fragments; verify HTMX swaps.
- PWA: optional Lighthouse run for installability and performance.

---

## DEPLOYMENT
- Python 3.10+
- `pip install flask jinja2`
- Optional: `pip install gunicorn` for production serving.
- Static assets (Shoelace, HTMX, Hyperscript) via CDN — no build pipeline.
