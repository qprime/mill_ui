# Recipe 04: Custom Template (Python)

**Goal:** Create a small, reusable Python template that expands into a `LayoutAST` (shapes + features), then run the normal AST → IR → planner pipeline.

**Difficulty:** Intermediate  
**Time:** 20–30 minutes  
**Prerequisites:** Recipe 03 (basic template usage)

---

## What You'll Build

A `templates/`-style class that generates a simple “panel with holes” part:
- Outer rectangle: profile through-cut (outside)
- Optional pocket: shallow recess
- Hole pattern: N mounting holes

This recipe is intentionally small so you can copy/paste it as a starting point for more serious templates.

---

## Step 1: Create a Template Class

Create `templates/panel_with_holes.py`:

```python
from __future__ import annotations

from layout_ast.layout import LayoutAST, Sheet, Item, Geometry, Placement, Feature


class PanelWithHoles:
    @staticmethod
    def expand_to_ast(*, params: dict, sheet_thickness_mm: float) -> LayoutAST:
        w = float(params["panel_w_mm"])
        h = float(params["panel_h_mm"])
        pocket_depth = float(params.get("pocket_depth_mm", 0.0))

        # Hole pattern (absolute coordinates, centered on the panel)
        hole_d = float(params.get("hole_diameter_mm", 5.0))
        holes = params.get("holes", [])

        cx, cy = w / 2.0, h / 2.0

        items: list[Item] = [
            Item(
                kind="shape",
                type="Rect",
                geometry=Geometry(data={"w_mm": w, "h_mm": h}),
                placement=Placement(center_xy_mm=(cx, cy)),
                feature=Feature(type="profile", depth="through", side="outside"),
                shape_id="panel:outer",
            )
        ]

        if pocket_depth > 0.0:
            items.append(
                Item(
                    kind="shape",
                    type="Rect",
                    geometry=Geometry(data={"w_mm": w - 20.0, "h_mm": h - 20.0}),
                    placement=Placement(center_xy_mm=(cx, cy)),
                    feature=Feature(type="pocket", depth="through", depth_mm=pocket_depth),
                    shape_id="panel:recess",
                )
            )

        for i, (hx, hy) in enumerate(holes, start=1):
            items.append(
                Item(
                    kind="shape",
                    type="Circle",
                    geometry=Geometry(data={"diameter_mm": hole_d}),
                    placement=Placement(center_xy_mm=(float(hx), float(hy))),
                    feature=Feature(type="hole", depth="through", depth_mm=float(params.get("hole_depth_mm", 8.0))),
                    shape_id=f"panel:hole:{i}",
                )
            )

        return LayoutAST(
            sheet=Sheet(width_mm=w, height_mm=h, thickness_mm=float(sheet_thickness_mm)),
            items=tuple(items),
        )
```

Optional: export it in `templates/__init__.py` so it’s importable like `from templates import PanelWithHoles`.

---

## Step 2: Use the Template to Generate LayoutAST

Create `panel_with_holes_demo.py`:

```python
from templates.panel_with_holes import PanelWithHoles

ast = PanelWithHoles.expand_to_ast(
    params={
        "panel_w_mm": 300.0,
        "panel_h_mm": 180.0,
        "pocket_depth_mm": 3.0,
        "hole_diameter_mm": 6.0,
        "hole_depth_mm": 10.0,
        "holes": [
            (30.0, 30.0),
            (270.0, 30.0),
            (30.0, 150.0),
            (270.0, 150.0),
        ],
    },
    sheet_thickness_mm=19.0,
)

print(ast.to_json())
```

Run:
```bash
PYTHONPATH=. python3 panel_with_holes_demo.py > panel_with_holes.layout.json
```

---

## Step 3: Plan Toolpaths and Emit G-code

Create `panel_with_holes_gcode.py`:

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

ast = parse_layout_json("panel_with_holes.layout.json")
intents = ast_to_removal_intents(ast)

hints = removal_intents_to_v1_hints(intents, kerf_width_mm=3.175, min_channel_width_mm=6.0)

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

open("panel_with_holes.nc", "w", encoding="utf-8").write("\n".join(all_gcode))
print("Wrote panel_with_holes.nc")
```

Run:
```bash
PYTHONPATH=. python3 panel_with_holes_gcode.py
```

---

## Variations

- **Parameterized hole grid**: generate `holes` from `(rows, cols, pitch_mm, margin_mm)` instead of explicit coordinates.
- **Two-tool workflow**: generate separate hints per tool diameter (rough vs finish).
- **Multiple outputs**: render a blueprint SVG (Recipe 08) and export STL (see `docs/recipes/generate_outputs.py` for a working STL pipeline).
