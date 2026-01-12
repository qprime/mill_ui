# Recipe 06: Multiple Depths in One Part (Profile + Pocket + Holes)

**Goal:** Combine multiple features with different depths on a single part: outer through profile, shallow pocket, and blind/through holes.

**Difficulty:** Beginner/Intermediate  
**Time:** 10–20 minutes  
**Prerequisites:** Recipe 01

---

## Design: A Simple Mounting Plate

- Outer cut: 180×120mm through (outside profile)
- Pocket: 140×80mm, 3mm deep (recess)
- Holes: four 6mm holes, 10mm deep

Save as `multi_depth_plate.pml`:

```pml
sheet 220mm 160mm 19mm

rect plate:outer at 110mm,80mm size 180mm,120mm profile through outside
rect plate:recess at 110mm,80mm size 140mm,80mm pocket 3mm

circle hole:1 at 50mm,40mm diameter 6mm hole 10mm
circle hole:2 at 170mm,40mm diameter 6mm hole 10mm
circle hole:3 at 50mm,120mm diameter 6mm hole 10mm
circle hole:4 at 170mm,120mm diameter 6mm hole 10mm
```

Convert to JSON:
```bash
PYTHONPATH=. python3 -m cli.convert_layout --from pml --to json multi_depth_plate.pml multi_depth_plate.json
```

---

## Generate G-code

Create `multi_depth_plate_gcode.py`:

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

ast = parse_layout_json("multi_depth_plate.json")
intents = ast_to_removal_intents(ast)
hints = removal_intents_to_v1_hints(intents, kerf_width_mm=3.175, min_channel_width_mm=6.0)

tool_db = [
    {"name": "6mm_endmill", "diameter": 6.0, "kind": "flat", "rpm": 18000, "feed_xy": 2000, "feed_z": 300}
]
config = Config(safe_z_mm=6.0, pocket_finish_perimeter=True)
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

open("multi_depth_plate.nc", "w", encoding="utf-8").write("\n".join(all_gcode))
print("Wrote multi_depth_plate.nc")
```

Run:
```bash
PYTHONPATH=. python3 multi_depth_plate_gcode.py
```

---

## Variations

- **Through holes**: change `hole 10mm` to `hole 19mm` (or `hole through` if you’re using JSON/Python).
- **Countersink/counterbore**: model as a larger, shallow pocket centered on the hole.
- **Rough-only pocket**: set `Config(pocket_finish_perimeter=False)` (see Recipe 09).
