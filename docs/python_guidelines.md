# Python Coding Guidelines

**Status:** Standard | **Version:** 1.0 | **Scope:** all Python in QPrime / TenneCNC projects.

Guidelines for writing consistent, correct, and maintainable Python code. Derived from production experience.

---

## Values

These are the stances all rules below are derived from. When you encounter a case the rules don't address, return here.

**Boring is a feature.** The reader's cognitive budget is finite. Code that uses two language features instead of seven, idiomatic patterns instead of clever ones, and explicit names instead of compressed ones is *better* even when it's longer. Default to the most boring construction that works. The test for whether something is appropriately boring: can the next reader understand what this does without leaving the file?

**Failure modes are visible.** Errors don't get swallowed. Invalid states are unrepresentable when possible, validated at construction when not. A reader should answer "what happens when this goes wrong" by looking at the code, not by reading minds. Silent partial output is the worst possible failure mode in any system whose output drives downstream work.

**Determinism is the default.** Same input must produce the same output. No hidden state, no randomness without explicit seeds, no dependence on dict ordering at runtime, no floating-point platform variance baked into outputs. Determinism is what makes golden-file testing meaningful and reproducible builds possible.

**Defensive at boundaries, trusting inside.** Validate at system boundaries — user input, file parsing, API responses, FFI calls. Trust validated data internally. Re-validating in every internal function produces noise that hides the real defenses. Construction-time validation (§9) is the preferred way to convert "I should check this" into "the type system already did."

**The type checker is your ally.** Make wrong code fail before it runs. Type hints on every public signature. Frozen dataclasses for data structures. Exhaustive union dispatch with a final `raise TypeError`. `Enum` for closed sets, `Literal` for inline constraints. `__post_init__` for construction-time validation. `mypy --strict` so the checker actually catches what the annotations promise. Each tool moves errors from runtime to authoring time; the value is to reach for them habitually, not after a bug demands them.

---

## 1. Immutability by Default

### Frozen Dataclasses

All core data structures should be frozen dataclasses. Immutability prevents an entire class of bugs where shared state is accidentally modified.

```python
@dataclass(frozen=True)
class Measurement:
    width_mm: float
    height_mm: float
```

**Modify with `replace()`, never mutation:**

```python
# Wrong
item.width_mm = 100

# Right
new_item = replace(item, width_mm=100)
```

### Nested Structures

Frozen dataclasses only enforce shallow immutability. Nested dicts and lists remain technically mutable. Treat them as immutable anyway — always create new collections instead of modifying in place.

```python
# Wrong
item.metadata["processed"] = True

# Right
new_item = replace(item, metadata={**item.metadata, "processed": True})
```

### Tuple Collections

Use tuples instead of lists for collections that represent structural data. Tuples signal immutability and prevent accidental append/remove/sort operations.

```python
@dataclass(frozen=True)
class Layout:
    items: tuple[Item, ...]        # not list[Item]
    boundaries: tuple[Point, ...]  # not list[Point]
```

### Field Ordering

Dataclass fields follow a consistent order. This makes constructors predictable and avoids the `non-default argument follows default argument` error.

1. **Required fields** (no default) — the essential identity of the object
2. **Optional typed fields** (`field: Type | None = None`) — present or absent
3. **Factory-default fields** (`field(default_factory=...)`) — complex defaults
4. **Scalar defaults** (`field: Type = value`) — simple defaults

```python
@dataclass(frozen=True)
class Feature:
    # 1. Required
    name: str
    width_mm: float

    # 2. Optional
    description: str | None = None

    # 3. Factory defaults
    tags: tuple[str, ...] = field(default_factory=tuple)

    # 4. Scalar defaults
    enabled: bool = True
```

### `with_*()` Helpers

When a frozen dataclass has a common mutation pattern, provide a named helper that wraps `replace()`. Keeps the call site readable and the boilerplate in one place.

```python
def with_tags(self, *new_tags: str) -> Feature:
    return replace(self, tags=self.tags + new_tags)
```

---

## 2. Pipeline Architecture

### Strict Layer Separation

If your system transforms data through multiple stages, keep those stages separate. Each layer has a single responsibility and a well-defined contract with adjacent layers.

```python
# Wrong — mixing layers
def build_and_export(raw_input):
    model = parse(raw_input)
    output = render(model)  # skipped validation
    return model

# Right — each stage is distinct
model = parse(raw_input)
validated = validate(model)
output = render(validated)
```

### Intermediate Representations

Use an explicit intermediate representation (IR) as the validation checkpoint between parsing and output generation. The IR describes *what* to do, not *how* to do it.

Benefits:
- Validation happens once, in one place
- Multiple backends can consume the same IR
- Tests target the IR (fast, focused) rather than the full pipeline (slow, brittle)

### No Pass-Through of Computed Data

Semantic data structures describe *what*, not *how*. Don't thread implementation details (computed geometry, backend-specific offsets, rendering hints) through semantic layers. Compute those details in the adapter between layers.

```python
# Wrong — threading computed data through semantic layer
@dataclass(frozen=True)
class Feature:
    name: str
    computed_offset: float  # implementation detail leaking into semantic layer

# Right — semantic layer stays clean
@dataclass(frozen=True)
class Feature:
    name: str
    position: float  # semantic, not computed

# Adapter computes implementation details from semantic fields
def feature_to_backend_input(feature: Feature) -> BackendInput:
    offset = compute_offset(feature.position)
    return BackendInput(offset=offset)
```

