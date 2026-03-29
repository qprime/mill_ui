---
description: Look up mill_ui terminology, abbreviations, invariant ID prefixes, G-code commands, data structures, and manufacturing terms. Use when the user asks what a term means, what an abbreviation stands for, or needs clarification on project-specific vocabulary.
---

# Glossary

## Abbreviations & Acronyms

| Term | Expansion | Context |
|------|-----------|---------|
| AST | Abstract Syntax Tree | Parse tree for PML (`layout_ast/`) |
| CAM | Computer-Aided Manufacturing | Pipeline from IR to G-code (`cam/`) |
| CNC | Computer Numerical Control | Machine tool controller |
| CS-n | Coordinate System invariant n | Numbered axioms in `docs/invariants/coordinates.md` |
| DS-n | Data Structure invariant n | Numbered axioms in `docs/invariants/data_structures.md` |
| DM-n | Domain invariant n | Numbered axioms in `docs/invariants/domains.md` |
| ET | ElementTree | `xml.etree.ElementTree` (SVG construction) |
| FFI | Foreign Function Interface | C++/Python boundary via pybind11 (`cam/native/core.py`) |
| GC-n | G-Code invariant n | Numbered axioms in `docs/invariants/gcode.md` |
| GN-n | Generator invariant n | Numbered axioms in `docs/invariants/generators.md` |
| IR | Intermediate Representation | RemovalIntent semantic layer (`ir/`) |
| JSON | JavaScript Object Notation | LayoutAST serialization format |
| MCP | Model Context Protocol | IDE integration server (`mill_mcp/`) |
| PDF | Portable Document Format | Blueprint export (`export/blueprint_pdf.py`) |
| PL-n | Pipeline invariant n | Numbered axioms in `docs/invariants/pipeline.md` |
| PML | Panel Machining Language | Declarative YAML layout language (`pml/`) |
| RPM | Revolutions Per Minute | Spindle speed |
| SVG | Scalable Vector Graphics | Blueprint visualization (`export/blueprint_svg.py`) |
| YAML | YAML Ain't Markup Language | PML source format |

## G-Code Commands (ISO 6983)

| Code | Meaning |
|------|---------|
| F | Feed rate (mm/min) |
| G0 | Rapid positioning (no cutting) |
| G1 | Linear interpolated cut |
| G4 | Dwell/pause (P = seconds) |
| M3 | Spindle start (clockwise) |
| M5 | Spindle stop |
| S | Spindle speed (RPM) |

## Pipeline Stages

| Stage | Module | Transform |
|-------|--------|-----------|
| Parse | `pml/yaml_parser.py` | PML YAML → CompositionalLayoutAST |
| Resolve | `resolution/layout_resolver.py` | CompositionalLayoutAST → LayoutAST |
| AST→IR | `adapters/ast_to_removal.py` | LayoutAST → list[RemovalIntent] |
| IR→Planner | `adapters/removal_to_planner.py` | RemovalIntent → PlannerInput via `removal_intents_to_planner_input()` |
| Plan | `cam/planner/passes/` | PlannerInput → PassRecord list |
| Post | `cam/post/gcode.py` | Move list → G-code string |
| Export | `export/blueprint_svg.py` | DiagramIR → SVG blueprint |

## Core Data Structures

| Name | Location | Description |
|------|----------|-------------|
| Bounds2D | `ir/removal_intent.py` | Axis-aligned bounding box (x_min, x_max, y_min, y_max) |
| CompositionalLayoutAST | `layout_ast/compositional.py` | Hierarchical AST with relative positioning |
| DiagramIR | `diagram_ir/diagram.py` | Intermediate representation for visualization |
| Domain | `domains/domain.py` | 2D bounded region supporting algebraic ops |
| Feature | `layout_ast/layout.py` | Machining feature attached to an Item (type, depth, constraints) |
| Item | `layout_ast/layout.py` | Single shape/feature entry in a LayoutAST |
| LayoutAST | `layout_ast/layout.py` | Flat AST with absolute coordinates |
| MultiDomain | `domains/domain.py` | List of disjoint Domain regions |
| PassRecord | `cam/planner/passes/__init__.py` | Single planner pass result (tool, moves, G-code file) |
| PipelineResult | `cam/pipeline.py` | Full pipeline output (AST, intents, passes, G-code, SVG, metrics) |
| PlannerInput | `cam/planner/planner_input.py` | Typed input to the CAM planner (replaces untyped hints dict) |
| RemovalIntent | `ir/removal_intent.py` | Semantic encoding of what to machine |

