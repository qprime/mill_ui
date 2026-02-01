# Data Structure Invariants

**Applies to:** All dataclasses, tuples, dicts, collections

---

## Invariants

| ID | Type | Invariant | Description |
|----|------|-----------|-------------|
| DS-1 | HARD | FROZEN_DATACLASSES | All core dataclasses are frozen (immutable) |
| DS-2 | HARD | USE_REPLACE | Use `replace()` to modify frozen dataclasses, never mutate |
| DS-3 | HARD | NESTED_DICT_IMMUTABLE | Treat nested dicts as immutable even though technically mutable |
| DS-4 | STRUCTURAL | ITEMS_TUPLE | LayoutAST.items is a tuple (immutable sequence) |
| DS-5 | STRUCTURAL | BOUNDARIES_TUPLE | Domain boundaries are tuples of tuples |
| DS-6 | STRUCTURAL | NOTCHES_TUPLE | PanelSpec.notches is tuple (immutable) |
| DS-7 | STRUCTURAL | DADOS_TUPLE | PanelSpec.dados is tuple (immutable) |
| DS-8 | HARD | NO_SHAPE_CLASSES | No separate Rect/Circle classes; shape identity is Item.type |
| DS-9 | HARD | PARAMS_IN_GEOMETRY | Shape parameters live in Geometry.data dict |

---

## Frozen Dataclass Discipline

**Wrong:**
```python
item.geometry.data["w_mm"] = 100
```

**Correct:**
```python
from dataclasses import replace
new_item = replace(item, geometry=Geometry(data={**item.geometry.data, "w_mm": 100}))
```

**Why:** Frozen dataclasses prevent accidental mutation. Nested dicts remain technically mutable but should be treated as immutable.

---

## Shape Representation

Shapes do NOT have their own classes. Shape identity is determined by `Item.type` and parameters live in `Geometry.data`.

**Wrong:**
```python
class Rectangle:
    width: float
    height: float
```

**Correct:**
```python
Item(type="rect", geometry=Geometry(data={"w_mm": 100, "h_mm": 50}))
```

**Why:** This keeps the type system flat and extensible. New shapes don't require new classes.

---

## Tuple Collections

These collections MUST be tuples (not lists):

| Collection | Location | Why |
|------------|----------|-----|
| `items` | LayoutAST | Immutable sequence of layout items |
| `boundaries` | Domain | Immutable boundary definitions |
| `notches` | PanelSpec | Immutable joinery features |
| `dados` | PanelSpec | Immutable groove features |

---

## Invariant Types

| Type | Meaning |
|------|---------|
| HARD | Violation breaks the system |
| STRUCTURAL | Requires coordinated migration to change |
