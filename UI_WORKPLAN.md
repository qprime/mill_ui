# PML Designer UI — Staged Workplan (AI Execution Contract)

You (Claude) are building a CNC-scoped "PML Designer" UI. This is **not** general CAD. It is a structured editor for our **PML / LayoutAST / RemovalIntent** pipeline.

## Core Principle
The UI edits **LayoutAST (canonical)** and views/edits **PML (human)**. The preview is a deterministic rendering of the resolved layout. The system must stay "tree + properties + visualization," QML-designer style.

## Tech Stack (unless you strongly disagree)
- **Frontend:** React + TypeScript + Vite
- **Backend:** FastAPI (thin bridge) that calls existing Python code in `skills.mill_ui`
- **Preview:** SVG (rendered from resolved layout and/or existing exporter)
- **Single source of truth:** LayoutAST JSON in memory

If you propose an alternative stack, keep it equally AI-buildable, cross-device (browser), and fast to iterate.

---

# Stage Table (execute strictly in order)

Each stage must end with:
- Passing tests (unit/integration as applicable)
- A runnable demo
- A clean commit
- Stage marked DONE in this document

**Do not expand scope beyond the current stage.**

---

## UI-S0: Repo Scaffolding + Dev Harness
**Status:** PENDING

**Goal:** Create the minimal repo/app skeleton and verify we can run a local dev environment.

**Deliverables**
- `ui/` folder (or separate repo) with:
  - Vite React TypeScript setup
  - FastAPI backend scaffold
  - README with run commands
- One endpoint: `GET /health`
- One page: "PML Designer (WIP)"

**Acceptance Criteria**
- `npm run dev` launches frontend
- `uvicorn` launches backend
- Frontend calls `/health` and shows "OK"

**Completion Notes:** (fill when done)

---

## UI-S1: Backend Compile Bridge (Parse/Resolve/Preview)
**Status:** PENDING

**Goal:** Provide backend endpoints that turn PML/JSON into a previewable resolved layout.

**Deliverables**

Backend endpoints (FastAPI):

1. `POST /compile/pml`
   - Input: `{ "pml": "<text>" }`
   - Output: `{ "layout_ast": {...}, "warnings": [...], "errors": [...] }`

2. `POST /resolve`
   - Input: `{ "layout_ast": {...} }`
   - Output: `{ "resolved": {...}, "warnings": [...], "errors": [...] }`

3. `POST /render/svg`
   - Input: `{ "resolved": {...} }` (or layout_ast if renderer expects it)
   - Output: `{ "svg": "<svg...>" }`

**Constraints**
- Keep "studio mode" semantics: warnings unless true crash-risk
- Do not invent new language semantics; use existing `skills.mill_ui` modules

**Acceptance Criteria**
- Given a known shaker PML exemplar, backend returns AST + SVG without errors

**Completion Notes:** (fill when done)

---

## UI-S2: Frontend MVP — PML Editor + Live SVG Preview
**Status:** PENDING

**Goal:** Make a usable "PML IDE" that compiles and previews.

**Deliverables**
- Text editor pane (textarea or Monaco)
- "Compile" button + auto-compile on debounce
- SVG preview pane (render inline)
- Error list (line/col if available, otherwise best effort)
- Save/load PML files (local filesystem download/upload is fine for now)

**Acceptance Criteria**
- Paste shaker example → see preview immediately
- Syntax error → error list updates, preview stays last-good

**Completion Notes:** (fill when done)

---

## UI-S3: JSON (LayoutAST) View + Converter
**Status:** PENDING

**Goal:** Add the canonical JSON view and allow AI-friendly workflows.

**Deliverables**
- Tabbed bottom pane:
  - PML tab
  - LayoutAST JSON tab (read-only initially)
- Button: "Export JSON"
- Button: "Import JSON" (loads into editor + preview)
- Backend endpoint (if needed): `POST /convert/json_to_pml` and `POST /convert/pml_to_json`

**Acceptance Criteria**
- PML → JSON view updates
- JSON import produces identical preview

**Completion Notes:** (fill when done)

---

## UI-S4: Tree View (Structured Editor) + Properties Inspector
**Status:** PENDING

**Goal:** Add QML-designer style structure editing.

**Deliverables**
- Tree panel showing LayoutAST/compositional nodes
- Inspector panel for selected node:
  - Numeric fields with mm units
  - Enums for feature types
  - Add/remove child nodes (context-aware)
- Tree edits update JSON + PML + preview

**Constraints**
- Do NOT implement freehand drawing
- Editing is structural (nodes + properties) only