---

## 3. Function Purity

### Pure Transformations

Functions that transform data should be pure: same input produces same output, no side effects, no mutation of inputs.

```python
# Wrong — mutates input
def process(domain: Domain) -> list[Item]:
    domain.metadata["processed"] = True
    return items

# Right — input is read-only
def process(domain: Domain) -> list[Item]:
    # domain is never modified
    return items
```

### Return Types

Operations that can produce zero, one, or many results should always return a collection, never a single item. This handles all cases uniformly.

```python
# Wrong — special-cases single result
def split(region: Region) -> Region | list[Region]:
    ...

# Right — always returns collection
def split(region: Region) -> list[Region]:
    ...
```

---

## 4. Error Handling

### Error Philosophy

| Category | Behavior | Use When |
|----------|----------|----------|
| Hard error | Raise exception | Invalid input, constraint violation |
| Soft failure | Return empty + flag, or raise `SkipError` (§18) | Optional operation, absence acceptable |
| Never allowed | Silent partial output | — |

`SkipError` (§18) is the canonical mechanism for the soft-failure row when the caller needs to distinguish "expected skip" from "actual bug." Use the empty + flag pattern only when no caller cares about the distinction.

**Exceptions are not control flow.** Don't `try/except` to choose a code path that a conditional would express more clearly. Exceptions signal that something the caller didn't anticipate happened; routine branching uses `if`. The one exception (so to speak) is the expected-failure pattern in §18 — `SkipError` is a deliberate signal that an operation is impossible for valid inputs, and the layer above is expected to catch it. That's the whole rule, not the start of a list.

### Error Message Format

Error messages must include four parts:

1. **What failed** — the class or subsystem
2. **What field** — the specific parameter
3. **What constraint was violated** — the rule that was broken
4. **Actual value** — what was received

```python
# Wrong
raise ValueError("invalid width")

# Right
raise ValueError("SheetConfig: width_mm must be > 0, got -3.5")
```

### No Silent Drops

Unsupported features or unrecognized inputs must error or warn — never silently pass. Silent partial output is the hardest class of bug to diagnose.

```python
# Wrong — silently ignores unknown constraint
if constraint.type in SUPPORTED:
    apply(constraint)
# (unknown constraints silently skipped)

# Right — explicit about what's not supported
if constraint.type not in SUPPORTED:
    warnings.warn(f"Constraint {constraint.type} not implemented, skipping")
```

---

## 5. Data Structure Design

### Flat Type Systems

Prefer flat, data-driven type systems over deep class hierarchies. Use a type tag + data dict instead of a class per variant. This is extensible without new classes and serializes naturally.

```python
# Wrong — class per variant
class Rectangle:
    width: float
    height: float

class Circle:
    radius: float

# Right — flat, data-driven (when variants share the same pipeline)
@dataclass(frozen=True)
class Item:
    type: str                        # "rect", "circle", etc.
    data: dict[str, Any]             # {"width": 100, "height": 50}
```

**When to use typed dataclasses instead:** Typed dataclasses are appropriate in higher-level compositional layers (where the code constructs and pattern-matches on specific shapes) and in rendering/output layers (where shape identity matters for dispatch). The flat approach works best for intermediate representations that need extensibility without code changes.

### Propagation via Params

When parent nodes need to pass context to children, use a params dict rather than special-casing child types.

```python
# Wrong — parent special-cases child types
for child in node.children:
    if isinstance(child, SpecialChild):
        handle_special(child, extra_context)
    else:
        handle_generic(child)

# Right — all children receive the same context
child_params = {**params, "context": extra_context}
for child in node.children:
    handle(child, child_params)
```

Children decide whether to consume the context. Parents don't need to know what children need.

---

## 6. Testing

### Test at the Right Level

Test against your intermediate representation, not the full pipeline output. IR-level tests are fast, focused, and don't depend on output format details.

```python
# Wrong — testing final output format
output = full_pipeline(input)
assert "expected_string" in output

# Right — testing semantic correctness
model = parse_and_validate(input)
assert model.items[0].width == 100
```

Full pipeline tests exist for integration/golden testing. Unit tests should target the layer where the logic lives.

### Test Project Code, Not the Language

Don't write tests for behavior guaranteed by Python itself.

```python
# Wrong — tests Python's @dataclass, not project code
def test_frozen():
    spec = Config(value=10)
    with pytest.raises(FrozenInstanceError):
        spec.value = 20

def test_equality():
    assert Config(value=5) == Config(value=5)

def test_replace():
    modified = replace(Config(value=10), value=20)
    assert modified.value == 20
```

Test construction only when the dataclass has custom `__post_init__` validation. Test behavior the project implements.

### No Duplicate Coverage

Before creating a new test file, check if existing tests already cover the same functions. Two test files testing the same function with the same inputs is a defect, not defense in depth.

### Semantic Equivalence in Round-Trip Tests

When testing serialization round-trips, assert on semantic equivalence, not syntax preservation. Whitespace, key order, and formatting may change.

```python
# Wrong
assert serialize(parse(input_text)) == input_text

# Right
assert parse(serialize(model)) == model
```

### Use the Test Framework

