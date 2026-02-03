# System Invariants

**Status:** Canonical Reference

Load this document before modifying core system behavior.

---

## Global Axioms

These invariants affect everything. Violating any one breaks the system.

| ID | Invariant | Rule |
|----|-----------|------|
| CS-1 | ALL_MILLIMETERS | All dimensions use millimeters. No unit conversions. |
| CS-7 | Z_POSITIVE_AWAY | Z positive away from material, negative into material. |
| DS-1 | FROZEN_DATACLASSES | All core dataclasses are frozen (immutable). |
| DS-2 | USE_REPLACE | Use `replace()` to modify frozen dataclasses, never mutate. |
| PL-1 | PIPELINE_ORDER | PML/JSON → LayoutAST → RemovalIntent IR → CAM Planner → G-code |
| PL-2 | IR_LAYER_REQUIRED | All AST-to-CAM conversion MUST pass through RemovalIntent IR layer. |
| PL-5 | DETERMINISTIC | Pipeline is deterministic. Same input = same output. |

---

## Regression Traps

These invariants block common "improvements" that break the system. Do NOT refactor these patterns.

| ID | Invariant | Why It's a Trap |
|----|-----------|-----------------|
| DS-8 | NO_SHAPE_CLASSES | LLMs add type hierarchies; shape identity lives in Item.type + Geometry.data |
| PL-2 | IR_LAYER_REQUIRED | LLMs shortcut pipelines to "simplify"; IR is the validation checkpoint |
| PL-3 | SEMANTIC_NOT_SYNTAX | LLMs preserve formatting; only AST equality matters |
| GN-2 | NO_DOMAIN_MUTATION | LLMs mutate for "efficiency"; generators must be pure |
| DS-2 | USE_REPLACE | LLMs forget frozen semantics; mutation corrupts shared state |
| DS-9 | PARAMS_IN_GEOMETRY | LLMs create parameter classes; all shape params live in Geometry.data dict |
| DM-10 | OPERATIONS_RETURN_MULTIDOMAIN | LLMs return single Domain; algebraic ops always return MultiDomain |

**Policy:** If a change "needs" to violate one of these, the invariant must be amended explicitly first—not worked around locally.

---

## Subsystem Invariant Files

Before modifying a subsystem, read its invariant file.

| Subsystem | Invariant File | Applies To |
|-----------|----------------|------------|
| Coordinates | [coordinates.md](coordinates.md) | All geometry, all dimensions |
| Data Structures | [data_structures.md](data_structures.md) | Dataclasses, tuples, dicts |
| Pipeline | [pipeline.md](pipeline.md) | AST, IR, CAM layers |
| Planner | [planner.md](planner.md) | RemovalIntent → Planner adapter, constraint enforcement |
| Bounds/Geometry | [bounds_geometry.md](bounds_geometry.md) | Bounds validation, shapes |
| Domains | [domains.md](domains.md) | Domain algebra, boundaries |
| Generators | [generators.md](generators.md) | Pattern generators |
| Assembly | [assembly.md](assembly.md) | Joinery, panels, interfaces |
| PML | [pml.md](pml.md) | Parser, syntax |
| Validation | [validation.md](validation.md) | Removal checks |
| G-Code | [gcode.md](gcode.md) | Machine output |
| Nesting | [nesting.md](nesting.md) | Bin packing |
| Defaults | [defaults.md](defaults.md) | Default values reference |

---

## Core Principles (Quick Reference)

### Always Go Through RemovalIntent IR

**Wrong:**
```python
hints = convert_ast_to_hints_directly(ast)
```

**Correct:**
```python
intents = ast_to_removal_intents(ast)
hints = removal_intents_to_hints(intents)
```

### Don't Mutate Frozen Dataclasses

**Wrong:**
```python
item.geometry.data["w_mm"] = 100
```

**Correct:**
```python
new_item = replace(item, geometry=Geometry(data={**item.geometry.data, "w_mm": 100}))
```

### Semantic Equivalence, Not Syntax Preservation

**Wrong:**
```python
assert format_pml(parse_pml(pml_input)) == pml_input
```

**Correct:**
```python
assert parse_pml(format_pml(ast1)) == ast1
```

---

## Error Philosophy

| Category | Behavior | Use When |
|----------|----------|----------|
| Hard error | Raise exception | Invalid input, constraint violation |
| Soft failure | Return empty + flag | Optional operation, absence acceptable |
| Never allowed | Silent partial output | — |

Error messages MUST include: what failed, what constraint was violated, actual vs expected.

---

## Amendment Process

If a new feature "needs" to violate an invariant:

1. **STOP** — do not work around it locally
2. Determine if the invariant is wrong or the feature design is wrong
3. If invariant needs change: amend the subsystem invariant file explicitly
4. Update this README if it affects global axioms
5. Coordinate code changes with documentation update

**Invariant:** Any change that violates a subsystem invariant must update that invariant file in the same commit.

Invariant violations are design bugs, not implementation bugs.
