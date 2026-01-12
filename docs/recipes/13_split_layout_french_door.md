# Recipe 13: Split Layout (French Door / Paned Pattern)

**Goal:** Use `split` to subdivide a region into panes while reserving material for rails and mullions.

**Difficulty:** Intermediate  
**Time:** 10–20 minutes  
**Prerequisites:** Compositional PML basics

---

## Design: 2×2 Panes With Rails/Mullions

Save as `split_door.pml`:

```pml
sheet 500.00mm 700.00mm 19.00mm

rect door profile through outside
    inset 30.00mm
        split 2 2 rail 60.00mm mullion 60.00mm
            cell
                rect pane pocket 4.00mm
```

Interpretation:
- Outer door gets a through profile cut.
- Inside the inset region, `split` creates 4 panes separated by 60mm rails/mullions.
- Each pane gets a shallow pocket.

---

## Resolve to Flat JSON and Render a Blueprint

```bash
PYTHONPATH=. python3 -m cli.parse_compositional_pml split_door.pml --resolve --format json > split_door.json
PYTHONPATH=. python3 -c "from layout_ast.parsers import parse_layout_json; from export.blueprint_svg import render_blueprint_svg; ast=parse_layout_json('split_door.json'); open('split_door.svg','w',encoding='utf-8').write(render_blueprint_svg(ast))"
```

---

## Generate G-code

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

ast = parse_layout_json("split_door.json")
intents = ast_to_removal_intents(ast)
hints = removal_intents_to_v1_hints(intents)

tool_db = [
    {"name": "6mm_endmill", "diameter": 6.0, "kind": "flat", "rpm": 18000, "feed_xy": 2000, "feed_z": 300}
]
config = Config(safe_z_mm=6.0)
material = Material(name="MDF")
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

open("split_door.nc", "w", encoding="utf-8").write("\n".join(all_gcode))
print("Wrote split_door.nc")
```

---

## Notes

- `split` reserves rail/mullion widths by shrinking pane regions; it does not automatically generate the bar geometry as separate shapes.
- If you want the rails/mullions to be machined as explicit geometry, model them as additional profile/pocket shapes.
