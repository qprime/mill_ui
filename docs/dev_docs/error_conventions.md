# Error Message Format Convention

**Status:** Convention (new code) | **As-Of:** 2026-03-29

Guidance for error message formatting. Not a mass migration — existing messages converge as code is touched.

---

## Standard Format

For parameter validation and constraint violations:

```
{ClassName}: {field_name} {constraint}, got {actual_value}
```

Examples:
```
FlatPocketParams: depth_mm must be positive, got -1
LayerSpec: length_mm must be positive, got 0
SheetConfig: thickness_mm must be > 0, got -3.5
```

The message names the source class, identifies the field, states the constraint, and shows the actual value. All four parts are required.

---

## Invariant Violation Format

When an error maps to a documented invariant code (see [docs/invariants/](../invariants/)):

```
{description} ({INVARIANT-CODE} violation)
```

Examples:
```
Butt joints align at position 150mm (BM-9 violation)
Stagger 10mm < minimum 50mm (BM-10 violation)
```

The invariant code makes violations traceable to the documented rule.

---

## When to Use Which

| Situation | Format |
|-----------|--------|
| Dataclass `__post_init__` validation | Standard format |
| Generator/params constraint check | Standard format |
| Documented invariant violated | Invariant violation format |
| Both apply (param check *is* an invariant) | Standard format with invariant code appended |

Combined example:
```
BeamSpec: stagger_mm must be >= 50, got 10 (BM-10 violation)
```

---

## Principles

These align with the [Error Philosophy](../invariants/README.md#error-philosophy) in the invariants README:

1. **What failed** — class or subsystem name
2. **What constraint was violated** — the rule that was broken
3. **Actual vs expected** — what was received vs what was required
4. **Never silent** — no partial output on constraint violation
