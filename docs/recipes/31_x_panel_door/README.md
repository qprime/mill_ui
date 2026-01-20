# Recipe 31: X-Panel Door

**Status:** Complete
**Difficulty:** Easy
**Demonstrates:** x_panel generator, parametric X-pattern design

## Overview

This recipe builds an X-panel cabinet door using the `x_panel` generator, which
automatically creates four triangular pockets forming raised diagonal bars in an
X pattern. This is a classic decorative door style often seen in farmhouse and
traditional cabinetry.

## Design

- 400mm x 600mm door blank, 19mm thick
- 50mm frame width around the perimeter
- Inner panel area: 300mm x 500mm (after frame inset)
- x_panel generator with 50mm bar width creates uniform X bars
- Four triangular pockets (6mm deep) automatically computed
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

The X bars width is controlled by the `bar_width` parameter:

```pml
x_panel bar_width 30mm depth 6mm   # Narrower bars
x_panel bar_width 75mm depth 6mm   # Wider bars
```
