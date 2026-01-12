# Recipe 12: Edge Treatment Intent (Allowance / Fillet / Chamfer)

**Goal:** Attach edge intent annotations to a profile or pocket so planners (current or future) can implement rough/finish strategies and decorative edges.

**Difficulty:** Advanced (semantic intent)  
**Time:** 10–15 minutes  
**Prerequisites:** Compositional PML

---

## PML Syntax Refresher

```pml
edge allowance <rough_mm> <finish_mm>
edge fillet <radius_mm>
edge chamfer <distance_mm>
```

---

## Example: Pocket With “Rough + Finish” Allowance Intent

Save as `edge_allowance_pocket.pml`:

```pml
sheet 300.00mm 200.00mm 19.00mm

rect recess pocket 4.00mm
    edge allowance 0.50mm 0.10mm
```

Resolve to JSON:
```bash
PYTHONPATH=. python3 -m cli.parse_compositional_pml edge_allowance_pocket.pml --resolve --format json > edge_allowance_pocket.json
```

In the resolved JSON, the pocket geometry includes an `edge_treatment` dict.

---

## Convert to RemovalIntent Including Edge Treatment

As with keepout islands (Recipe 11), edge treatment metadata is easiest to inspect via the `Item` adapter:

```python
from layout_ast.parsers import parse_layout_json
from adapters.hints_to_removal import item_to_removal_intent

ast = parse_layout_json("edge_allowance_pocket.json")
item = [it for it in ast.items if it.kind == "shape" and it.feature and it.feature.type == "pocket"][0]
intent = item_to_removal_intent(item)

edge = intent.constraints.edge_treatment
print(edge)
```

---

## Current Planner Support

Edge treatment is **semantic annotation** today:
- stored on the resolved item’s geometry (`edge_treatment`)
- propagated into IR constraints by the item-level adapter

The default v1 planner path does not yet use edge intent to create multiple passes/tools.

