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
from pml import parse_pml
from export.blueprint_svg import render_blueprint_svg

pml = open('docs/recipes/31_x_panel_door/example.pml.yml').read()
ast = parse_pml(pml)
svg = render_blueprint_svg(ast)
```

## Variant: Adjusting X Proportions

The X bars width is controlled by the `bar_width` parameter:

```yaml
- XPanel:
    bar_width: 30mm  # Narrower bars
    depth: 6mm

- XPanel:
    bar_width: 75mm  # Wider bars
    depth: 6mm
```
