---
description: Step-by-step patterns for extending the system — adding shapes, templates, generators, domain operations, validation invariants, metrics, or planner feature types. Use when adding new capabilities to the mill_ui codebase.
---

# Extension Patterns

## Pattern Index

| Pattern | When to use |
|---------|-------------|
| [Add a New Shape](#pattern-1-add-a-new-shape) | New geometric primitive (Ellipse, Polygon, etc.) |
| [Create a Template](#pattern-2-create-a-template) | Reusable parametric component |
| [Create a Generator](#pattern-3-create-a-generator) | New pattern or operation type |
| [Add a Domain Operation](#pattern-4-add-a-domain-operation) | New algebraic operation on domains |
| [Add a Validation Invariant](#pattern-5-add-a-validation-invariant) | New structural check for CAM artifacts |
| [Add a Metric](#pattern-6-add-a-metric) | New measurement from CAM artifacts |
| [Add a Planner Feature Type](#pattern-7-add-a-planner-feature-type) | New machining operation the planner must handle |

---

## Pattern 1: Add a New Shape

**When:** New geometric primitive not currently in the system.

**Steps:**
1. AST already supports arbitrary shapes via `Item.type` field (no change needed)
2. Add bounds calculation in `adapters/hints_to_removal.py`
3. Add tests

**Files to modify:**
- `adapters/hints_to_removal.py` — extend `_geometry_to_bounds()` and `_item_geometry_to_bounds()`

**Test location:** `tests/test_removal_intent_model.py`

**Example:** Adding Ellipse bounds calculation

```python
def _item_geometry_to_bounds(item_type, geometry_data, cx, cy):
    if item_type == "Ellipse":
        rx = geometry_data["rx_mm"]
        ry = geometry_data["ry_mm"]
        return Bounds2D(
            x_min=cx - rx, x_max=cx + rx,
            y_min=cy - ry, y_max=cy + ry
        )
```

---

## Pattern 2: Create a Template

**When:** Reusable parametric component (cabinet door, mounting plate, etc.).

**Steps:**
1. Create class in `templates/`
2. Implement `expand_to_ast(params, sheet_thickness_mm) -> LayoutAST`
3. Register in `templates/__init__.py`
4. Add tests

**Files to modify:**
- `templates/new_template.py` (create)
- `templates/__init__.py` (register)

**Test location:** `tests/test_templates.py` or add to existing test module

---

## Pattern 3: Create a Generator

**When:** New pattern or operation type (spiral, zigzag, circle grid, etc.).

**Steps:**
1. Create parameter dataclass in `generators/base.py`
2. Implement generator function in `generators/area/` or `generators/loop/`
3. Export from `generators/__init__.py`
4. Add tests

**Files to modify:**
- `generators/base.py` (parameter class)
- `generators/area/new_generator.py` or `generators/loop/new_generator.py` (create)
- `generators/__init__.py` (export)

**Test location:** `tests/test_generators.py`

---

## Pattern 4: Add a Domain Operation

**When:** New algebraic operation on domains (union, convex hull, etc.).

**Steps:**
1. Add method to `Domain` class in `domains/domain.py`
2. Use Shapely for underlying geometry operation
3. Return `MultiDomain` for consistency
4. Add tests

**Files to modify:**
- `domains/domain.py`

**Test location:** `tests/test_domains.py`

---

## Pattern 5: Add a Validation Invariant

**When:** New structural check for CAM artifacts (safety check, quality rule, etc.).

**Steps:**
1. Add invariant ID and check function in `validation/invariants/*_invariants.py`
2. Add to `*_INVARIANT_IDS` list
3. Call from `check_*_invariants()` function
4. Add tests

**Files to modify:**
- `validation/invariants/gcode_invariants.py` (or svg variant)

**Test location:** `tests/test_*_invariants.py`

---

## Pattern 6: Add a Metric

**When:** New measurement from CAM artifacts for regression testing.

**Steps:**
1. Add field to `*Metrics` dataclass in `validation/metrics/*_metrics.py`
2. Extract value in `extract_*_metrics()` function
3. Add tests

**Files to modify:**
- `validation/metrics/gcode_metrics.py` (or svg variant)

**Test location:** `tests/test_*_metrics.py`

---

## Pattern 7: Add a Planner Feature Type

**When:** New machining operation that flows through the full pipeline: RemovalIntent → PlannerInput → planner pass → G-code.

This pattern covers the planner side. If the feature also needs PML syntax, AST nodes, and generators, combine this with Pattern 3 and the PML-First checklist in CLAUDE.md.

**Steps:**

1. Define typed input dataclass in `cam/planner/planner_input.py`
2. Add field to `PlannerInput` for the new feature bucket
3. Route from `RemovalIntent` in `adapters/removal_to_planner.py`
4. Implement pass function in `cam/planner/passes/`
5. Add tool selection in `cam/planner/passes/tools.py` if new tool type needed
6. Wire dispatch in `plan_passes()` in `cam/planner/passes/__init__.py`
7. Update `PLANNER_CAPABILITIES` in `cam/planner/capabilities.py`
8. Update support matrix in `docs/invariants/planner.md`
9. Add IR-level tests (invariant PL-4: test at IR, not CAM)

**Files to modify:**

| File | Change |
|------|--------|
| `cam/planner/planner_input.py` | New input dataclass, new field on `PlannerInput` |
| `adapters/removal_to_planner.py` | Extract from `RemovalIntent`, populate new bucket |
| `cam/planner/passes/new_pass.py` | **Create** — pass function |
| `cam/planner/passes/tools.py` | Tool selection for new operation (if needed) |
| `cam/planner/passes/__init__.py` | Call new pass from `plan_passes()` |
| `cam/planner/capabilities.py` | Update `PLANNER_CAPABILITIES` status |
| `docs/invariants/planner.md` | Update support matrix table |

**Test location:** `tests/test_planner_passes.py` or new test module

**Constraints:**

- Planner passes receive typed frozen dataclasses, not untyped dicts (invariant PC-3)
- Unsupported constraints must not silently pass — warn or error (invariant PC-1)
- Every pipeline run audits constraints and emits a summary (invariant PC-2)
- All Z values respect safe_z for rapids (invariant GC-1)
- Single plunge must not exceed max_stepdown (invariant GC-4)
- All XY coordinates within sheet + margin (invariant GC-8)

**Key conventions from existing passes:**

- Pass functions take a tuple of typed inputs + `accumulator` + `tool_db`
- Pass functions return `None` — they append moves to the accumulator
- `accumulator.get_record(operation, tool)` groups moves by operation+tool into separate `.nc` files
- Tool selection happens per-feature inside the pass, not before
- Depth stepping uses `stepdown_for_tool()` from `tools.py`
- Stepover uses `stepover_for_tool()` from `tools.py`