## Machining Features

| Term | Description |
|------|-------------|
| Bevel | Angled edge cut (width, angle, inner depth) |
| Chamfer | Angled edge break (width, angle) |
| Engrave | Shallow surface carving |
| Hole | Through-hole removal |
| Pocket | Clearing an enclosed area to a depth |
| Profile | Cutting around a boundary (inside/outside/on) |
| Surface | Facing pass to flatten stock surface (with optional cooling dwells) |
| Tab | Holding bridge left during profile cuts |

## Depth Modes

| Mode | Description |
|------|-------------|
| constant | Flat depth cut |
| linear_gradient | Tapered depth with direction angle |
| v_carve | V-shaped engraving with bit angle |

## Layout Managers

| Manager | Purpose |
|---------|---------|
| Assembly | Assembly definition with joinery |
| Cell | Individual grid cell |
| Frame | Border inset with auto outer profile |
| Grid | Row/column cell division |
| Inset | Uniform shrink on all sides |
| Keepout | No-machining exclusion zone |
| Panel | Simple container |
| Place | Manual positioning |
| RaisedPanel | Decorative beveled panel (generator: `RaisedPanelGen`) |
| Split | Window-pane division (rail/mullion) |

## Shape Types

| Shape | Key Parameters |
|-------|---------------|
| Arch | width, height, radius |
| Circle | diameter |
| Line | orientation (horizontal/vertical) |
| Polygon | points list |
| Polyline | points list |
| Rect | width, height |
| RoundedRect | width, height, radius, corners |
| SplinePath | points list, tolerance |
| Triangle | base, height |

## Joinery Strategies

Canonical identifiers — do not rename or reinterpret.

| Strategy | Description |
|----------|-------------|
| Butt | Edge-to-face, no interlock |
| Captured | Floating tenon in captured groove |
| Finger | Interlocking fingers (box corners) |
| HalfLap | 50% depth overlap on both sides |

## Assembly Types

| Type | Module | Description |
|------|--------|-------------|
| Beam | `assembly/beam.py` | Laminated/spliced linear member |
| Box | `assembly/primitives.py` | 4-part box with joinery |
| Carcass | `assembly/primitives.py` | Cabinet frame structure |
| Cubby | `assembly/primitives.py` | Multi-compartment frame |

## Nesting Algorithms

| Algorithm | Module | Description |
|-----------|--------|-------------|
| Guillotine | `nesting/guillotine.py` | Fast guillotine-cut bin packing |
| MaxRects | `nesting/maxrects.py` | Free-rectangle tracking bin packing |

## Domain Operations

| Operation | Result |
|-----------|--------|
| inset(d) | Contract boundary inward |
| intersect(other) | Keep only overlapping region |
| offset(d) | Expand boundary outward |
| subtract(other) | Remove overlapping region |

## Move Types

| Class | G-Code | Purpose |
|-------|--------|---------|
| CommentMove | (comment) | Inline annotation |
| CutMove | G1 | Linear cutting feed |
| DwellMove | G4 | Pause/dwell for cooling |
| RapidMove | G0 | Fast non-cutting travel |
| RetractMove | G0 Z | Z-only retract |
| SetFeedMove | F | Set feed rate |
| SetRpmMove | M3/M5 | Spindle control |

## Manufacturing Terms

| Term | Definition |
|------|------------|
| Feedrate | Speed of tool travel during cutting (mm/min) |
| Flute | Cutting edge on an endmill |
| Kerf | Width of material removed by the cutting tool |
| Plunge rate | Vertical feed rate when entering material |
| Safe Z | Height above stock for rapid moves without collision |
| Stepover | Lateral distance between adjacent pocket passes |
| Stock | Raw material workpiece |
| Spoilboard | Sacrificial surface beneath the workpiece |