**Acceptance Criteria**
- Create shaker door using tree only (no typing)
- Preview updates live

**Completion Notes:** (fill when done)

---

## UI-S5: Reusable Components + Library
**Status:** PENDING

**Goal:** Make composition-of-compositions real: components/templates as reusable assets.

**Deliverables**
- "Extract to Component" action from a subtree
- Component library browser (local folder-backed)
- "Instantiate component" into current layout
- Save a design bundle:
  - `design.pml`
  - `design.json`
  - `preview.svg`
  - `manifest.json`

**Acceptance Criteria**
- Create a component once, place 4 instances on a sheet, export bundle

**Completion Notes:** (fill when done)

---

## UI-S6: Sheet Composition UX (Place/Grid/Split Helpers)
**Status:** PENDING

**Goal:** Make "4 doors + 3 drawers" easy without manual editing.

**Deliverables**
- UI helpers:
  - "Add Place Grid"
  - "Set rows/cols/gap"
  - "Auto-fill next slots"
- Visual overlay in preview showing cell boundaries

**Acceptance Criteria**
- Build a mixed sheet layout in <2 minutes using only UI

**Completion Notes:** (fill when done)

---

## UI-S7: Outputs (G-code + SVG Dims + STL/STEP as available)
**Status:** PENDING

**Goal:** One-click compilation outputs for real work.

**Deliverables**

Backend endpoints:
- `POST /export/gcode`
- `POST /export/svg_dims` (or wireframe if dims not wired)
- `POST /export/stl` (optional if already available)
- `POST /export/step` (optional; if missing native backend, show "unavailable" cleanly)

Frontend:
- Output panel with download buttons

**Acceptance Criteria**
- Shaker door layout exports G-code and SVG preview reliably

**Completion Notes:** (fill when done)

---

## UI-S8: Semantic DWG Overlays + Tool Preview (V2 UX)
**Status:** PENDING

**Goal:** Add CNC-specific overlays that DWG can't express cleanly.

**Deliverables**
- Toggle overlays:
  - Pockets/profiles/engraves/holes
  - Allowance bands (if supported)
  - Keepouts/islands (if supported)
- Tool preview widget:
  - Tool type: flat/ball/V
  - Diameter
  - Overlay tool envelope stroke + effective boundary preview (preview-only)

**Acceptance Criteria**
- Changing tool diameter updates preview overlays without recompiling geometry semantics

**Completion Notes:** (fill when done)

---

## UI-S9: Photo-to-Template Intake (V3)
**Status:** PENDING

**Goal:** Support "photo → style template" library building.

**Deliverables**
- Upload photo
- Backend returns draft template + overlay SVG
- Minimal question loop if uncertain
- Save as component bundle

**Acceptance Criteria**
- Ingest a door photo → produce a reusable template entry

**Completion Notes:** (fill when done)

---

# Stage Execution Rules (MUST FOLLOW)

1. **One stage at a time.** No bundling.
2. **Keep diffs minimal and scoped.**
3. **Prefer adding tests/assertions over refactors.**
4. **No "general CAD features."** No constraints solver.
5. **Maintain studio-mode permissiveness.**

Before proceeding with any stage:
1. Restate the stage deliverables and acceptance criteria
2. Propose the exact folder layout
3. Wait for "go" before proceeding

---

# Current Status

**Current Stage:** UI-S0 (Repo Scaffolding + Dev Harness)
**Overall Progress:** 0/9 stages complete

---

# Architecture Notes

## Integration with Existing mill_ui

The UI will integrate with the existing mill_ui Python codebase:

- **PML Parsing:** `skills.mill_ui.pml.yaml_parser` (YAML-based PML)
- **LayoutAST:** `skills.mill_ui.layout_ast.layout` and `skills.mill_ui.layout_ast.compositional`
- **Resolution:** `skills.mill_ui.resolution.layout_resolver` (compositional → flat)
- **RemovalIntent IR:** `skills.mill_ui.ir.removal_intent`
- **CAM Adapters:** `skills.mill_ui.adapters.ast_to_removal`, `skills.mill_ui.adapters.removal_to_planner`
- **Export:** `skills.mill_ui.export.svg_removal` (SVG with RemovalIntent overlay)
- **CAD Export:** `skills.mill_ui.cad.export.svg_dims` (may be functional), others need import fixes

## UI Does NOT Implement:
- New language features
- New geometric operations
- CAM planning logic
- G-code generation