Tests are discovered by pytest (or your project's framework). Don't add:

- `if __name__ == "__main__":` runner blocks
- `print("PASS")` / `print("FAIL")` reporting
- `return True` from test functions
- `sys.path` manipulation

These are dead code in a framework-collected suite and mislead future contributors into copying the pattern.

### Expensive Iteration

If your test suite iterates over a large fixture set (all examples, all configs), limit this to one test per validation concern. If a higher-level test already runs the full set, don't add redundant loops.

---

## 7. Coordinate and Unit Discipline

### Single Unit System

Pick one unit and use it everywhere. No runtime conversions, no mixed units, no unit suffixes on variable names (unless disambiguating at system boundaries).

```python
# Wrong — mixed units
width_inches = 4.0
width_mm = width_inches * 25.4

# Right — one unit throughout
width_mm = 101.6
```

If your system needs to accept external input in different units, convert at the boundary and never again internally.

### Coordinate Spaces

Define and document your coordinate system explicitly. When multiple coordinate spaces exist (local, world, screen), name them and document the transforms between them.

Rules:
- Internal code operates in one canonical coordinate space
- Transforms happen at well-defined boundaries (import, export, rendering)
- Never apply the same transform twice — track what space data is in

```python
# Wrong — margin applied in internal computation AND at export
item_x = margin + offset  # internal
export_x = margin + item_x  # double margin

# Right — internal coordinates are pure; transform at export
item_x = offset  # working-area space
export_x = margin + item_x  # transform once at export
```

---

## 8. Defaults and Configuration

### Document Defaults

Maintain a single reference for all default values, including where they're defined and what they mean. When defaults appear in multiple locations, they must agree.

### Changing Defaults

Changes to defaults affect all consumers that rely on implicit values. When changing a default:
- Check all call sites that rely on the implicit value
- Document the change in the commit message
- Consider whether existing saved configurations need migration

### Policy vs Invariant

Distinguish between values that are policy (can change with care) and values that are invariants (changing breaks the system). Label them explicitly.

---

## 9. Validation

### Validate at Construction

Constraints on data structures should be enforced at construction time, not checked later.

```python
@dataclass(frozen=True)
class Box:
    width: float
    height: float

    def __post_init__(self):
        if self.width <= 0:
            raise ValueError(f"Box: width must be > 0, got {self.width}")
        if self.height <= 0:
            raise ValueError(f"Box: height must be > 0, got {self.height}")
```

### Validate at Boundaries

Validate data at system boundaries: user input, file parsing, API responses, database reads. Internal code can trust validated data — don't re-validate at every function call.

### Wrapper Types for Structural Preconditions

Scalar preconditions (positive width, non-empty string) get enforced by `__post_init__` on the type that owns them. Structural preconditions (convex polygon, sorted range, non-empty buffer, monotonic sequence, oriented loop) deserve a *named wrapper type* — so that downstream functions can require the precondition by signature, not by docstring.

The pattern: a frozen dataclass with `__post_init__` that rejects invalid inputs, plus a `try_from` classmethod that returns `None` instead of raising when the caller wants the soft-failure form.

```python
@dataclass(frozen=True)
class ConvexPolygon:
    points: tuple[Point, ...]

    def __post_init__(self) -> None:
        if not _is_convex(self.points):
            raise ValueError(f"ConvexPolygon: points are not convex, got {len(self.points)} vertices")

    @classmethod
    def try_from(cls, points: tuple[Point, ...]) -> ConvexPolygon | None:
        try:
            return cls(points)
        except ValueError:
            return None


def inset(poly: ConvexPolygon, offset: float) -> Polygon:
    # signature proves the precondition; no defensive check needed inside
    ...
```

Two things this buys you:
1. The signature `inset(poly: ConvexPolygon, ...)` *proves* the precondition. A non-convex polygon cannot reach `inset` without going through the wrapper's check.
2. The check happens *once*, at the boundary, not inside every algorithm that wants to assume the precondition.

Use this pattern for: closed paths, non-self-intersecting curves, monotonic sequences, oriented loops with known winding, sorted ranges, non-empty containers, calibrated values, validated identifiers.

When *not* to wrap: if the precondition is scalar and the type already owns it (e.g., `Box.width > 0` belongs on `Box`, not on a separate `PositiveWidth` wrapper). Wrap when the precondition is structural and the wrapped value is otherwise a generic collection or primitive that other code might pass unwrapped.

### Constraint Auditing

When your system processes constraints or configuration, emit an audit summary showing what was honored, what was ignored, and what isn't implemented yet. This makes "it silently didn't work" impossible.

---

## 10. Code Style

### Self-Documenting Code

Write code that communicates intent through naming, structure, and type signatures. Comments should be rare — reserved for explaining *why*, never *what*. If code needs a comment to explain what it does, rename things until it doesn't.

### No Dead Code

Don't leave commented-out code, unused imports, backward-compatibility shims for removed features, or `# removed` markers. If something is unused, delete it. Version control remembers.

### Named Constants

All magic numbers and layout values should be named module-level constants. Inline literals make code harder to maintain and produce inconsistencies when the same value appears in multiple places.

```python
# Wrong
if margin < 10.0:
    ...

# Right
MIN_MARGIN_MM = 10.0
if margin < MIN_MARGIN_MM:
    ...
```

### Minimal Changes

Only change what's directly needed. A bug fix doesn't need surrounding code cleaned up. A feature doesn't need extra configurability. Don't add docstrings, comments, or type annotations to code you didn't write or change.

---

## 11. Output and Serialization

### Deterministic Output

Same input must produce byte-identical output. This enables golden file testing, reproducible builds, and meaningful diffs.

### Single Conversion Path

For any given input→output transformation, maintain exactly one code path. Multiple paths for the same conversion inevitably diverge and produce inconsistent results.

### Valid Output

Output must always be valid according to its format specification. Malformed output is a bug, not a "the consumer should handle it" situation.

---

## 12. Dependency Direction

### Imports Flow Downward

Lower layers must not import from higher layers. If your validation layer imports from your renderer, or your data model imports from your CLI, the dependency is inverted.

```
Input/CLI  →  Parser  →  IR/Model  →  Validation  →  Backend/Output
   ↓            ↓           ↓             ↓               ↓
 (each layer may import from layers to its right, never to its left)
```

### Enforcing Direction

A practical test: if you delete a higher-level module, lower-level modules should still import cleanly. If removing your CLI breaks your data model, you have a circular dependency.

### Adapter Pattern

When a higher layer's types are needed by a lower layer, introduce an adapter at the boundary rather than pulling the higher layer's imports downward.

```python
# Wrong — model imports from renderer
from renderer.types import RenderHint

@dataclass(frozen=True)
class Feature:
    render_hint: RenderHint  # model depends on renderer

# Right — adapter converts at the boundary
# model.py
@dataclass(frozen=True)
class Feature:
    style: str  # generic, no renderer dependency

# adapter.py
from model import Feature
from renderer.types import RenderHint

def feature_to_render_hint(feature: Feature) -> RenderHint:
    return STYLE_MAP[feature.style]
```

---

## 13. Enums vs String Literals

### Closed Sets Use Enums

When the set of valid values is known and fixed, use an Enum. Enums catch typos at import time, enable IDE autocomplete, and make the valid set discoverable.

```python
# Wrong — stringly typed
def set_mode(mode: str):
    if mode == "fast":  # typo "fats" would silently fail
        ...

# Right — closed set
class Mode(Enum):
    FAST = auto()
    SAFE = auto()
    DRY_RUN = auto()

def set_mode(mode: Mode):
    ...
```

### Open Sets Use Strings

When the set of values is extensible without code changes (shape types in a flat IR, plugin names, user-defined tags), strings are appropriate. The extensibility is the point — new values shouldn't require new code.

### The Decision Rule

| Question | Answer | Use |
|----------|--------|-----|
| Can a new value be added without changing Python code? | Yes | `str` |
| Adding a new value requires a new code path? | Yes | `Enum` |
| Is the set defined by external data (config, schema)? | Yes | `str` |
| Is the set defined by the program's logic? | Yes | `Enum` |

---

## 14. Union Types and Exhaustiveness

### Explicit Unions for Variant Types

When a value can be one of several concrete types, define the union explicitly.

```python
FaceFeature = DrillHole | SquareMortise | CarvedDesign | GeometricPattern
```

### Handle Every Variant

Match/if-else chains over union types must handle every variant. Adding a new variant to the union should cause visible failures, not silent fallthrough.

```python
def process(feature: FaceFeature) -> Output:
    if isinstance(feature, DrillHole):
        return process_hole(feature)
    elif isinstance(feature, SquareMortise):
        return process_mortise(feature)
    elif isinstance(feature, CarvedDesign):
        return process_carving(feature)
    elif isinstance(feature, GeometricPattern):
        return process_pattern(feature)
    else:
        raise TypeError(f"Unhandled feature type: {type(feature).__name__}")
```

### The Else Clause

Always include a final `else` that raises `TypeError` with the unexpected type name. This turns silent bugs into immediate, diagnosable failures when a new variant is added.

For `match` statements, use a wildcard case with the same pattern:

```python
match feature:
    case DrillHole():
        ...
    case SquareMortise():
        ...
    case _:
        raise TypeError(f"Unhandled feature type: {type(feature).__name__}")
```

---

## 15. Logging and Diagnostics

### print() Is for CLI Output, Not Library Code

`print()` belongs in CLI entry points (`cli/`, `main()`, `if __name__ == "__main__":` blocks) and one-off scripts. It does not belong in library code, framework code, or anything imported by other modules. A function imported by other modules has no business deciding whether to write to stdout — that's the caller's job.

The failure this rule prevents: a `print()` snuck into a deep helper for debugging, never removed, now spamming stdout every time the pipeline runs.

If you need runtime diagnostics from library code, use the `logging` module.

```python
# Wrong — print in production code
def process(items):
    print(f"Processing {len(items)} items")
    for item in items:
        print(f"  item: {item.name}")
    return results

# Right — structured logging
import logging
logger = logging.getLogger(__name__)

def process(items):
    logger.info("Processing %d items", len(items))
    for item in items:
        logger.debug("Processing item: %s", item.name)
    return results
```

### Level Discipline

| Level | Use When |
|-------|----------|
| `DEBUG` | Internal state useful during development (variable values, branch taken) |
| `INFO` | High-level progress milestones ("Processing 47 items", "Export complete") |
| `WARNING` | Something unexpected but recoverable (unsupported constraint skipped, fallback used) |
| `ERROR` | Something failed but the program continues (one item in a batch failed) |
| `CRITICAL` | The program cannot continue |

Don't use `WARNING` for expected situations. Don't use `INFO` for per-item detail that floods the output. Match the level to the audience: `INFO` is for operators, `DEBUG` is for developers.

---

## 16. Exception Types

### Standard Exception Hierarchy

Use Python's built-in exceptions consistently:

| Exception | Use When |
|-----------|----------|
| `ValueError` | Value is the right type but violates a constraint (negative width, empty string, out of range) |
| `TypeError` | Value is the wrong type entirely (passed a string where an int was expected, unhandled union variant) |
| `KeyError` | Required key missing from a dict or mapping |
| `RuntimeError` | A state that "shouldn't happen" was reached (invariant violation at runtime, impossible branch) |
| `NotImplementedError` | Method exists in interface but this subclass hasn't implemented it yet |
| `FileNotFoundError` | Expected file/path doesn't exist |

### Custom Exceptions

Create custom exceptions when callers need to distinguish your errors from generic ones for recovery purposes.

```python
class ValidationError(ValueError):
    """A constraint check failed during validation."""

class PipelineError(RuntimeError):
    """An invariant was violated during pipeline execution."""
```

Don't create custom exceptions just for naming. If no caller will ever `except YourCustomError`, it doesn't need to exist — use the standard type.

### Exception Granularity

One custom base exception per subsystem is usually enough. Don't create a unique exception class for every possible error — that's a class hierarchy problem in disguise.

```python
# Wrong — exception class explosion
class WidthTooSmallError(ValidationError): ...
class HeightTooSmallError(ValidationError): ...
class DepthNegativeError(ValidationError): ...

# Right — one exception, descriptive message
raise ValidationError("Box: width must be > 0, got -3.5")
```

The error message carries the specifics. The exception type carries the category.

---

## 17. Error Semantics by Layer

### Each Layer Has Its Own Failure Mode

Not every layer should handle errors the same way. Define the failure behavior per layer and stick to it.

| Layer | On Failure | Mechanism |
|-------|-----------|-----------|
| Parser | Fail hard | Raise a parse error; malformed input is not recoverable |
| Resolver / Builder | Skip item | Catch expected-failure exceptions; continue with remaining items |
| Adapters | Warn + skip | Catch `ValueError` around each item; log warning, collect into warnings list, continue |
| Core engine / Planner | Warn + skip | Log to structured accumulator; skip individual item, continue job |
| Pipeline orchestrator | Collect + gate | Accumulate errors/warnings from all layers; halt on safety-critical failures |

The principle: failures become less fatal as you move outward. The parser is strict. The pipeline orchestrator is lenient with individual items but strict about safety constraints.

### Per-Item Isolation

In any loop that processes a collection, wrap each item in `try/except`. One bad item should never kill the batch.

```python
# Wrong — one bad item kills everything
results = []
for item in items:
    results.append(process(item))

# Right — per-item isolation
results = []
warnings = []
for item in items:
    try:
        results.append(process(item))
    except ValueError as e:
        warnings.append(f"Skipped {item.id}: {e}")
```

### Structured Warning Collection

When an item is skipped, emit both:
1. A log message (`logger.warning(...)`) for developer diagnostics
2. A structured warning (`warnings.append(msg)`) for the pipeline result

If the skip affects final output, it must reach the structured warnings — pure logging is only for internal diagnostics that don't affect correctness.

Warning messages always include: item identity, the specific problem, and the action taken ("— skipped").

---

## 18. Expected-Failure Exceptions

### The Skip Protocol

Some failures are expected and normal — not bugs. A region too small to machine, a constraint that can't be satisfied, an optional operation with no work to do. These need a dedicated exception type so callers can distinguish "expected skip" from "actual bug."

```python
class SkipError(ValueError):
    """Operation impossible for this input — expected condition, not a bug."""
```

### The Full Pattern

```python
def generate(domain, params, *, allow_empty=False):
    if domain.area < min_area(params):
        if allow_empty:
            return []
        raise SkipError(f"Domain area {domain.area} below minimum {min_area(params)}")
    return do_work(domain, params)
```

Callers choose their tolerance:
- **Strict mode** (`allow_empty=False`): raises on skip — caller must handle
- **Lenient mode** (`allow_empty=True`): returns empty — caller gets no output but no exception

The layer above always catches `SkipError` and continues. It never propagates past the immediate caller.

---

## 19. Dispatch Patterns

### Registry Dict Over If/Elif

When dispatching on a type tag or feature name, prefer a registry dict over long if/elif chains. Registries are declarative, extensible, and self-documenting.

```python
# Wrong — long if/elif chain
def handle(feature_type, data):
    if feature_type == "pocket":
        return handle_pocket(data)
    elif feature_type == "profile":
        return handle_profile(data)
    elif feature_type == "hole":
        return handle_hole(data)
    # grows forever...

# Right — registry dict
HANDLERS = {
    "pocket": handle_pocket,
    "profile": handle_profile,
    "hole": handle_hole,
}

def handle(feature_type, data):
    handler = HANDLERS.get(feature_type)
    if handler is None:
        raise ValueError(f"Unknown feature type: {feature_type}")
    return handler(data)
```

### Decorator Registration

For large registries, a decorator keeps the handler and its registration co-located:

```python
HANDLERS: dict[str, Callable] = {}

def register(feature_type: str):
    def decorator(fn):
        HANDLERS[feature_type] = fn
        return fn
    return decorator

@register("pocket")
def handle_pocket(data):
    ...
```

### Normalize Before Dispatch

If your type tags come from external input with inconsistent casing, normalize at the dispatch entry point — not inside each handler.

```python
def handle(feature_type: str, data):
    handler = HANDLERS.get(feature_type.lower())
    ...
```

---

## 20. Function Signature Conventions

### Frozen Params Objects

When a function takes more than 3 related parameters, group them into a frozen dataclass. This prevents argument-order bugs, makes the call site self-documenting, and provides a natural place for validation.

```python
# Wrong — too many positional args
def generate(width, height, depth, spacing, offset, angle):
    ...

# Right — params object
@dataclass(frozen=True)
class GridParams:
    width_mm: float
    height_mm: float
    depth_mm: float
    spacing_mm: float
    offset_mm: float = 0.0
    angle_deg: float = 0.0

def generate(domain: Domain, params: GridParams):
    ...
```

### Keyword-Only Arguments

Use `*` to force keyword-only arguments for flags and options that would be ambiguous as positional args.

```python
def generate(domain: Domain, params: GridParams, *, allow_empty: bool = False):
    ...
```

### Max Positional Parameters

A function should take at most 3 positional parameters. Beyond that, use a params object or keyword-only arguments. Long positional signatures invite argument-order bugs that the type checker can't catch.

---

## 21. Naming Vocabulary

### Consistent Verbs at Layer Boundaries

Use the same verb for the same operation across the codebase. When a new contributor sees `parse_`, they should know exactly what kind of operation it is.

| Verb | Meaning | Example |
|------|---------|---------|
| `parse_*` | String/text → structured data | `parse_config`, `parse_dimension` |
| `format_*` | Structured data → string/text | `format_output`, `format_report` |
| `resolve_*` | Simplify structure, expand references | `resolve_layout`, `resolve_template` |
| `*_to_*` | Convert between typed representations | `model_to_dto`, `ast_to_ir` |
| `validate_*` | Check correctness, raise on failure | `validate_config`, `validate_bounds` |
| `build_*` | Construct complex object from parts | `build_pipeline`, `build_tool_db` |
| `load_*` | Read from disk or external source | `load_config`, `load_template` |
| `write_*` | Emit machine/file output | `write_output`, `write_report` |
| `render_*` | Emit visual/display output | `render_diagram`, `render_html` |
| `expand_*` | Parameterized instantiation | `expand_template`, `expand_macro` |

For predicates and constructor-style helpers:

| Pattern | Purpose | Example |
|---------|---------|---------|
| `is_*` / `has_*` | Boolean predicates returning `bool` | `is_convex`, `has_through_cut` |
| `try_from` / `try_*` | Constructor or operation that may fail; returns `T \| None` instead of raising | `ConvexPolygon.try_from`, `try_parse_dimension` |
| `find_*` | Search that may not find; returns `T \| None` | `find_tool`, `find_intersection` |
| `make_*` | Construct a value (factory function) | `make_default_config`, `make_tool_db` |
| `get_*` | Accessor that cannot fail; precondition is the caller's responsibility | `get_bounds`, `get_active_tool` |

The `try_from` idiom pairs with the wrapper-type pattern (§9): the wrapper's `__post_init__` raises, the `try_from` classmethod returns `None`, and callers pick the form that matches their failure semantics.

### Private Helper Prefixes

Private helpers follow the same verb conventions with underscore prefix:

| Pattern | Purpose |
|---------|---------|
| `_handle_*` | Dispatch target for a specific case |
| `_build_*` | Internal construction helper |
| `_validate_*` | Internal validation check |
| `_collect_*` / `_count_*` | Aggregation helpers |
| `_is_*` / `_has_*` | Boolean predicates |

---

## 22. Guard Clauses and Input Normalization

### Guard Clauses at Entry

Functions validate preconditions with early `raise` before doing real work. This keeps the happy path unindented and easy to follow.

```python
# Wrong — nested conditionals
def process(items, config):
    if items:
        if config.is_valid():
            # 3 levels deep before real work starts
            for item in items:
                ...

# Right — guard clauses
def process(items, config):
    if not items:
        return []
    if not config.is_valid():
        raise ValueError(f"Config: must be valid, got {config}")
    for item in items:
        ...
```

### Normalize Before Branching

Canonicalize inputs at function entry — before any validation or dispatch logic. This prevents scattered normalization and missed cases.

```python
def handle_shape(shape_type: str, data: dict):
    shape_type = shape_type.lower().strip()
    # now all branches see normalized input
    handler = HANDLERS.get(shape_type)
    ...
```

Common normalizations:
- `.lower()` / `.strip()` for string tags
- `float()` / `int()` for numeric strings from parsed input
- `None` checks resolved to defaults

---

## 23. Collection Building

### Explicit Loops Over Comprehensions

When building collections with per-item error handling, conditional logic, or multi-step processing, use explicit loops. Comprehensions are for simple transforms.

```python
# Wrong — comprehension with try/except (not possible) or conditional that hides errors
items = [process(x) for x in inputs if can_process(x)]

# Right — explicit loop with error handling
items = []
for x in inputs:
    try:
        items.append(process(x))
    except ValueError as e:
        warnings.append(f"Skipped {x.id}: {e}")
```

Comprehensions are fine for simple, infallible transforms: `names = [item.name for item in items]`.

### Tuple at the Return Boundary

Internal accumulation uses `list` (for `.append()`). Convert to `tuple` at the return boundary when the frozen dataclass field expects it.

```python
def collect_items(source) -> tuple[Item, ...]:
    result = []  # mutable during construction
    for raw in source:
        result.append(Item.from_raw(raw))
    return tuple(result)  # frozen at return
```

### Preserve Input Order

Output order should match input order by default. If you need deduplication, use a dict keyed by identity to preserve first-seen order:

```python
seen = {}
for item in items:
    key = item.identity_key()
    if key not in seen:
        seen[key] = item
unique_items = tuple(seen.values())
```

---

## 24. Serialization Completeness

### Serialize All Non-Private Fields

`to_dict()` methods must serialize all non-private fields. If a field is intentionally omitted, document the omission at the serialization site explaining why. Silent omission is a data-loss bug.

```python
# Wrong — silently drops field
def to_dict(self):
    return {
        "name": self.name,
        "width": self.width,
        # height silently missing
    }

# Right — all fields present
def to_dict(self):
    return {
        "name": self.name,
        "width": self.width,
        "height": self.height,
    }
```

### Round-Trip Completeness

All fields must survive a `serialize → deserialize → serialize` round-trip. When adding a new field to a data structure, update the serializer, the deserializer, and the round-trip tests. Incomplete coverage silently drops the field.

### Non-Default Emission

Formatters should emit only non-default fields for brevity. Parsers must accept both the full and abbreviated forms. The formatter emits the simplest valid representation; the parser accepts the most permissive.

---

## 25. Nullable Numeric Parsing

### The `or` Trap

Never use `or` for nullable numeric fields where `0` is a valid value. Python's `or` treats `0`, `0.0`, and `""` as falsy, silently falling through to the alternative.

```python
# Wrong — silently replaces 0 with fallback
width = data.get("width") or default_width
# If data["width"] is 0, width becomes default_width

# Right — explicit None check
width = data.get("width")
if width is None:
    width = default_width
```

This applies to all parsed input (YAML, JSON, CLI args, database reads) where numeric fields may legitimately be zero. The same trap applies to string fields where empty string `""` is valid — use the same `is None` pattern.

---

## 26. Type System Conventions

### Six Type Mechanisms

Python offers several ways to constrain types. Each has a specific use case — don't reach for the wrong one.

| Mechanism | When to Use | Example |
|-----------|------------|---------|
| `Enum` with `auto()` | Internal identity types (value doesn't matter) | `Role.ADMIN`, `Status.ACTIVE` |
| `Enum` with string values | Serialized or user-facing values | `Mode("fast")`, `Verdict("pass")` |
| `Literal[...]` | Inline field constraints on dataclass fields | `side: Literal["left", "right"]` |
| Constants class | String keys for dict lookup and dispatch | `class FeatureType: POCKET = "pocket"` |
| Pipe union (`A \| B`) | Sum types at module level | `Event = Click \| Hover \| Scroll` |
| `@runtime_checkable Protocol` | Structural subtyping interfaces | `class Handler(Protocol): def handle(self) -> None: ...` |

### Protocol Over ABC

When defining an interface, prefer `@runtime_checkable Protocol` over `ABC`. Protocols use structural subtyping — any class with the right methods satisfies the protocol without inheriting from it. Use ABC only when shared implementation is genuinely needed.

---

## 27. The Amendment Culture

These guidelines are not immutable. But they can't be ignored, either. The process for change:

1. If a guideline blocks your work, **stop**
2. Determine if the guideline is wrong or your approach is wrong
3. If the guideline needs to change, change it explicitly with rationale
4. Never work around a guideline locally — that creates invisible technical debt

---

## Tooling Commitments

A standard that doesn't say what the build refuses leaves the most consequential decisions implicit. These are the QPrime defaults.

**Enforcement is required.** Every project has an automated gate that, at minimum, runs the linter, the type checker, the formatter, and the test suite. A change that doesn't pass the gate doesn't merge.

The QPrime mechanism is **pre-commit hooks** — checks colocate with the code, which lets both the human and AI collaborators run, diagnose, and fix them in a tight loop. CI is appropriate when a project grows beyond solo work; until then it's overhead without payoff.

**Linting:** `ruff` with project-level configuration in `pyproject.toml`. The QPrime baseline enables `E`, `F`, `W` (pycodestyle/pyflakes), `I` (isort), `B` (bugbear), `UP` (pyupgrade), and `SIM` (simplify). Disabling a specific rule requires a comment explaining why, in either `pyproject.toml` or a `# noqa: <code>` at the call site.

**Formatting:** `ruff format` with the project-level config. Decided once per project and not relitigated. The QPrime starter is line length 100, double quotes, and the default ruff style otherwise; deviations are project choices.

**Type checking:** `mypy` in strict mode. New projects start strict. Selective relaxations (`# type: ignore[code]` with the specific code, never bare `# type: ignore`) are permitted at boundaries with untyped third-party libraries. Type-check findings block merge.

**Testing:** `pytest`. Tests live in `tests/` parallel to the source tree. Coverage is measured but not gated on a percentage — the standards in §6 cover what to test and what not to test, which is more meaningful than a coverage number.

**Python version:** projects target a specific Python version (3.12+ for new work) stated in `pyproject.toml`. Reaching for a Python 3.13 feature on a 3.12 project is a bug, not a clever optimization.

**What's per-project, not QPrime-level:**
- Specific ruff rule disables beyond the baseline
- Line length (100 is a default, not a mandate)
- Test framework choice (pytest is default; alternatives permitted with reason)
- Build/packaging tool (`uv`, `poetry`, plain `pip` + `pyproject.toml`)
- Dependency management policy (lockfile, version pinning, etc.)

These are listed not because they don't matter, but because they're decisions where reasonable projects differ. The QPrime standard names the dimensions; the project picks the values.

---

## FFI Conventions

The boundary between languages is where each language's conventions disagree most. AI generation defaults to applying each language's local conventions, which produces a seam that doesn't survive the trip. These rules apply identically on both sides of the FFI.

**Names cross unchanged.** A function called `parse_layout` in Python pairs with `parse_layout` in C++. No `parseLayout`, no `_parse_layout_impl` on the C++ side that's only called from Python. The Naming Vocabulary (§21) applies to both languages.

**Validation is the calling side's job.** The caller validates inputs before crossing the boundary. The called side may assert preconditions cheaply but does not re-validate as a defensive measure. This matches the "defensive at boundaries, trusting inside" value: the FFI boundary is the boundary, not every function on the called side.

**Errors translate at the boundary, not in flight.** C++ exceptions become Python exceptions exactly once, at the pybind11 (or equivalent) layer. Python code does not wrap pybind11-translated exceptions in additional layers — the original type and message are preserved. C++ code does not catch exceptions to translate them mid-stack.

**Absence maps to absence.** `Optional[T]` (or `T | None`) ↔ `std::optional<T>`. `None` ↔ `std::nullopt`. NaN does not appear in either direction; empty collections do not signal failure. When a value is genuinely optional, both sides see it as optional.

**Units survive the trip.** If C++ takes millimeters, Python passes millimeters. If C++ takes seconds, Python passes seconds. Conversion happens at the *outer* boundary (user input, file parsing, §7) and never at the FFI seam — converting at the FFI is a category error that produces double-conversion bugs the moment a caller is added.

**Ownership is explicit.** Objects passed across the FFI by value are copied; objects passed by reference are non-owning views with documented lifetime. Python does not pass mutable objects expecting C++ to retain them past the call. C++ does not return raw pointers to Python; ownership transfers via `std::unique_ptr` (which pybind11 wraps) or by-value copy.

**The IR is the contract.** When the two languages share data structures (move IRs, parsed layouts, plan output), there is exactly one schema, defined in one place, and both sides agree on it. A change to the shared schema is a versioned change requiring both sides and the goldens to move together.

---

## What This Convention Deliberately Does Not Require

- **No naming bikeshed.** `snake_case` for functions and variables, `PascalCase` for types, `SCREAMING_SNAKE_CASE` for module-level constants. PEP 8 is the default; don't relitigate it.
- **No docstring quotas.** Docstrings are reserved for public API surface, non-obvious algorithms, and load-bearing assumptions a reader couldn't infer from the code. Don't write docstrings on every internal helper. Don't write docstrings that restate the function signature.
- **No metaclass tricks.** Metaclasses, `__init_subclass__`, dynamic class generation — none of these appear unless the code already has at least two concrete cases that justify the abstraction, and the alternative is genuinely worse. The first instance is a function; the second instance is when you decide whether it's a pattern.
- **No `__getattr__` magic.** Dynamic attribute access for things that could be explicit methods or dictionary lookups makes the code untraceable by IDE and reader. Use it only for genuine proxy/forwarding patterns at module boundaries.
- **No decorator stacks more than two deep.** A decorator can replace a function; two decorators can compose; three or more is a sign that the wrapping is doing work that should be a real function call.
- **No premature `Generic[T]`.** Generic type variables are appropriate when the code genuinely operates on multiple types with the same logic. They are not appropriate when the code has one concrete type and "might" need others — wait until the second type exists.
- **No monkey-patching.** Don't reach into another module's namespace to replace its functions or classes. If you need different behavior, pass it in or wrap it explicitly.
- **No exotic Python.** Walrus operators in obscure positions, structural pattern matching for things that are obviously dict lookups, descriptor protocol for things that are obviously properties — when the boring construction works, use the boring construction.

---

## Adoption

For a new codebase: everything applies immediately.

For an existing codebase: the rules represent a target state, not a flag-day requirement. Work toward them as files are touched. Suggested order:

1. **Tooling first** — turn on the pre-commit gate (ruff, mypy strict, formatter), fix the resulting findings file by file. Mechanical; catches a category of issues before any rule-by-rule work.
2. **Validation at construction** (§9) — frozen dataclasses with `__post_init__` checks. Adds protection at the type level without requiring caller changes.
3. **Error message format and exception types** (§4, §16) — mechanical pass through error sites.
4. **Union exhaustiveness** (§14) — adding the final `else: raise TypeError(...)` is one-line per dispatch site and immediately catches missing variants.
5. **Naming vocabulary** (§21) — done as files are renamed or new functions are added; not worth a flag-day rename pass.
6. **Layer separation, dependency direction** (§2, §12) — the deepest changes; do these as features or refactors create the opportunity.

Trying to adopt all of it at once on a mature codebase produces a wall of findings nobody triages. The discipline is to land each tier deliberately and let the goldens (or your equivalent regression baseline) confirm the changes are refactors.

---

## Why This Convention Exists

Python is a language that lets you write almost anything. That's its strength as a research and prototyping tool, and a liability when the same code is asked to drive production systems. Without explicit discipline, a Python codebase reflects the union of every contributor's habits: mixed mutation patterns, ad-hoc error handling, undocumented coordinate spaces, silently dropped fields in serializers, drifting naming conventions.

This convention is the discipline. It's grounded in real patterns of weakness rather than abstract preferences. The values let the rules generalize beyond their stated cases. The rules let the values be checked at review time. The tooling section makes the build itself enforce what the values say should be enforced.

The test for whether the standard is working: an AI session writing new code under it produces code that looks like the rules without anyone having to invoke them by name.
