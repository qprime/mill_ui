<!-- spec-style -->
# Edge Treatment Intent

As-Of Date: 2026-01-19
Document Type: Feature Specification

---

## Purpose

Define edge treatment semantics for profiles and pockets.
Edge treatments influence RemovalIntent constraints for downstream toolpath planning.

---

## Edge Types

| Type | Description | PML Syntax |
|------|-------------|------------|
| allowance | Multi-pass rough/finish operations | `edge allowance <rough_mm> <finish_mm>` |
| fillet | Decorative rounded edge | `edge fillet <radius_mm>` |
| chamfer | Decorative beveled edge | `edge chamfer <distance_mm>` |

---

## Allowance Semantics

Edge allowances enable multi-pass operations with different tools/strategies.

| Parameter | Description |
|-----------|-------------|
| rough_allowance_mm | Stock left after rough pass |
| finish_allowance_mm | Stock left after finish pass |

Multi-tool workflow:
1. Rough pass: Cut to boundary + rough_allowance (larger, faster tool)
2. Finish pass: Cut to boundary + finish_allowance (smaller, precision tool)

Edge allowances are per-edge intent, distinct from global kerf compensation.

---

## Kerf Compatibility

| Concept | Scope | Purpose |
|---------|-------|---------|
| Kerf compensation | Global, tool-dependent | Compensates for tool radius |
| Edge allowances | Per-edge, tool-independent | Multi-pass strategy intent |

Total offset = kerf_offset + edge_allowance

---

## Resolution Behavior

1. Edge nodes extracted from shape children during resolution
2. Edge treatment stored in Item geometry data as `edge_treatment` dict
3. Edge nodes NOT emitted as separate items (metadata only)

---

## RemovalIntent Integration

Edge treatment propagates via `item_to_removal_intent()`:

```python
if removal.constraints.edge_treatment:
    if removal.constraints.edge_treatment.type == "allowance":
        rough = removal.constraints.edge_treatment.rough_allowance_mm
        finish = removal.constraints.edge_treatment.finish_allowance_mm
    elif removal.constraints.edge_treatment.type == "fillet":
        radius = removal.constraints.edge_treatment.radius_mm
```

---

## Limitations

| Limitation | Description |
|------------|-------------|
| Single edge per shape | Only one Edge node per shape currently |
| Intent only | Toolpath strategy not yet implemented |
| No validation | Minimum tool clearance not enforced |

---

## Files

| File | Purpose |
|------|---------|
| layout_ast/compositional.py | Edge node definition |
| ir/removal_intent.py | EdgeTreatment dataclass |
| pml/compositional_parser.py | Edge parsing |
| resolution/layout_resolver.py | Edge extraction logic |
| adapters/hints_to_removal.py | Item → RemovalIntent with edge treatment |
