# Recipe 11: Pockets With Keepout Islands (Raised Panel)

**Goal:** Define a pocket that preserves a “material island” (a faux raised panel) using `keepout` in compositional PML.

**Difficulty:** Advanced (IR semantics)  
**Time:** 10–20 minutes  
**Prerequisites:** Compositional PML + basic IR inspection

---

## Design: Pocket With a Rectangular Island

Save as `raised_panel_keepout.pml`:

```pml
sheet 400.00mm 400.00mm 19.00mm

rect panel pocket 6.00mm
    keepout
        inset 60.00mm
            rect island
```

This means:
- Cut a 6mm deep pocket over the full sheet region
- But preserve an inset rectangle as an island

---

## Resolve and Inspect the Island Metadata

Resolve to flat JSON:
```bash
PYTHONPATH=. python3 -m cli.parse_compositional_pml raised_panel_keepout.pml --resolve --format json > raised_panel_keepout.json
```

In the resolved JSON, the pocket shape’s geometry will include an `islands` array (computed bounds in sheet coordinates).

---

## Convert to RemovalIntent Including Islands

The canonical `adapters/ast_to_removal.py` path currently focuses on v1-hint compatibility and does not propagate island metadata.

For island-aware IR inspection, convert at the `Item` level:

```python
from layout_ast.parsers import parse_layout_json
from adapters.hints_to_removal import item_to_removal_intent

ast = parse_layout_json("raised_panel_keepout.json")

# Find the pocket item and convert it
pocket_item = [it for it in ast.items if it.kind == "shape" and it.feature and it.feature.type == "pocket"][0]
intent = item_to_removal_intent(pocket_item)

print(intent.region_id)
print("Island count:", len(intent.constraints.islands))
for island in intent.constraints.islands:
    print(island.bounds)
```

---

## Current Planner Support

- The IR can carry islands (`RemovalIntent.constraints.islands`).
- The default v1 planner path does not consume this field via the IR adapter yet.

Use this recipe primarily to:
- author/resolve keepout semantics
- validate island bounds
- drive future island-aware pocket strategies

