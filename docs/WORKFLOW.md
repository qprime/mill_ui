<!-- spec-style -->
# mill_ui Workflow

As-Of Date: 2026-01-19
Document Type: Pipeline Reference

---

## Pipeline Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                               INPUT FORMATS                                          │
├────────────────┬──────────────────┬─────────────────────┬────────────────────────────┤
│  Flat PML      │ Compositional PML│ JSON/Python Template│  Nest PML (.nest)          │
│  (explicit xy) │ (layout managers)│ (programmatic)      │  (bin-packing jobs)        │
└───────┬────────┴────────┬─────────┴─────────┬───────────┴────────────┬───────────────┘
        │                 │                   │                        │
        │ pml.parser      │ pml.comp_parser   │ layout_ast.parsers     │ pml.nest_parser
        ▼                 ▼                   │                        ▼
    ┌────────────────────────────────────────┐│      ┌─────────────────────────┐
    │   CompositionalLayoutAST               ││      │       NestJob           │
    │   (hierarchical, relative)             ││      └───────────┬─────────────┘
    └────────────────┬───────────────────────┘│                  │ nesting.api
                     │ resolve_layout()       │      ┌───────────▼─────────────┐
                     ▼                        │      │    Nesting Algorithms   │
                                              │      │  • guillotine • maxrects│
         ┌───────────────────────────────────┐│      └───────────┬─────────────┘
         │       LayoutAST (FLAT)            │◄──────────────────┘
         │  - Sheet, Items, Placement        │   (multiple LayoutASTs from nesting)
         └───────────────┬───────────────────┘
                         │
         ┌───────────────┼───────────────────┐
         ▼               ▼                   ▼
    ┌─────────┐   ┌─────────────┐    ┌──────────────────┐
    │ PML     │   │ JSON        │    │ SVG Preview      │
    │ Emitter │   │ Emitter     │    │                  │
    └─────────┘   └─────────────┘    └──────────────────┘
                         │
                         │ ast_to_removal_intents()
                         ▼
         ┌───────────────────────────────────┐
         │      RemovalIntent IR             │◄─── Validation Layer
         │  - region_id, bounds, z_top/bottom│
         │  - allowance, constraints         │
         └───────────────┬───────────────────┘
                         │
         ┌───────────────┼───────────────────┬────────────────┐
         ▼               ▼                   ▼                ▼
    ┌─────────┐   ┌─────────────┐    ┌──────────┐    ┌──────────────┐
    │ STL     │   │ STEP        │    │ DXF      │    │ DWG          │
    │[PARTIAL]│   │[BROKEN]     │    │[FUTURE]  │    │[FUTURE]      │
    └─────────┘   └─────────────┘    └──────────┘    └──────────────┘
                         │
                         │ removal_intents_to_v1_hints()
                         ▼
         ┌───────────────────────────────────┐
         │      Planner Hint Dicts           │
         └───────────────┬───────────────────┘
                         │ plan_all_passes()
                         ▼
         ┌───────────────────────────────────┐
         │      CAM Execution Plan           │
         │  Profile/Pocket/Hole/Engrave      │
         └───────────────┬───────────────────┘
                         │
         ┌───────────────┼───────────────────┐
         ▼               ▼                   │
    ┌──────────┐   ┌─────────────┐          │
    │ Path     │   │ Native CAM  │          │
    │Strategies│──▶│ Core (C++)  │          │
    └──────────┘   └─────────────┘          │
                         │
                         │ post_gcode()
                         ▼
         ┌───────────────────────────────────┐
         │          G-CODE                   │
         │  G0/G1/G2/G3 + M commands         │
         └───────────────────────────────────┘
```

---

## Pipeline Stages

| Stage | Input | Output | Entry Point |
|-------|-------|--------|-------------|
| 1. Parse | PML/JSON text | CompositionalLayoutAST or LayoutAST | `parse_compositional_pml()`, `parse_pml()` |
| 1B. Domain/Generator | Domain params | LayoutAST Items | `Domain`, generators |
| 2. Resolution | CompositionalLayoutAST | LayoutAST (flat) | `resolve_layout()` |
| 2B. Nesting | NestJob | list[LayoutAST] | `nest_and_generate()` |
| 3. IR Conversion | LayoutAST | list[RemovalIntent] | `ast_to_removal_intents()` |
| 4A. CAD Export | LayoutAST/IR | STL/STEP/SVG | `cad/export/` |
| 4B. CAM Planning | RemovalIntent | Move sequences | `plan_all_passes()` |
| 5. Post-process | Moves | G-code | `post_gcode()` |

---

## Input Format Selection

| Format | Use Case |
|--------|----------|
| Flat PML | Simple layouts, explicit control |
| Compositional PML | Complex layouts, reusable components |
| JSON | Programmatic generation, AI output |
| Python Templates | Standardized components (Shaker, etc.) |
| Nest PML | Production runs, multi-sheet jobs |
| Domain/Generator | Complex programmatic designs, SKU variation |

---

## Export Format Selection

| Format | Purpose | Status |
|--------|---------|--------|
| G-code | CNC execution | Production |
| STL | 3D visualization | Partial |
| SVG | 2D layout debugging | Working |
| STEP | 3D CAD interop | Broken |
| DXF/DWG | 2D CAD format | Future |

---

## Native Backend Requirements

| Task | Native Required |
|------|-----------------|
| Parse PML → LayoutAST | No |
| AST → RemovalIntent IR | No |
| IR validation | No |
| Toolpath generation | Yes |
| G-code output | Yes |

---

## Key Files

| Category | Files |
|----------|-------|
| Input Processing | `pml/parser.py`, `pml/compositional_parser.py`, `pml/nest_parser.py` |
| Resolution | `resolution/layout_resolver.py` |
| Nesting | `nesting/api.py`, `nesting/guillotine.py`, `nesting/maxrects.py` |
| Core Pipeline | `adapters/ast_to_removal.py`, `adapters/removal_to_planner.py` |
| CAM | `cam/planner/plan.py`, `cam/post/gcode.py` |
| CAD Export | `cad/export/panel_stl.py`, `export/svg_removal.py` |
| Validation | `validation/removal_checks.py`, `validation/runner.py` |

---

## Status Summary

| Category | Status |
|----------|--------|
| PML → LayoutAST → RemovalIntent → G-code | Production |
| Nesting (guillotine, maxrects) | Production |
| Profile tabs (F004) | Production |
| Pocket cleanup pass (F001) | Production |
| STL export | Partial |
| SVG visualization | Working |
| STEP export | Broken (import path) |
| DXF/DWG export | Future |