## UI DOES Implement:
- Visual editing of existing LayoutAST
- Component library management
- Layout composition helpers (grid, split, etc.)
- Multi-format I/O (PML, JSON, SVG preview)
- Export orchestration (calls existing backends)

---

# Technical Constraints

## Studio Mode
The UI maintains "studio mode" semantics from the core system:
- Warnings for questionable inputs (overlaps, tight tolerances)
- Errors only for true crash-risk (negative depths, invalid geometry)
- Permissive: let users experiment, warn don't block

## No Client-Side Compilation
All PML parsing, AST resolution, RemovalIntent generation, and rendering happen server-side:
- Keeps frontend simple (React UI only)
- Reuses battle-tested Python code
- No duplication of parsing/semantic logic
- Client just sends text, receives JSON/SVG

## Deterministic Preview
Preview must be deterministic from LayoutAST:
- Same AST → same SVG every time
- No client-side rendering variability
- Preview accurately represents what G-code will cut

---

# Development Workflow

## Per-Stage Process
1. Read stage description
2. Restate deliverables + acceptance criteria
3. Propose folder structure
4. Wait for user approval ("go")
5. Implement minimal scope
6. Write tests
7. Create demo
8. Commit with message: `[UI-SX] <brief description>`
9. Mark stage DONE in this document
10. Wait for user to approve next stage

## Testing Requirements
Each stage must include:
- Backend: pytest tests for new endpoints
- Frontend: Manual verification via running demo
- Integration: End-to-end workflow validation

## Commit Messages
Format: `[UI-SX] <description>`

Examples:
- `[UI-S0] Scaffold Vite React + FastAPI health check`
- `[UI-S1] Add PML compile, resolve, SVG render endpoints`
- `[UI-S2] Implement PML editor with live preview`

---

# Future Considerations (Not In Scope)

The following are explicitly OUT OF SCOPE for this workplan:

- General CAD features (constraints, snapping, dimensions as editing primitives)
- Freehand drawing or sketch-based input
- Real-time collaborative editing
- 3D rendering (2.5D SVG preview is sufficient)
- Alternative CAM backends (use existing v1 planner)
- Native mobile apps (browser-based is fine)

These may be considered in future iterations, but not during this staged rollout.

---

# Success Criteria (Overall Project)

The PML Designer UI is complete when:

1. **A non-programmer can create a shaker door** using only the UI (no code/text editing)
2. **The UI exports production-ready G-code** via existing mill_ui pipeline
3. **Components are reusable** (create once, place many times)
4. **Complex layouts are easy** (4 doors + 3 drawers in <2 minutes)
5. **Photo templates work** (upload door photo → generate reusable template)
6. **All 9 stages pass acceptance criteria**

---

# Appendix: Example Data

## Shaker Door PML (Compositional)
```pml
sheet 400.00mm 600.00mm 19.00mm

rect outer profile through outside
    inset 50.00mm
        rect inner pocket 6.00mm
```

## Expected LayoutAST (Flat, Resolved)
```json
{
  "sheet": {
    "width_mm": 400.0,
    "height_mm": 600.0,
    "thickness_mm": 19.0
  },
  "items": [
    {
      "kind": "shape",
      "type": "Rect",
      "geometry": {
        "width_mm": 400.0,
        "height_mm": 600.0
      },
      "center_xy_mm": [200.0, 300.0],
      "feature": {
        "type": "profile",
        "profile_type": "outside",
        "depth_mm": 19.0
      }
    },
    {
      "kind": "shape",
      "type": "Rect",
      "geometry": {
        "width_mm": 300.0,
        "height_mm": 500.0
      },
      "center_xy_mm": [200.0, 300.0],
      "feature": {
        "type": "pocket",
        "depth_mm": 6.0
      }
    }
  ]
}
```

## Expected RemovalIntent IR (conceptual)
```python
[
  RemovalIntent(
    region_id="outer_profile",
    bounds=Bounds2D(0, 0, 400, 600),
    z_top=0.0,
    z_bottom=-19.0,
    allowance=Allowance.OUTSIDE,
    constraints=Constraints(tabs=[], keepouts=[], islands=[]),
    metadata={"source": "outer"}
  ),
  RemovalIntent(
    region_id="inner_pocket",
    bounds=Bounds2D(50, 50, 350, 550),
    z_top=0.0,
    z_bottom=-6.0,
    allowance=Allowance.INSIDE,
    constraints=Constraints(tabs=[], keepouts=[], islands=[]),
    metadata={"source": "inner"}
  )
]
```

---

**End of Workplan**

When ready to begin UI-S0, restate the deliverables and propose folder structure.
