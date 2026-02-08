# SVG Generation Invariants

**Applies to:** Blueprint SVG output (`diagram_render/render_svg.py`, `adapters/layoutast_to_ir.py`)

---

## Overview

The SVG generation system converts LayoutAST to visual blueprints via DiagramIR. The IR decouples layout semantics from SVG rendering.

Pipeline: `LayoutAST -> DiagramIR -> SVG`

---

## Invariants

| ID | Type | Invariant | Description |
|----|------|-----------|-------------|
| SVG-1 | HARD | SHAPE_REGISTRY_COMPLETE | All shape types in DiagramIR have registered renderers |
| SVG-2 | HARD | FEATURE_REGISTRY_COMPLETE | All feature types in LayoutAST map to DiagramIR layers |
| SVG-3 | HARD | THEME_STYLES_VALID | All StyleSpec values are valid (hex colors, positive widths) |
| SVG-4 | HARD | IR_BOUNDS_CONTAIN_SHAPES | All shapes in DiagramIR fall within declared bounds |
| SVG-5 | HARD | SINGLE_RENDER_PATH | Only one LayoutAST->SVG conversion path exists |
| SVG-6 | HARD | CONFIG_NOT_HARDCODED | All layout constants come from SVGConfig, not inline literals |
| SVG-7 | HARD | VALID_XML_OUTPUT | Output is well-formed XML with proper escaping |
| SVG-8 | HARD | VIEWBOX_CONTAINS_CONTENT | All rendered elements fit within SVG viewBox |
| SVG-9 | HARD | DETERMINISTIC_OUTPUT | Same LayoutAST always produces identical SVG |

---

## Shape Types

Registered shape renderers in `diagram_render/render_svg.py`:

| Shape Type | SVG Element | Required Params |
|------------|-------------|-----------------|
| Rect | `<rect>` | x, y, width, height |
| Circle | `<circle>` | cx, cy, r |
| Line | `<line>` | x1, y1, x2, y2 |
| Polyline | `<polyline>` or `<path>` | points |
| Text | `<text>` | x, y, content |
| Path | `<path>` | d |

---

## Feature -> Layer Mapping

Defined in `adapters/layoutast_to_ir.py`:

| Feature Type | DiagramIR Layer |
|--------------|-----------------|
| profile | PROFILE_CUTS |
| pocket | POCKET_REGIONS |
| hole | HOLES |
| engrave | ENGRAVE_PATHS |
| notch | PROFILE_CUTS |
| waste | WASTE_CUTS |

---

## Style Tokens

Defined in `diagram_render/render_svg.py` DiagramTheme:

| Token | Purpose |
|-------|---------|
| default | Fallback style |
| sheet-outline | Sheet boundary |
| profile | Profile cut lines |
| pocket | Pocket regions |
| hole | Drill holes |
| engrave | Engraving paths |
| waste | Waste cut lines |
| toolpath | Toolpath preview |
| dimension | Dimension lines |
| dimension-text | Dimension labels |
| construction | Construction lines |
| label | Part labels |
| notes | Notes text |
| legend | Legend text |
| title | Title block text |
| margin-zone | Sheet margin areas |

---

## Invariant Types

| Type | Meaning |
|------|---------|
| HARD | Violation breaks the system |
