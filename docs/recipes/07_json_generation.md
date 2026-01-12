# Recipe 07: JSON Generation (AI-Friendly LayoutAST)

**Goal:** Author `LayoutAST` directly as JSON (or generate it programmatically) and round-trip it through the existing parsers/emitters.

**Difficulty:** Beginner  
**Time:** 10 minutes  
**Prerequisites:** None

---

## Why JSON?

JSON is:
- explicit (no parsing ambiguity)
- easy for tools/LLMs to generate
- directly compatible with `layout_ast/parsers.py`

---

## Minimal LayoutAST JSON

Create `layout.json`:

```json
{
  "sheet": { "width_mm": 300, "height_mm": 200, "thickness_mm": 19 },
  "items": [
    {
      "kind": "shape",
      "type": "Rect",
      "geometry": { "w_mm": 220, "h_mm": 140 },
      "placement": { "center_xy_mm": [150, 100] },
      "feature": { "type": "profile", "depth": "through", "side": "outside" },
      "shape_id": "outer"
    },
    {
      "kind": "shape",
      "type": "Rect",
      "geometry": { "w_mm": 180, "h_mm": 100 },
      "placement": { "center_xy_mm": [150, 100] },
      "feature": { "type": "pocket", "depth_mm": 6.0 },
      "shape_id": "recess"
    }
  ]
}
```

---

## Parse + Canonicalize + Re-emit

Create `json_roundtrip.py`:

```python
from layout_ast.parsers import parse_layout_json

ast = parse_layout_json("layout.json")

# Emit canonical JSON (sorted keys, stable formatting)
canonical = ast.to_json()
open("layout.canonical.json", "w", encoding="utf-8").write(canonical)
print("Wrote layout.canonical.json")
```

Run:
```bash
PYTHONPATH=. python3 json_roundtrip.py
```

---

## Convert From Flat PML → JSON (CLI)

If you already have flat PML:

```bash
PYTHONPATH=. python3 -m cli.convert_layout --from pml --to json input.pml output.json
```

---

## Common Pitfalls

- `layout_ast.parsers.parse_layout_json()` takes a **file path**, not a JSON string.
- For numeric depths, prefer `feature.depth_mm` (and you can omit `feature.depth` entirely).
- `placement.center_xy_mm` is always `[x, y]` in millimeters.

