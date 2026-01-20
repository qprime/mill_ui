# Recipe 31: X-Panel Door

**Status:** Draft
**Difficulty:** Intermediate
**Demonstrates:** Polygon shape primitive, triangular pockets, X-pattern design

## Overview

This recipe builds an X-panel cabinet door using four triangular pockets that meet
at the center, creating raised diagonal bars forming an X pattern. This is a classic
decorative door style often seen in farmhouse and traditional cabinetry.

## Design

- 400mm x 600mm door blank, 19mm thick
- 50mm frame width around the perimeter
- Inner panel area: 300mm x 500mm (after frame inset)
- Four triangular pockets (6mm deep) with 25mm inset from panel edges
- Triangles inset from center by 25mm to create ~50mm wide X bars
- The remaining material forms the raised X pattern crossing the panel

## Output

The `output/` folder contains:
- `intents.json` - RemovalIntent IR representation
- `preview.svg` - Visual blueprint

## Run

```python
from pml.compositional_parser import parse_compositional_pml
from resolution.layout_resolver import resolve_layout
from export.blueprint_svg import render_blueprint_svg

pml = open('docs/recipes/31_x_panel_door/example.pml').read()
ast = parse_compositional_pml(pml)
flat = resolve_layout(ast)
svg = render_blueprint_svg(flat)
```

## Variant: Adjusting X Proportions

The X bars width is controlled by the pocket depth and the triangle vertices.
For wider bars, adjust the triangle points to leave more material between them.
