# Recipe 08: SVG Visualization (Blueprint Output)

**Goal:** Render a layout as a dimensioned SVG “blueprint” so you can visually sanity-check geometry and feature annotations.

**Difficulty:** Beginner  
**Time:** 5–10 minutes  
**Prerequisites:** None

---

## Render a Blueprint SVG From `layout.json`

Create `render_blueprint.py`:

```python
from layout_ast.parsers import parse_layout_json
from export.blueprint_svg import render_blueprint_svg

ast = parse_layout_json("layout.json")

svg = render_blueprint_svg(ast, theme="light")
open("layout.blueprint.light.svg", "w", encoding="utf-8").write(svg)

svg = render_blueprint_svg(ast, theme="dark")
open("layout.blueprint.dark.svg", "w", encoding="utf-8").write(svg)

print("Wrote layout.blueprint.*.svg")
```

Run:
```bash
PYTHONPATH=. python3 render_blueprint.py
```

Open the SVGs in a browser or Inkscape.

---

## Generate Reference Outputs for Built-In Recipes

The existing recipes 01–03 have a generator that produces SVG/STL/G-code fixtures:

```bash
PYTHONPATH=. python3 docs/recipes/generate_outputs.py
```

---

## Tips

- If your layout is compositional PML, resolve it to JSON first:
  ```bash
  PYTHONPATH=. python3 -m cli.parse_compositional_pml input.pml --resolve --format json > layout.json
  ```
- Use SVG output as a fast “diffable” artifact during iteration (commit it or compare it in PRs).

