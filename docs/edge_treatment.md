<!-- spec-style -->
# Edge Treatment and Edge Features

As-Of Date: 2026-02-24
Document Type: Feature Specification

---

## Two Distinct Systems

The codebase has two separate mechanisms for edge work. This split is intentional and must be preserved.

### 1. Edge Features (standalone machining operations)

Generators (`generators/loop/chamfer.py`, `generators/area/raised_panel.py`) produce items with `feature.type == "bevel"` or `feature.type == "chamfer"`. The adapter converts these to `RemovalIntent` with `EdgeFeatureSpec` (a `BevelSpec | ChamferSpec` union on `RemovalIntent.edge_feature`). These are **standalone machining operations** — boundary-following V-bit passes with angled depth.

| Layer | Location |
|-------|----------|
| IR type | `ir/removal_intent.py` — `EdgeFeatureSpec = BevelSpec \| ChamferSpec` |
| Adapter | `adapters/ast_to_removal.py` — `_build_edge_feature_intent()` |
| Planner routing | `adapters/removal_to_planner.py` — routes to `edge_features` bucket |
| Planner input | `cam/planner/planner_input.py` — `EdgeFeatureInput` |
| Planner pass | `cam/planner/passes/edge.py` — `plan_edge_feature_passes()` |
| Tool selection | `cam/planner/passes/tools.py` — `pick_tool_for_edge()` |
| Validation | `validation/removal_checks.py` — `check_edge_feature()` |

**Dispatch path:**
```
RemovalIntent.edge_feature (BevelSpec | ChamferSpec)
  → _classify_feature() → "edge_features"
  → PlannerInput.edge_features (EdgeFeatureInput objects)
  → plan_edge_feature_passes() → V-bit toolpath in edge-*.nc
```

### 2. Edge Treatment Constraints (per-feature modifiers)

The PML `Edge` node attaches to shapes (pockets, profiles) as a child. It flows through resolution into `Constraints.edge_treatment` on the parent feature's `RemovalIntent`. These are **modifiers to existing operations** — they change how a pocket or profile is machined.

| Layer | Location |
|-------|----------|
| PML syntax | `pml/yaml_parser.py` — `Edge` node with `treatment`, `radius`, `distance`, `rough_allowance`, `finish_allowance` |
| AST node | `layout_ast/compositional.py` — `Edge` dataclass |
| Resolution | `resolution/layout_resolver.py` — extracts `Edge` → `Item.geometry.data["edge_treatment"]` |
| Adapter | `adapters/hints_to_removal.py` → `RemovalIntent.constraints.edge_treatment` |
| IR type | `ir/removal_intent.py` — `EdgeTreatment` on `Constraints` |
| Planner (allowance) | `cam/planner/passes/pocket.py`, `cam/planner/passes/__init__.py` — rough/finish splitting |

**Dispatch path (allowance):**
```
Constraints.edge_treatment (type: "allowance")
  → FeatureInput.edge_treatment
  → Pocket: rough raster + rough profile + finish profile (separate .nc)
  → Profile: rough offset + finish offset (separate .nc)
```

---

## Edge Types

### Edge features (on RemovalIntent.edge_feature)

| Type | Spec | Description |
|------|------|-------------|
| bevel | `BevelSpec(width_mm, angle_deg, inner_depth_mm)` | Angled cut on panel edge |
| chamfer | `ChamferSpec(width_mm, angle_deg)` | Angled cut on panel edge |

### Edge treatments (on Constraints.edge_treatment)

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

## V-bit Geometry

For a V-bit with included angle `V` cutting a feature of width `W` at face angle `A`:

| Parameter | Formula |
|-----------|---------|
| Half-angle of bit | `α = V / 2` |
| Cut depth from surface | `d = W × tan(A)` |
| Effective cutting radius | `r_eff = d × tan(α)` |
| Toolpath offset from boundary | `r_eff` (positive for outside, negative for inside) |

Implemented in `cam/planner/passes/edge.py`: `vbit_cut_depth()` and `vbit_effective_radius()`.

---

## Validation

`check_edge_feature()` in `validation/removal_checks.py` validates:

| Check | Severity | Condition |
|-------|----------|-----------|
| Positive width | Error | `width_mm <= 0` |
| Valid angle range | Warning | `angle_deg <= 0` or `angle_deg >= 90` |
| Non-negative inner depth (bevel) | Error | `inner_depth_mm < 0` |
| Depth within sheet (bevel) | Error | `inner_depth_mm > sheet_thickness_mm` |
| Cut depth within sheet (chamfer) | Error | Computed cut depth > sheet_thickness_mm |
| V-bit availability | Warning | No V-bit with matching included angle |
| Tool clearance | Warning | Edge width > half the feature size |

---

## Resolution Behavior

1. Edge nodes extracted from shape children during resolution
2. Edge treatment stored in Item geometry data as `edge_treatment` dict
3. Edge nodes NOT emitted as separate items (metadata only)

---

## Implementation Status

| Capability | Status |
|------------|--------|
| Edge feature (bevel/chamfer) V-bit toolpath | Honored |
| Edge treatment allowance (rough/finish splitting) | Honored |
| Edge treatment fillet | Not implemented |
| Edge feature validation | Honored |

---

## Files

| File | Purpose |
|------|---------|
| `layout_ast/compositional.py` | Edge node definition |
| `ir/removal_intent.py` | `BevelSpec`, `ChamferSpec`, `EdgeFeatureSpec`, `EdgeTreatment` |
| `pml/yaml_parser.py` | Edge parsing |
| `resolution/layout_resolver.py` | Edge extraction logic |
| `adapters/ast_to_removal.py` | AST → RemovalIntent with edge_feature |
| `adapters/hints_to_removal.py` | Item → RemovalIntent with edge treatment |
| `adapters/removal_to_planner.py` | Routes edge features to planner |
| `cam/planner/planner_input.py` | `EdgeFeatureInput` dataclass |
| `cam/planner/passes/edge.py` | V-bit toolpath generation |
| `cam/planner/passes/tools.py` | `pick_tool_for_edge()` |
| `cam/planner/capabilities.py` | Capability audit |
| `validation/removal_checks.py` | `check_edge_feature()` validation |

---

## Adding New Edge Feature Types

To add a new edge feature type (e.g. `roundover`):

1. Define `RoundoverSpec` in `ir/removal_intent.py`
2. Add to union: `EdgeFeatureSpec = BevelSpec | ChamferSpec | RoundoverSpec`
3. Add generator in `generators/loop/roundover.py`
4. Add adapter branch in `adapters/ast_to_removal.py`
5. Add validation branch in `validation/removal_checks.py`
6. Add planner handler in `cam/planner/passes/edge.py`
