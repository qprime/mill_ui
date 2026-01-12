# Recipe 10: Hole Patterns With Compositional Grid

**Goal:** Create a repeatable hole pattern (e.g., shelf pin holes) using compositional layout managers (`inset` + `grid`) without hand-authoring coordinates.

**Difficulty:** Intermediate  
**Time:** 10–15 minutes  
**Prerequisites:** Familiarity with compositional PML

---

## Design: Two Columns of Shelf Pin Holes

- Panel: 300×700×19mm
- Margin: 25mm
- Hole diameter: 5mm
- Hole depth: 12mm
- Two columns (left/right), 16 rows

Save as `shelf_pin_holes.pml`:

```pml
sheet 300.00mm 700.00mm 19.00mm

rect panel
    inset 25.00mm
        grid 16 2 gap 20.00mm
            cell
                circle diameter 5.00mm hole 12.00mm
```

Notes:
- `rect panel` establishes the region for layout; it has **no feature**, so it won’t be machined by itself.
- The `circle ... hole ...` node is replicated into each grid cell.

---

## Resolve to Flat JSON

```bash
PYTHONPATH=. python3 -m cli.parse_compositional_pml shelf_pin_holes.pml --resolve --format json > shelf_pin_holes.json
```

You can now render a blueprint (Recipe 08):
```bash
PYTHONPATH=. python3 -c "from layout_ast.parsers import parse_layout_json; from export.blueprint_svg import render_blueprint_svg; ast=parse_layout_json('shelf_pin_holes.json'); open('shelf_pin_holes.svg','w',encoding='utf-8').write(render_blueprint_svg(ast))"
```

---

## Generate G-code (Holes Only)

```python
from layout_ast.parsers import parse_layout_json
from adapters.ast_to_removal import ast_to_removal_intents
from adapters.removal_to_planner import removal_intents_to_v1_hints
from cam.config import Config
from cam.planner.passes import plan_passes
from cam.post.gcode import write_gcode
from cam.model.stock import Stock
from cam.model.material import Material
from cam.model.machine import Machine

ast = parse_layout_json("shelf_pin_holes.json")
intents = ast_to_removal_intents(ast)
hints = removal_intents_to_v1_hints(intents)

tool_db = [
    {"name": "5mm_endmill", "diameter": 5.0, "kind": "flat", "rpm": 18000, "feed_xy": 1200, "feed_z": 250}
]
config = Config(safe_z_mm=6.0)
material = Material(name="plywood")
machine = Machine()
stock = Stock(width=ast.sheet.width_mm, height=ast.sheet.height_mm, thickness=ast.sheet.thickness_mm)

passes, _summary = plan_passes(
    hints,
    config=config,
    tool_db=tool_db,
    material=material,
    machine=machine,
    stock=stock,
)

all_gcode = []
for p in passes:
    moves = p.get("moves") or []
    if not moves:
        continue
    all_gcode.append(write_gcode(moves, safe_z=config.safe_z_mm))

open("shelf_pin_holes.nc", "w", encoding="utf-8").write("\n".join(all_gcode))
print("Wrote shelf_pin_holes.nc")
```

---

## Variations

- **Edge referencing**: add another `inset` level to shift the usable grid region.
- **Single column**: `grid 16 1 gap 20mm`.
- **Different spacing**: adjust `gap` (affects both row and column spacing).
