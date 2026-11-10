# Testing Invariants

**Applies to:** All test files in `tests/`

---

## Invariants

| ID | Type | Invariant | Description |
|----|------|-----------|-------------|
| TS-1 | HARD | TEST_AT_IR | Write tests against RemovalIntent IR, not full CAM pipeline (see PL-4) |
| TS-2 | HARD | NO_DUPLICATE_COVERAGE | Before adding a test file, verify no existing file tests the same code paths |
| TS-3 | HARD | TEST_PROJECT_CODE | Tests must exercise project logic, not Python builtins |
| TS-4 | HARD | PYTEST_ONLY | Tests are collected by pytest. No hand-rolled runners or print-based reporting |
| TS-5 | STRUCTURAL | TESTS_OWN_INPUTS | Tests never read `docs/recipes/`. Inputs are inline PML or files under `tests/fixtures/` |
| TS-6 | HARD | GOLDENS_ARE_TRACKED | Any file a test reads from disk must be tracked by git. Goldens in gitignored paths make fresh clones fail the test for filesystem reasons, not code reasons. If the test reads it, git tracks it. |

---

## Test at IR Level (TS-1)

Canonical fast path: assert on `RemovalIntent` fields after `ast_to_removal_intents()`.

**Wrong:**
```python
gcode = generate_full_pipeline(ast)
assert "G1 X100" in gcode
```

**Right:**
```python
intents = ast_to_removal_intents(ast)
assert intents[0].bounds == Bounds2D(x_min=50, x_max=150, ...)
```

**When full pipeline is appropriate:** Tests of the artifact checkers (SVG and G-code metrics and invariants, the validation runner, `validate_cam`) and CLI tests. They run the pipeline on a small inline PML to get real artifacts to check.

---

## No Duplicate Coverage (TS-2)

Before creating a new test file, check whether existing tests already cover the same functions. Two test files testing the same `strategy.apply()` with the same panel dimensions is a defect, not defense in depth.

**Check:**
```bash
grep -r "from assembly.joinery import" tests/
```

If another file already imports and tests the same module, add your tests there or confirm distinct coverage before creating a new file.

---

## Test Project Code, Not Python (TS-3)

Do not write tests for behavior guaranteed by Python itself.

**Wrong:**
```python
def test_frozen(self):
    spec = BevelSpec(width_mm=10.0, angle_deg=45.0)
    with pytest.raises(FrozenInstanceError):
        spec.width_mm = 20.0

def test_equality(self):
    a = BevelSpec(width_mm=5.0, angle_deg=30.0)
    b = BevelSpec(width_mm=5.0, angle_deg=30.0)
    assert a == b

def test_replace(self):
    spec = BevelSpec(width_mm=10.0, angle_deg=45.0)
    modified = replace(spec, angle_deg=60.0)
    assert modified.angle_deg == 60.0
```

These test `@dataclass(frozen=True)`, `__eq__`, and `dataclasses.replace()` -- all Python stdlib guarantees. Zero project code is exercised.

**Right:** Test construction only when the dataclass has custom `__post_init__` validation. Test behavior that the project implements.

---

## Pytest Only (TS-4)

Tests are discovered and run by pytest. Do not add:

- `if __name__ == "__main__":` runner blocks
- `print("Running test_foo...")` / `print("  PASS")` statements
- `return True` from test functions
- `sys.path.insert(0, ...)` path manipulation

These are dead code in a pytest-collected suite. They clutter output and mislead future agents into copying the pattern.

---

## Tests Own Their Inputs (TS-5)

Recipes are documentation checked by `python -m cli.recipes`, not test fixtures. A test that reads a recipe breaks when the recipe is renamed or rebuilt, and silently loses coverage when it guards the read with a skip.

A test that needs PML writes it inline, as a module constant in its own file. A test that needs a recipe folder (`validate_recipe`, `cli.mill --recipe`, `validate_cam --recipe`) writes one into `tmp_path`. A test over a corpus of PML files reads it from `tests/fixtures/` (see `tests/fixtures/pml_round_trip/`).

---

## Invariant Types

| Type | Meaning |
|------|---------|
| HARD | Violation wastes CI time or produces false confidence |
| STRUCTURAL | Requires coordinated changes across multiple test files |
