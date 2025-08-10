=== FILE: modular.app.framework.design.md ===
# Modular App Framework Guidance v1

## Header Format
# path: docs/modular.app.framework.design.md
# desc: Canonical architectural template for modular web/mobile apps
# api: modular_app_framework
# tags: architecture,modular,react-native,web

## Core Principles
1. Fast spin-up: One design session = working module/app.
2. Plug-and-play: Drop in folder → auto-register → go live.
3. Context-aware: Logic, APIs, and data models discoverable by new modules.
4. Self-documenting: Manifest + ground truth always loaded; no stale docs.
5. Extensible: Add modules, APIs, UI without global rewiring.
6. AI-first: All context available for LLM-driven development and UI generation.

## Architecture
A. Modular App Shell  
- Single codebase, plugin-style monorepo.  
- Each module exports: UI entry point(s), manifest.json, ground_truth.md.  

B. Centralized Loader  
- Scans `/apps/*/manifest.json` and `/apps/*/ground_truth.md` at boot.  
- Exposes manifest & ground truth to: AI context injection, UI registration, live docs.  

C. Shared Business Logic Registry  
- Common code in `/lib` or `/services`, each with its own manifest.  
- Modules reference shared logic declaratively; no deep imports.  

D. Declarative Navigation  
- Manifest defines nav entries/routes.  
- Add module → nav auto-populates.  

E. Metadata-Driven UI Wiring  
- UI derives actions/state from manifest.  
- All features, docs, APIs globally discoverable.

## Minimum Module Structure
/apps/<module>/manifest.json:
```json
{
  "id": "tasks",
  "name": "Task Manager",
  "entry": "index.tsx",
  "ground_truth": "ground_truth.md",
  "requires": ["auth", "user", "tasksAPI"],
  "provides": ["taskList", "taskEditor"]
}
````

/apps/<module>/ground\_truth.md:

```md
# Task Manager Ground Truth
## Purpose
Manage and review user tasks. Supports create, edit, assign, complete, and filter.
## Data Models
- Task
- User
## API Dependencies
- `tasksAPI` for CRUD
- `userAPI` for assignees
## UI Patterns
- List view
- Detail pane
- Status filters
```

## Workflow

1. **Design** – Write manifest + ground truth.
2. **Scaffold** – Create `/apps/<module>/index.tsx`, manifest.json, ground\_truth.md.
3. **Integrate** – Shell auto-discovers, loads context, updates nav/docs.
4. **Iterate** – Refine schema as patterns evolve.

## Boot Process

At boot/build:

* Shell scans all modules for manifest + ground truth.
* Builds global context registry for AI codegen, UI nav, feature discovery, live docs.
* Modules become available system-wide instantly.

## Benefits

* Zero-to-app in one chat.
* Living documentation; versioned & auto-loaded.
* Easy extension by dropping in new modules.
* AI-native: all ground truths available for chat-driven dev.

## Developer How-To

1. Clone repo or starter template.
2. Create `/apps/<your_app>/` with:

   * `index.tsx` (entry point)
   * `manifest.json` (metadata)
   * `ground_truth.md` (purpose, APIs, models, UI patterns)
3. Define shared APIs/logic in `/services` or `/lib`.
4. Drop in folder; update root manifest if needed.
5. Run `yarn dev`; new app appears in UI/nav/docs.

## Next Steps

* Finalize minimum manifest/ground truth schema.
* Bootstrap repo structure: `/apps`, `/lib`, `/services`, `/public`.
* Build shell loader/nav/context registry.
* Create first module (e.g., "tasks" or "reviewer") as a test.
* Refine as modules reveal new needs.
