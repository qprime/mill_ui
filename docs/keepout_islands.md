<!-- spec-style -->
# Keepout/Island Semantics

As-Of Date: 2026-01-19
Document Type: Feature Specification

---

## Purpose

Define keepout feature for creating pockets with preserved material islands.

---

## Terminology

| Term | Definition |
|------|------------|
| Keepout | Layout node marking subregions to preserve during pocket milling |
| Island | Physical result: material left standing within a pocket |

---

## PML Syntax

```pml
rect <id> pocket <depth>mm
    keepout [id]
        <shape nodes defining island boundaries>
```

---

## Behavior

Keepouts use region-relative composition like other layout nodes.
Keepouts work with any shape (rect, circle, rounded_rect).

### Resolution

1. Keepout children resolved within parent region
2. Island bounds computed from resolved keepout shapes
3. Bounds stored in parent shape's geometry data as `islands` array
4. Keepout shapes NOT emitted as separate items (metadata only)

### Island Data Structure

```json
{
  "islands": [
    {
      "x_min": float,
      "x_max": float,
      "y_min": float,
      "y_max": float
    }
  ]
}
```

Coordinates are absolute sheet coordinates.
Circular islands use bounding box.

---

## Supported Operations

| Operation | Supported |
|-----------|-----------|
| Keepout with pocket features | Yes |
| Multiple keepouts per shape | Yes |
| Any shape type for islands | Yes (Rect, Circle, RoundedRect) |
| Composition with layout managers | Yes |
| Nested keepout validation | Parser rejects with error |

---

## Limitations

| Limitation | Description |
|------------|-------------|
| Profile features | Keepouts ignored for profiles (pockets only) |
| Complex shapes | Polyline/Line cannot define keepout boundaries |

---

## RemovalIntent Integration

Islands propagate to RemovalIntent via `item_to_removal_intent()`:

1. Extracts `islands` array from Item geometry data
2. Converts each island dict to `Island` object with `Bounds2D`
3. Attaches islands to `Constraints` in resulting `RemovalIntent`

Downstream toolpath planners receive island information for adaptive clearing.

---

## Files

| File | Purpose |
|------|---------|
| layout_ast/compositional.py | Keepout node definition |
| resolution/layout_resolver.py | Island bounds collection |
| pml/yaml_parser.py | PML YAML parsing with nested keepout validation |
| adapters/hints_to_removal.py | Item → RemovalIntent with island propagation |
