# QPrime C++ Coding Convention

**Status:** Standard | **Version:** 3.0 | **Scope:** all C++ in QPrime / TenneCNC projects.
**Companions:** [mechanisms.md](mechanisms.md) · [std/cpp11.md](std/cpp11.md) · [std/cpp17.md](std/cpp17.md) · [std/cpp20.md](std/cpp20.md)

This document exists so that C++ written across every QPrime project reads as though one engineer wrote it. Not merely correct — *designed*. Consistent, readable, and correct by construction rather than by test.

---

## What this document is

This is a **prioritized, tiered, multi-standard, FFI-aware profile of the [C++ Core Guidelines](https://isocpp.github.io/CppCoreGuidelines/CppCoreGuidelines)**.

The Core Guidelines are the philosophical basis. They are authoritative, they are written by the people who designed the language, and where they say something we do not repeat it in our own words — we cite it. Every mandatory rule below carries its citation, so no rule here rests on one engineer's taste.

What the Core Guidelines do not provide, and this document does:

| The CG gives | This document adds |
|--------------|-------------------|
| ~500 rules, unordered | Three tiers, so an author knows what is non-negotiable |
| Roughly C++17+ with a GSL dependency | A per-standard mechanism matrix, C++11 through C++23, no GSL |
| Language guidance | FFI conventions, cross-language naming, golden-tested IR |
| Reference material to look up | A document to follow |

Read the [tiers](#the-three-tiers) first. Read a [pattern](#patterns) when you are about to build the thing it describes. Read a [trap](#traps) when the Quick Lookup sends you there. The [mechanism matrix](mechanisms.md) tells you what to write for your project's standard.

**Sibling document:** [python_guidelines.md](../python_guidelines.md) is the matched Python convention. The two are deliberately symmetric: the naming vocabulary, FFI rules, error-message format, and testing discipline are identical on both sides, so names and semantics cross the language boundary unchanged.

---

## Quick Lookup

When you're about to write... go to...

| Situation | Section |
|-----------|---------|
| A new type holding data | [Pattern: value type with invariant](#pattern-value-type-with-invariant) |
| `struct` or `class`? | [Pattern: value type with invariant](#pattern-value-type-with-invariant) |
| A function with several scalar parameters | [Pattern: params struct](#pattern-params-struct) |
| Two parameters of the same type next to each other | [Pattern: params struct](#pattern-params-struct) |
| A function that may fail | [Pattern: failure mechanism](#pattern-failure-mechanism) |
| A function with a structural precondition (convex, sorted, non-empty) | [Pattern: wrapper type for preconditions](#pattern-wrapper-type-for-preconditions) |
| A type that owns a resource | [Pattern: ownership decision](#pattern-ownership-decision) |
| Copy / move / destructor | [Pattern: rule of zero](#pattern-rule-of-zero) |
| A new header | [Pattern: module boundary](#pattern-module-boundary) |
| A helper — member or free function? | [Pattern: free function by default](#pattern-free-function-by-default) |
| A value that never changes | [Pattern: immutability by default](#pattern-immutability-by-default) |
| A long function doing several things | [Pattern: named operation](#pattern-named-operation) |
| Deciding whether something deserves its own type | [Decision: when a thing becomes a type](#decision-when-a-thing-becomes-a-type) |
| Deciding how to pass a parameter | [Decision: how to pass a parameter](#decision-how-to-pass-a-parameter) |
| `std::string kind` field, or `enum` + if/else-if chain | [Trap: stringly-typed dispatch](#trap-stringly-typed-dispatch) |
| NaN or `-1` meaning "no value" | [Trap: sentinel value](#trap-sentinel-value) |
| `std::shared_ptr<T>` as the heap default | [Trap: reflexive shared_ptr](#trap-reflexive-shared_ptr) |
| `std::mutex` member to make a class "thread-safe" | [Trap: cargo-culted mutex](#trap-cargo-culted-mutex) |
| `auto` everywhere | [Trap: auto by default](#trap-auto-by-default) |
| `noexcept` on every function | [Trap: blanket noexcept](#trap-blanket-noexcept) |
| `template<...>` as the first reach | [Trap: premature template](#trap-premature-template) |
| An inheritance hierarchy for variant types | [Trap: inheritance for variation](#trap-inheritance-for-variation) |
| Catching an exception to convert it | [Trap: mid-stack exception translation](#trap-mid-stack-exception-translation) |
| `(void)param;` to silence a warning | [Trap: void-cast unused param](#trap-void-cast-unused-param) |
| A stub returning `{}` | [Trap: empty-stub public function](#trap-empty-stub-public-function) |
| An inline numeric literal in a check | [Trap: magic number](#trap-magic-number) |
| Storing a `span` / `string_view` as a member | [Trap: stored view](#trap-stored-view) |
| Two functions sharing most of their bodies | [Trap: parallel near-duplicates](#trap-parallel-near-duplicates) |
| Defensive checks at every call site | [Trap: defensive everywhere](#trap-defensive-everywhere) |
| A pybind11 binding or a schema shared with Python | [FFI Conventions](#ffi-conventions) |
| A real-time loop, audio callback, ISR | [Real-Time Loops](#real-time-loops) |
| A coroutine | [Coroutines](#coroutines) |
| Logging | [Logging](#logging) |
| A test | [Testing](#testing) |
| A name for a new function | [Naming](#naming) |
| Code in a native tree for the first time | [Tooling Commitments](#tooling-commitments) |

---

## The Three Tiers

Rules are tiered by how much latitude an author has. This is the structure the Core Guidelines do not provide, and it is what makes a document followable rather than merely consultable.

| Tier | Meaning |
|------|---------|
| **Tier 1 — Universal Mandatory** | Satisfiable in every supported standard. No escape hatch. If you cannot follow one of these, you have found a design problem, not an exception. |
| **Tier 2 — Mandatory Given the Mechanism** | Absolute where the standard provides the facility. The [mechanism matrix](mechanisms.md) gates applicability, not the author's judgment. |
| **Tier 3 — Strong Default, Named Escapes** | A default plus an enumerated list of when it does not apply. If your case is not on the list, the default holds. |

Tier 1 and Tier 2 rules are not style preferences. A reviewer citing one of them is citing the standard, and the response is to change the code or change the standard — not to argue the instance.

### Tier 1 — Universal Mandatory

| # | Rule | Citation |
|---|------|----------|
| 1 | **Ownership is single and explicit.** Every allocation has one owner, identifiable from its declaration. A raw pointer or reference is always non-owning. | `[CG R.20, R.21, R.3, R.4, R.11]` |
| 2 | **Types with invariants establish them at construction.** A type whose members can vary independently is a `struct`. A type with a constraint is a `class` with a constructor that enforces it. No object exists in an invalid state. | `[CG C.2, C.40, C.41, C.42]` |
| 3 | **Absence is represented, never encoded.** No NaN-as-missing, no `-1`-as-not-found, no empty-string-as-null. | `[CG F.60]`, `[CG P.6]` |
| 4 | **Interfaces do not admit silent reordering.** No two adjacent parameters may be interchangeable with a change of meaning and no compiler complaint. Keep argument counts low. | `[CG I.23, I.24]` |
| 5 | **Dimensioned values carry their unit in the name.** `width_mm`, `feed_mm_per_min`, `angle_deg`. At every interface, without exception. | `[CG I.4]`, `[CG NL.19]` |
| 6 | **Errors carry the four-part message:** what failed, what field, what constraint, actual value. | *ours* |
| 7 | **No magic constants.** | `[CG ES.45]` |
| 8 | **Dependency direction holds.** Includes flow one way through the layer stack. | *ours* |
| 9 | **Determinism.** No undefined behaviour, no unordered-container iteration order in output, no uninitialized reads, no platform-dependent floating-point in golden output. | `[CG P.4]`, `[CG ES.20]` |
| 10 | **Prefer immutable data.** `const` by default on objects, members, member functions, and parameters. | `[CG P.10]`, `[CG Con.1-Con.5]` |
| 11 | **Rule of zero.** Declare no special member functions unless you must; if you declare or `=delete` one, do all of them. | `[CG C.20, C.21, C.22]` |

### Tier 2 — Mandatory Given the Mechanism

Each of these is absolute where your standard provides the facility. See [mechanisms.md](mechanisms.md) for the per-standard column.

| Rule | Mechanism gate |
|------|---------------|
| Closed-set variation is compiler-checked for exhaustiveness | `std::variant` + `std::visit` (C++17+); `enum class` + `default`-less `switch` under `-Werror=switch` (C++11) |
| Absence uses the standard optional | `std::optional` (C++17+) |
| Sequence parameters carry their bounds | `std::span` (C++20+); iterator pair or `const vector&` earlier |
| Non-owning string parameters use a view | `std::string_view` (C++17+) |
| Informative failure uses the standard result type | `std::expected` (C++23); project result type earlier |
| Text formatting is type-safe | `std::format` (C++20+) |
| Template parameters are constrained | concepts (C++20+); `static_assert` earlier |
| Enumerations are scoped | `enum class` (C++11+, i.e. always) |

### Tier 3 — Strong Default, Named Escapes

| Default | Named escapes |
|---------|--------------|
| **Dimensioned scalars stay primitives with unit-suffixed names** (Tier 1 #5). Strong typedefs are *not* the default. | Introduce a strong typedef when: (a) two units of the same underlying type are genuinely confusable at a boundary *and* (b) arithmetic does not flow through the type. Wrapping values that participate in geometry arithmetic produces ceremony without safety — see [Decision: when a thing becomes a type](#decision-when-a-thing-becomes-a-type). |
| **Exceptions are permitted at module boundaries.** | Forbidden in real-time loops; never cross an FFI boundary un-translated; `-fno-exceptions` permitted per module when latency, binary size, or an FFI target justifies it, declared in that module's top-level header. |
| **Concrete types over templates.** | Templatize when a third concrete caller forces it, or when the alternative is a runtime-typed interface that loses checking. |
| **Public API is validated; internals trust their contracts.** | The FFI layer is an explicit escape hatch: it converts and validates at the seam and is permitted the boilerplate that implies. Document it as the boundary it is. |
| **`class` with a constructor for types with invariants** (Tier 1 #2). | Genuinely constraint-free data — a 2D point, an RGB triple, a config bag whose fields are independent — stays an aggregate `struct`. `[CG C.2]` is the test, not a preference for encapsulation. |

---

## Values

When no rule above addresses your case, decide from these. They are ordered; earlier beats later.

1. **Correct by construction beats correct by test.** The best defect is the one the type system refuses to compile. The second best is the one a constructor rejects at the boundary. Tests are due diligence — they confirm what the design already guarantees. A codebase that relies on its test suite for correctness has moved the invariant out of the code and into a process. `[CG P.4, P.5]`
2. **Failure modes are visible.** Errors are not swallowed. Invalid states are unrepresentable where possible and rejected at construction where not. In a system whose output drives a physical machine, a silent wrong answer is the worst possible failure. `[CG P.6, P.7]`
3. **Ownership is obvious.** Who owns this memory, this resource, this lifetime — answerable in under five seconds by anyone reading the declaration. RAII by default. `[CG P.8]`
4. **Boring is a feature.** Two language features rather than seven. Idiomatic rather than clever. The next reader should not need to leave the file. Every C++ feature you reach for is a feature the next reader must know.
5. **Defensive at boundaries, trusting inside.** Validate at the outside edge — user input, file parsing, FFI. Then trust it. Defensive checks scattered through internals are a symptom of an invariant that was never established. `[CG P.7]`
6. **Express intent, not mechanism.** The reader should see *what* the code means before *how* it works. `[CG P.1, P.3]`
7. **Determinism is the default.** Same input, same output, on every platform and every run.
8. **The compiler is your ally.** Strong types where they matter, `enum class` always, `[[nodiscard]]` where the return value is the point, `constexpr` where possible, `noexcept` where genuinely true, exhaustive dispatch that breaks compilation when a case is added. `[CG P.5]`

---

## Patterns

A pattern answers *how do I build this kind of thing*. This is the section that produces designed code; the [traps](#traps) only prevent wrong code.

Examples are in the domain these projects actually occupy — geometry, toolpaths, machine configuration — because a pattern illustrated with `Foo` and `Bar` does not transfer.

### Pattern: Value Type With Invariant

**The most load-bearing pattern in this document.** It is the C++ analogue of the frozen dataclass that anchors the Python convention.

The decision is `[CG C.2]`, and it is a question about the *data*, not about taste:

> Use `class` if the class has an invariant; use `struct` if the data members can vary independently.

**Members vary independently → aggregate `struct`.** A 2D point is any two doubles. There is no combination of `x` and `y` that is invalid. Wrapping it in a class with accessors adds ceremony and subtracts nothing.

```cpp
struct Vec2 {
    double x = 0.0;
    double y = 0.0;
};
```

**Members are constrained → `class` with a constructor.** A cutting tool with zero diameter is not a tool. The constructor is the only way in, so no such object exists.

```cpp
class Tool {
 public:
    Tool(double diameter_mm, double rpm, double feed_xy_mm_per_min, double feed_z_mm_per_min);

    double diameter_mm() const { return diameter_mm_; }
    double radius_mm() const { return 0.5 * diameter_mm_; }
    double rpm() const { return rpm_; }
    double feed_xy_mm_per_min() const { return feed_xy_mm_per_min_; }
    double feed_z_mm_per_min() const { return feed_z_mm_per_min_; }

 private:
    double diameter_mm_;
    double rpm_;
    double feed_xy_mm_per_min_;
    double feed_z_mm_per_min_;
};

Tool::Tool(double diameter_mm, double rpm, double feed_xy_mm_per_min, double feed_z_mm_per_min)
    : diameter_mm_(diameter_mm),
      rpm_(rpm),
      feed_xy_mm_per_min_(feed_xy_mm_per_min),
      feed_z_mm_per_min_(feed_z_mm_per_min) {
    if (diameter_mm <= 0.0) {
        throw std::invalid_argument("Tool: diameter_mm must be > 0, got " +
                                    std::to_string(diameter_mm));
    }
    if (rpm < 0.0) {
        throw std::invalid_argument("Tool: rpm must be >= 0, got " + std::to_string(rpm));
    }
}
```

**What this buys, concretely.** Without the invariant, every consumer defends itself:

```cpp
// in one planner
const double tool_d = tool.diameter <= 0.0 ? kDefaultToolDiameterMm : tool.diameter;
// in another planner, months later
const double tool_d = tool.diameter <= 0.0 ? kBoreDefaultToolDiameterMm : tool.diameter;
```

Two sites, two different fallbacks, one silent divergence in machine output. This is not hypothetical — it is the failure this pattern exists to prevent. With the invariant, both lines delete and the question *"what does a zero-diameter tool mean"* is answered once, at the boundary where tools are loaded.

**Non-throwing construction.** Where a caller wants to test rather than catch, add a static `try_from` alongside the constructor. It does not duplicate the validation — it delegates to it.

```cpp
// Return type is the optional mechanism for your standard — mechanisms.md §1.
static std::optional<Tool> try_from(double diameter_mm, double rpm,
                                    double feed_xy_mm_per_min, double feed_z_mm_per_min);
```

**Rules this pattern carries:**
- Validate in the constructor, not in an `init()` the caller must remember. `[CG C.41]`
- Throw when construction cannot produce a valid object. `[CG C.42]`
- Members are `private`; accessors are `const`. `[CG C.8]`, `[CG Con.2]`
- Prefer initialization to assignment in the member-init list. `[CG C.49]`
- Single-argument constructors are `explicit`. `[CG C.46]`
- Do not write a default constructor that only zeroes members — use default member initializers. `[CG C.45]`

### Pattern: Params Struct

`[CG I.23]` *Keep the number of function arguments low.* `[CG I.24]` *Avoid adjacent parameters that can be invoked by the same arguments in either order with different meaning.*

I.24 is the sharper of the two, and it is the reason this pattern is Tier 1. The defect is not the count — it is that the compiler cannot tell a correct call from a transposed one.

```cpp
// Wrong. Four adjacent doubles; every ordering compiles.
Paths plan_pocket(const PlanarFace& face, const Tool& tool, double step_over_mm,
                  double step_down_mm, double safe_z_mm, double ramp_angle_deg,
                  PocketStrategy strategy);

plan_pocket(face, tool, 6.0, 2.0, 5.0, 30.0, PocketStrategy::Spiral);
//                      ^^^^^^^^^^^^^^^^^^^ transpose any pair; still compiles
```

```cpp
// Right. Named fields at the construction site; no ordering to get wrong.
struct PocketParams {
    double step_over_mm;
    double step_down_mm;
    double safe_z_mm;
    double ramp_angle_deg;
    PocketStrategy strategy = PocketStrategy::Raster;
};

Paths plan_pocket(const PlanarFace& face, const Tool& tool, const PocketParams& params);

plan_pocket(face, tool, PocketParams{
    .step_over_mm = 6.0,
    .step_down_mm = 2.0,
    .safe_z_mm = 5.0,
    .ramp_angle_deg = 30.0,
    .strategy = PocketStrategy::Spiral,
});
```

C++ has no keyword arguments, so a params struct with designated initializers is how a call site becomes self-describing. (Designated initializers are C++20; on earlier standards the struct is still correct and the fields are assigned before the call, or a small builder is used.)

**Two compliant routes.** A params struct satisfies I.24 by *naming* the parameters. Distinct types satisfy it by making a transposition ill-formed. Either is acceptable — you are not required to do both.

**Thresholds.** More than four parameters is a trigger regardless of types. Two adjacent same-type parameters is a trigger regardless of count.

**Escape:** genuinely ordered mathematical arguments where the order is the convention and a reader would not expect otherwise — `lerp(a, b, t)`, `clamp(v, lo, hi)`, `atan2(y, x)`. These are not improved by a struct.

**Related:** `[CG F.21]` *To return multiple "out" values, prefer returning a struct.* The same reasoning applies on the way out.

### Pattern: Ownership Decision

Answer three questions in order. The first "yes" is your answer. `[CG R.*]`

| Question | Answer |
|----------|--------|
| Does this need to outlive the current scope? | **No** → a value or an automatic variable. Do not heap-allocate. `[CG R.5]` |
| Is there exactly one owner? | **Yes** → `std::unique_ptr<T>`, transferred by move. `[CG R.20]` |
| Are there genuinely multiple independent owners with no primary? | **Yes** → `std::shared_ptr<T>`. `[CG R.21]` |
| None of the above — you just need to look at it | A `const T&` parameter, or `T*` if null is meaningful. Non-owning, always. `[CG R.3, R.4]`, `[CG F.60]` |

Most code never reaches question two. A value member, a `std::vector<T>`, and a `const&` parameter cover the large majority of real ownership needs, and they are the forms with no lifetime question to answer.

**Ownership never transfers through a raw pointer.** `[CG I.11]` A function taking `std::unique_ptr<T>` by value assumes ownership and says so in its signature. `[CG R.32]`

### Pattern: Rule of Zero

`[CG C.20]` *If you can avoid defining default operations, do.*

A type built out of values and standard containers needs no copy constructor, no assignment operator, and no destructor. The compiler-generated ones are correct, and every one you write by hand is a place to introduce a bug.

```cpp
class Toolpath {
 public:
    explicit Toolpath(std::vector<Move> moves);
    // no destructor, no copy, no move — all correct by default
 private:
    std::vector<Move> moves_;
};
```

**If you declare one, declare all five.** `[CG C.21]` Declaring a destructor suppresses implicit move generation, which silently turns moves into copies — a performance defect with no diagnostic. If you write any of copy ctor, copy assign, move ctor, move assign, or destructor, then write or `= delete` all of them.

**When you genuinely need them:** a type directly managing a non-RAII resource (an OS handle, a C library object). That type should be small, should do nothing but own that resource, and everything else composes it. `[CG C.31]`, `[CG P.11]`

Move operations are `noexcept`. `[CG C.66]`

### Pattern: Immutability By Default

`[CG Con.1]` *By default, make objects immutable.* `[CG P.10]` *Prefer immutable data to mutable data.*

This is the Python convention's frozen-dataclass discipline expressed in C++, and it is Tier 1 for the same reason: immutable data cannot be corrupted by a caller you did not think about.

```cpp
const Bounds b = bounds_of(polygon);          // const local              [CG ES.25]
double radius_mm() const { return ...; }      // const member function    [CG Con.2]
void process(const Polygon& poly);            // const parameter          [CG Con.3]
constexpr double kMinMarginMm = 10.0;         // compile-time constant    [CG Con.5]
```

Write `const` first and remove it when you need to mutate — not the reverse. A non-`const` local in the middle of a function is a signal to the reader that it changes; if it does not change, the signal is a lie.

`mutable` members exist for caches and are otherwise a smell.

### Pattern: Wrapper Type For Preconditions

A function with a *structural* precondition — convex, sorted, non-empty, closed, known winding — takes a type that proves it. The check happens once, at the boundary, rather than inside every algorithm that wants to assume it.

```cpp
class ConvexPolygon {
 public:
    // std::optional here is the C++17+ spelling; see mechanisms.md §1 for earlier standards.
    static std::optional<ConvexPolygon> try_from(Polygon points);
    const Polygon& points() const { return points_; }

 private:
    explicit ConvexPolygon(Polygon points);
    Polygon points_;
};

Polygon inset(const ConvexPolygon& poly, double offset_mm);
```

`inset`'s signature *proves* its precondition. A non-convex polygon cannot reach it without passing through `try_from`. Contrast the alternative, where `inset` either re-checks convexity on every call or trusts a comment.

This is the structural case of [value type with invariant](#pattern-value-type-with-invariant), and it is how `[CG I.5]` *State preconditions* is satisfied without the GSL: the precondition is not stated, it is *enforced by the type*.

**Scalar preconditions do not get a wrapper.** A positive width belongs on the type that owns the width field. Reserve wrappers for structure.

**Frequent `assert`s are a missing wrapper type.** If a function asserts the same precondition its three callers also assert, the precondition wants to be a type.

### Pattern: Module Boundary

A header is an interface. What it exposes is a promise; what it hides is free to change.

```cpp
// include/proj/algo/plan_2d.hpp
#pragma once

#include <vector>
#include "proj/types.hpp"

namespace proj::algo {

Paths plan_pocket(const PlanarFace& face, const Tool& tool, const PocketParams& params);

}  // namespace proj::algo
```

```cpp
// algo/plan_2d.cpp
#include "proj/algo/plan_2d.hpp"

namespace proj::algo {
namespace {

// Everything internal lives here. Not in the header, not with static linkage.
constexpr int kHelixSegments = 60;
Paths plan_pocket_spiral(...);

}  // namespace
}  // namespace proj::algo
```

| Rule | Citation |
|------|----------|
| Internal entities go in an anonymous namespace in the `.cpp` | `[CG SF.22]` |
| Never an anonymous namespace in a header | `[CG SF.21]` |
| Headers are self-contained — a header compiles alone | `[CG SF.11]` |
| No object definitions or non-inline function definitions in a header | `[CG SF.2]` |
| A `.cpp` includes the header defining its own interface, first | `[CG SF.5]` |
| No `using namespace` at header scope | `[CG SF.7]` |
| Namespaces express logical structure | `[CG SF.20]` |
| Include guards on every header (`#pragma once` is acceptable) | `[CG SF.8]` |

**Test for a leaky header:** if changing a private implementation detail forces a recompile of unrelated translation units, the detail is in the wrong file.

### Pattern: Free Function By Default

`[CG C.4]` *Make a function a member only if it needs direct access to the representation of a class.*

A member function is part of a type's interface, and its interface should be as small as the invariant requires. Everything else is a free function in the same namespace. `[CG C.5]`

```cpp
class ConvexPolygon { /* only what needs the representation */ };

// same namespace, not members — these need only the public interface
Polygon inset(const ConvexPolygon& poly, double offset_mm);
double area_mm2(const ConvexPolygon& poly);
Bounds bounds_of(const ConvexPolygon& poly);
```

This keeps the class small enough to audit, lets algorithms be added without touching the type, and means a bug in `area_mm2` cannot corrupt the invariant.

### Pattern: Named Operation

`[CG F.1]` *"Package" meaningful operations as carefully named functions.* `[CG F.2]` *A function should perform a single logical operation.* `[CG F.3]` *Keep functions short and simple.*

A long function is usually several operations that have not been named. Naming them is not decomposition for its own sake — it is how the reader learns what the code does without simulating it.

The signal is not line count, it is **whether you can name what a block does.** If a comment would explain a block, that block is a function and the comment is its name.

```cpp
// Instead of one 90-line plan_pocket_spiral with four implicit phases:
std::vector<Polygon> build_inset_rings(const ConvexPolygon& outermost, double step_over_mm);
std::optional<Span> find_sliver_span(const Polygon& innermost, double tool_diameter_mm);
void emit_ring_transition(Path& moves, const Polygon& from, const Polygon& to);
```

Prefer pure functions — same input, same output, no side effects. `[CG F.8]` They are the ones you can test in isolation and reason about without context.

Avoid unnecessary condition nesting; prefer early returns. `[CG F.56]`

### Pattern: Failure Mechanism

Pick by *what the caller needs*, not by what is convenient to write.

| Mode | Use when | Citation |
|------|----------|----------|
| Standard optional | Absence is the only failure mode; there is nothing to explain | `[CG F.60]` |
| Result type (`std::expected` on C++23) | Failure carries information the caller must act on | `[CG E.1]` |
| Exception | Genuinely exceptional: allocation failure, invariant violation, unrecoverable corruption | `[CG E.2]`, `[CG I.10]` |
| `assert` | "Cannot happen" — upstream validation already guarantees it. Sparingly; frequent asserts mean a [wrapper type](#pattern-wrapper-type-for-preconditions) is missing | `[CG I.5]` |
| Silent partial output | **Never.** | — |

See [mechanisms.md — Failure](mechanisms.md#5-failure) for the per-standard mechanism.

**Error message format.** Every constructed message — exception, result payload, log line, structured warning — has four parts:

1. **What failed** — class, function, or subsystem
2. **What field** — the specific parameter or invariant
3. **What constraint** — the rule broken
4. **Actual value** — what was received

```cpp
throw std::invalid_argument("SheetConfig: width_mm must be > 0, got -3.5");
```

This format is identical in the Python convention, deliberately, so a message reads the same regardless of which side of the FFI produced it.

**Exception types are purpose-designed, not built-in.** `[CG E.14]` Throw by value, catch by reference. `[CG E.15]` Never use exception specifications other than `noexcept`. `[CG E.30]`

### Failure Semantics By Layer

Failures become less fatal as you move outward. Parsers are strict; orchestrators tolerate per-item failure and are strict about safety.

| Layer | On failure | Mechanism |
|-------|-----------|-----------|
| FFI boundary | Translate to the host language | C++ exception → Python exception at the binding layer. Never let one cross unhandled. |
| Module public API | Return a result type | Result type for recoverable failure; throw only for invariant violations |
| Internal helpers | Trust contracts | Input is validated upstream; `assert` cheaply where defensible |
| Real-time loop | Log and continue | Record in a pre-allocated trace structure; surface at the scan boundary; never throw |
| Real-time loop boundary | Inspect the trace | The caller examines accumulated errors and decides whether to halt |

---

## Decision Procedures

C++ has design axes Python does not — ownership, lifetime, value versus reference, compile time versus runtime. These are the questions to ask before writing, in the order to ask them.

### Decision: When A Thing Becomes A Type

Work down the list; stop at the first match.

| Question | If yes |
|----------|--------|
| Does it have an invariant — some combination of values that must never exist? | A `class` with a validating constructor. [Pattern](#pattern-value-type-with-invariant) `[CG C.2]` |
| Does it have a *structural* precondition other code wants to assume? | A [wrapper type](#pattern-wrapper-type-for-preconditions) |
| Is it a fixed set of alternatives? | `enum class`, or a variant if the alternatives carry payloads |
| Do several values always travel together into functions? | A params struct or an aggregate. [Pattern](#pattern-params-struct) |
| Are two same-typed values confusable at a boundary, *and* does arithmetic not flow through them? | A strong typedef — **Tier 3, not the default** |
| None of the above | A primitive with a unit-suffixed name. This is the common case. |

**On strong typedefs, explicitly.** The temptation is to wrap every dimensioned scalar in a `Millimeters` type. Resist it in arithmetic-heavy code. Compare:

```cpp
const double r_eff_mm = std::max(0.01, (bore_d_mm - tool_d_mm) * 0.5);              // clear
const Millimeters r_eff = std::max(Millimeters{0.01},
                                   (bore_d - tool_d) * Millimeters{0.5});          // worse
```

A type supporting the full arithmetic of geometry correctly *is* a units library — real infrastructure with real cost. A partial one produces ceremony without safety. Tier 1 #5 (unit suffixes) plus [params structs](#pattern-params-struct) already close the transposition hole that motivates wrapping, at a fraction of the cost. Reach for a strong typedef at a confusable boundary where the value is carried, not computed.

### Decision: How To Pass A Parameter

`[CG F.15]` *Prefer simple and conventional ways of passing information.* `[CG F.16]` *For "in" parameters, pass cheaply-copied types by value and others by reference to `const`.*

| Pass by | When | Citation |
|---------|------|----------|
| Value | Small and cheap to copy (`double`, `Vec2`, an enum); or you will modify your own copy; or you will move from it | `[CG F.16]` |
| `const T&` | Larger types you only read | `[CG F.16]`, `[CG Con.3]` |
| `T&` | In-out parameters. Rare — prefer returning a value | `[CG F.17]` |
| `T*` | Null is a meaningful value | `[CG F.60]` |
| `T&&` | You will move from it and the caller knows | `[CG F.18]` |
| Sequence view | A read-only or write-through sequence — see [mechanisms.md](mechanisms.md#4-sequences) | `[CG F.24]` |
| Return by value | Output. Always prefer this to an out-parameter | `[CG F.20]` |

Return a struct for multiple outputs. `[CG F.21]` Never return a reference or pointer to a local. `[CG F.43]`

### Decision: Compile Time Or Runtime

`[CG P.5]` *Prefer compile-time checking to run-time checking.*

| Question | Mechanism |
|----------|-----------|
| Can this be wrong at compile time? | Make it a type error. Distinct types, `enum class`, exhaustive dispatch |
| Is this value known at compile time? | `constexpr` `[CG Con.5]`, `[CG F.4]` |
| Is this a fact about types the reader should see? | `static_assert` with a message |
| Must this be checked at runtime? | Check it **once**, at the boundary, and encode the result in a type `[CG P.6, P.7]` |

### Decision: Is Inheritance Right

Almost always no. Inheritance shares *implementation*; it is not how variation is represented.

| Question | Answer |
|----------|--------|
| Is this a fixed set of alternatives? | Not inheritance — see [mechanisms.md — closed-set variation](mechanisms.md#2-closed-set-variation) |
| Is it an open set of behaviours, injected by a caller? | An abstract interface with no data. `[CG I.25]`, `[CG C.129]` |
| Is it code reuse? | Not inheritance — composition, or a free function |
| Do I have at least two concrete cases in hand? | If not, write the function. Decide on the second. |

A polymorphic base class has a public virtual destructor, or a protected non-virtual one. `[CG C.35]` Virtual functions specify exactly one of `virtual`, `override`, `final`. `[CG C.128]` Never call a virtual function from a constructor or destructor. `[CG C.82]`

---

## Traps

Each trap names a pattern that generation — human or machine — produces by default, and the rule that contradicts it.

### Trap: stringly-typed dispatch

A struct with a `std::string kind` field plus optional payload members is a tagged union with no checking. An `enum class` paired with an if/else-if chain is only half a fix: the enum is a real type, but nothing forces the chain to handle every case.

**Use** the exhaustive mechanism for your standard — [mechanisms.md §2](mechanisms.md#2-closed-set-variation). Adding an alternative must turn "forgot to handle it" into a compile error.

Shown in its C++17+ form. On C++11 the same intent is expressed with an `enum class` tag and a `default`-less `switch` under `-Werror=switch`; the guarantee is identical.

```cpp
struct Comment { std::string text; };
struct SetRpm  { double rpm; };
struct Rapid   { std::optional<double> x, y, z; };
struct Cut     { std::optional<double> x, y, z, feed; };

using Move = std::variant<Comment, SetRpm, Rapid, Cut>;

std::string emit(const Move& move) {
    return std::visit(overloaded{
        [](const Comment& c) { return "; " + c.text; },
        [](const SetRpm& s)  { return format_rpm(s.rpm); },
        [](const Rapid& r)   { return format_rapid(r); },
        [](const Cut& c)     { return format_cut(c); },
    }, move);
}
```

One overload per alternative, never a generic `[](auto&&)` fallback — a catch-all compiles for every future alternative and silently swallows the case you just added, destroying the only property the variant was chosen for.

### Trap: inheritance for variation

`class Move { virtual ~Move(); }` with `Rapid` and `Cut` deriving from it is a v-table where a variant belongs. It costs an allocation, a pointer chase, and the compiler's ability to tell you a case is missing.

**Use** a variant. Inherit only for an open set of behaviours behind an interface with no data. See [Decision: is inheritance right](#decision-is-inheritance-right). `[CG C.129]`

### Trap: sentinel value

NaN means *invalid number*, not *no number*. `-1` is an integer. `""` is a string. Encoding absence in the value space means real bugs — degenerate geometry, division by zero, uninitialized arithmetic — become indistinguishable from intentional absence.

**Use** the absence mechanism for your standard — [mechanisms.md §1](mechanisms.md#1-absence). NaN in output is a bug to investigate, never a value with meaning.

### Trap: defensive everywhere

The same precondition checked in three functions is not thoroughness — it is an invariant that was never established, paying for itself three times and drifting the moment one site's fallback differs from another's.

```cpp
// site A
const double d = tool.diameter <= 0.0 ? kDefaultToolDiameterMm : tool.diameter;
// site B, different fallback, silent divergence in output
const double d = tool.diameter <= 0.0 ? kBoreDefaultToolDiameterMm : tool.diameter;
```

**Use** a [value type with an invariant](#pattern-value-type-with-invariant). Check once, at construction, then trust the type. This is Value 5 — defensive at boundaries, trusting inside.

### Trap: pointer-and-length pair

`(const T* data, size_t length)` puts the lifetime contract in a comment and the bounds check on every caller.

**Use** the sequence mechanism for your standard — [mechanisms.md §4](mechanisms.md#4-sequences). `[CG I.13]`

At an `extern "C"` boundary the foreign signature dictates the pair. Convert on entry and never touch the raw pointer again — to a span on C++20, to a vector or iterator pair earlier:

```cpp
extern "C" int process_buffer(const Vec2* data, size_t length) {
    const std::span<const Vec2> path(data, length);   // C++20; see mechanisms.md §4
    // body uses path only
}
```

### Trap: stored view

A non-owning view — `std::span` or `std::string_view` where your standard has them, an iterator pair or bare pointer earlier — refers to data it does not own. Storing one as a member ties the object's validity to data it does not control: a use-after-free waiting for a caller to go out of scope first.

**Use** an owning member (`std::vector<T>`, `std::string`) if the object retains the data; take the view as a parameter if it needs it only for the duration of a call.

### Trap: reflexive shared_ptr

`std::shared_ptr` is for genuinely shared ownership. Reaching for it because the ownership question is unresolved hides the question and buys an atomic refcount the design does not need.

**Use** the [ownership decision](#pattern-ownership-decision). `[CG R.21]`

### Trap: cargo-culted mutex

A `std::mutex` member on a class with no documented threading model is cosplay. The default for every type is *single-threaded by contract*; concurrent access is the caller's problem until stated otherwise.

**Use** nothing, and document the threading model when concurrency is actually introduced. Then see [mechanisms.md §10](mechanisms.md#10-concurrency).

If a module's concurrency model is not obvious from its API, state it in one or two sentences at the top of the header.

### Trap: auto by default

`auto` hides the type. Use it where the type is obvious from the right-hand side or unspellable — `auto it = container.begin()`, `auto p = std::make_unique<Tool>(...)`, lambdas. Do not use it where the type is the load-bearing fact: `auto result = compute_thing();` tells the reader nothing.

`[CG ES.11]` *Use `auto` to avoid redundant repetition of type names* — the rule is about redundancy, not about avoiding type names.

### Trap: blanket noexcept

`noexcept` is a claim, and if it is false the program calls `std::terminate`. "It is free" is wrong.

**Use** `noexcept` where it is genuinely true and it matters: move operations `[CG C.66]`, swap, destructors, pure arithmetic on built-ins. `[CG E.12]`

### Trap: premature template

A function with two concrete callers is not generic — it is two callers.

**Use** a concrete type. Templatize on the third caller, or when the alternative loses type checking. `[CG T.120]`

On C++20 an unconstrained template parameter is incomplete. `[CG T.10]`

### Trap: mid-stack exception translation

Catching to re-throw a different type at every layer produces noise that buries real handling.

**Use** exceptions for genuinely exceptional conditions and translate exactly once — at the FFI boundary, into the host language's mechanism. `[CG E.17]` *Don't try to catch every exception in every function.* `[CG E.18]` *Minimize the use of explicit `try`/`catch`.*

Exceptions as control flow are forbidden. `[CG E.3]`

### Trap: void-cast unused param

`(void)param;` marks a parameter that should not exist.

**Allowed** on a virtual override or interface implementation where the signature is mandated. **Not allowed** on a leaf function — delete the parameter.

### Trap: empty-stub public function

A function in a public header returning `{}` is indistinguishable from one that legitimately produced an empty result.

**Use** deletion until it is implemented. If a caller needs the symbol first, it is `[[noreturn]]` and throws `std::logic_error("not implemented: <name>")`. An unimplemented function gets no FFI binding.

### Trap: magic number

Inline literals in geometry, timing, and limit checks drift and diverge.

**Use** a named constant — `constexpr` at file scope, or a shared constants header for cross-module values. `[CG ES.45]`

```cpp
constexpr double kMinMarginMm = 10.0;
if (margin_mm < kMinMarginMm) { ... }
```

Trivially obvious literals — `0`, `1`, `0.5` for a midpoint, array indices — need no name.

### Trap: parallel near-duplicates

Two functions sharing more than half their bodies drift: a fix applied to one is forgotten in the other.

**Use** one function with an explicit [params struct](#pattern-params-struct) carrying the difference.

The test is *would a future change need to be made in both places*. Accidental similarity that would not co-evolve stays separate.

---

## FFI Conventions

The boundary between languages is where each language's conventions disagree most. These rules are identical in the [Python convention](../python_guidelines.md#ffi-conventions), by design — the two documents state the same contract from each side.

| Rule | Mechanism |
|------|-----------|
| Names cross unchanged | `parse_layout` in Python is `parse_layout` in C++. No `parseLayout`, no `_parse_layout_impl` shim. |
| Validation is the calling side's job | The caller validates before crossing. The callee may assert cheaply; it does not re-validate defensively. |
| Errors translate exactly once | C++ exception → Python exception at the binding layer. C++ does not catch to translate mid-stack; Python does not re-wrap. Type and message are preserved. |
| Absence maps to absence | `std::optional<T>` ↔ `Optional[T]`; `std::nullopt` ↔ `None`. NaN never crosses. An empty collection does not signal failure. |
| Units survive the trip | Conversion happens at the *outer* boundary — user input, file parsing. Converting at the FFI seam is a category error. |
| Ownership is explicit | By-value crossings copy. By-reference crossings are non-owning with documented lifetime. C++ does not hand raw pointers to the host; ownership transfers by `std::unique_ptr` or by value. Python does not pass mutable objects expecting C++ to retain them past the call. |
| The IR is the contract | Shared structures — move IR, parsed layouts, plan output — have one schema and one source of truth. A schema change is versioned and moves both sides plus the goldens together. |
| The binding layer is a declared escape hatch | It converts, validates, and translates at the seam, and is permitted the boilerplate that implies. It is the one place where boundary ceremony is correct. |

---

## Dependency Direction

Includes flow one way:

```
Input/CLI  →  Parser  →  IR/Model  →  Validation  →  Backend/Output
```

Each layer may include from layers to its right, never to its left.

| Trigger | Action |
|---------|--------|
| A lower layer needs a higher layer's type | Introduce an adapter at the boundary. Do not pull the higher layer's headers down. |
| A wrapper type is used by several layers | It lives at the layer that owns the precondition, not the layer that consumes the value. |
| Ambiguity check | Delete the higher-level module mentally. Do the lower-level modules still compile? If not, the dependency is inverted. |

---

## Real-Time Loops

Scan loops, audio callbacks, ISRs. Different rules apply, and they override the defaults above.

| Concern | Rule |
|---------|------|
| Exceptions | Forbidden — non-deterministic timing. Follow `[CG E.25, E.26, E.27]` for the exception-free discipline. |
| Allocation | Pre-allocate. `push_back`, string operations that may reallocate, and anything reaching `malloc` are defects unless proven otherwise. |
| Errors | Recorded in a pre-allocated trace structure, surfaced at the scan boundary, never thrown. |
| Logging | The trace structure, not a runtime logger. Formatting cost and lock contention are unacceptable here. |
| Determinism | No unbounded loops, no lock acquisition of unbounded duration, no I/O. |

---

## Coroutines

| Concern | Rule |
|---------|------|
| Reference parameters into a coroutine that may suspend | Forbidden. The reference dangles if the caller's frame dies before resumption. Pass by value. |
| Lambda captures into coroutines | By value, unless the lambda's lifetime is provably bounded by the captured object's. |
| Awaitable lifetime | Awaitables are non-owning by default. An awaitable outliving the awaiting frame is an explicit ownership decision. |
| `co_await` chains deeper than two or three | Use symmetric transfer — return `coroutine_handle<>` from `await_suspend` — to bound stack growth. |

---

## Testing

Tests are due diligence, not a quality mechanism. A defect the type system can refuse should never reach a test. What tests are for is confirming that the design does what it claims and that it keeps doing it.

| Rule | Mechanism |
|------|-----------|
| Test where the logic lives | Unit tests target the function or class, not the pipeline. Pipeline tests are integration tests, and there are few. |
| Do not test the language | No test asserting that a `const` member cannot be assigned, or that an optional is empty by default. Test what *your code* adds. |
| Test the invariant, not the getter | A validating constructor deserves a test that a violating input is rejected. An accessor returning a member does not. |
| Round-trip tests assert semantic equivalence | `parse(format(model)) == model`. Whitespace, key order, and equivalent representations may legitimately differ. |
| One assertion of a behaviour | Two tests covering the same behaviour over the same input is a defect. Check what exists before adding a file. |
| Use the framework | Catch2, GoogleTest, or doctest per project. No hand-rolled `int main()` runners, no PASS/FAIL prints, no manual reporting. |
| Golden-tested IR | Any computation producing structured output — toolpaths, plans, schedules, traces, generated code — has a golden-tested IR. Every change is either (a) no golden diff, proving a refactor, or (b) a deliberate regeneration whose diff is explained in the commit message. Adding an IR alternative is versioned: define, expose across the FFI, document, regenerate — in that order. |
| Include a test that would fail | A test suite where every test passes on a plausible wrong implementation is not testing. |

---

## Logging

| Rule | Mechanism |
|------|-----------|
| No `std::cout` or `printf` in library code | They belong in CLI entry points. One left in a deep helper spams every run thereafter. |
| Use a structured logger | spdlog, glog, or the project's chosen library. |
| Real-time loops use trace structures | See [Real-Time Loops](#real-time-loops). |

| Level | Use when |
|-------|----------|
| `TRACE` / `DEBUG` | Internal state during development — values, branch taken |
| `INFO` | High-level progress. Operators read this; do not flood it with per-item detail |
| `WARN` | Unexpected but recoverable. Not for expected situations |
| `ERROR` | Something failed; the program continues |
| `FATAL` | The program cannot continue |

---

## Naming

Names are mandated machine-wide, not per project. The FFI rule requires names to cross language boundaries unchanged, which is only achievable if both languages agree on case — so the choice is structural rather than cosmetic.

| Kind | Case | Example |
|------|------|---------|
| Functions, variables, parameters, members | `snake_case` | `plan_pocket`, `step_over_mm` |
| Private data members | `snake_case_` trailing underscore | `diameter_mm_` |
| Types (class, struct, enum, alias) | `PascalCase` | `ConvexPolygon`, `PocketParams` |
| Enumerators | `PascalCase` | `PocketStrategy::Spiral` |
| Constants (`constexpr`, `const` at namespace scope) | `kPascalCase` | `kMinMarginMm` |
| Macros | `ALL_CAPS`, project-prefixed — and avoid macros | `PROJ_ASSERT` |
| Namespaces | `snake_case`, nested by layer | `proj::algo` |
| Files | `snake_case`, `.hpp` / `.cpp` | `plan_2d.cpp` |

`[CG NL.8]` *Use a consistent naming style.* `[CG NL.10]` *Prefer `underscore_style` names.* `[CG NL.9]` *Use `ALL_CAPS` for macro names only.* `[CG NL.5]` *Avoid encoding type information in names.*

Do not relitigate this per project.

### Naming Vocabulary

Same verb, same operation — in both languages, so names cross the FFI unchanged. This table is identical in the [Python convention](../python_guidelines.md#naming-vocabulary).

| Verb | Meaning | Example |
|------|---------|---------|
| `parse_*` | Text or bytes → structured data | `parse_config` |
| `format_*` | Structured data → text | `format_output` |
| `resolve_*` | Simplify structure, expand references | `resolve_layout` |
| `*_to_*` | Convert between typed representations | `ast_to_ir` |
| `validate_*` | Check correctness; throw or return an error | `validate_bounds` |
| `build_*` | Construct a complex object from parts | `build_pipeline` |
| `load_*` | Read from disk or an external source | `load_config` |
| `write_*` | Emit machine or file output | `write_report` |
| `render_*` | Emit visual output | `render_diagram` |
| `expand_*` | Parameterized instantiation | `expand_template` |
| `plan_*` | Compute an execution sequence | `plan_pocket` |

| Pattern | Returns |
|---------|---------|
| `is_*` / `has_*` | `bool` |
| `try_*` / `try_from` | Optional or result — never throws. Pairs with [wrapper types](#pattern-wrapper-type-for-preconditions) |
| `get_*` | An accessor that cannot fail; the precondition is the caller's |
| `find_*` | Optional or iterator |
| `make_*` | Constructs a value |

Prefer a name over a comment. `[CG NL.1]` *Don't say in comments what can be clearly stated in code.*

---

## Tooling Commitments

Tools are due diligence. They catch what slipped, and they are not how quality is produced — a codebase that needs its linter to be well-designed is not well-designed. That said, the build should refuse what the standard refuses.

| Tool | Configuration |
|------|--------------|
| Warnings | `-Wall -Wextra -Wpedantic -Wconversion -Wsign-conversion -Werror`. `-Werror=switch` is load-bearing on C++11 projects — see [mechanisms.md §2](mechanisms.md#2-closed-set-variation). Any per-site disable carries a comment. |
| Sanitizers | UBSan and ASan in at least one configuration. TSan once concurrency exists. Findings block merge. |
| Static analysis | `clang-tidy` with `bugprone-*`, `cert-*`, `cppcoreguidelines-*`, `performance-*`, `readability-*`. Project-level disables live in `.clang-tidy`, one comment per disable. |
| Formatting | `clang-format`, decided once per project. Baseline: `BasedOnStyle: Google`, `IndentWidth: 4`, `ColumnLimit: 100`. |
| Build system | CMake by default. Alternatives permitted with a stated reason. |
| Standard | Declared in the top-level build config. Reaching for a feature from a later standard than declared is a bug. |

Per-project, not standard-level: clang-tidy disables, formatting details beyond the baseline, build system, test framework, library layout.

---

## Divergences From The Core Guidelines

Every deliberate difference, with its reason. Nothing silent.

| CG rule | Our position | Reason |
|---------|-------------|--------|
| `[CG I.6]` *Prefer `Expects()` for preconditions*, `[CG I.8]` *Prefer `Ensures()`* | Concept adopted, GSL dependency declined. Preconditions are made unrepresentable by a [wrapper type](#pattern-wrapper-type-for-preconditions) where structural, and `assert`ed otherwise. | A third-party dependency in an FFI kernel is not worth two macros. `std::span` — the GSL facility with real value — is in C++20. |
| `[CG I.12]` *Declare a pointer that must not be null as `not_null`*, `[CG F.23]` | Documented and asserted rather than typed. | Same GSL reason. |
| `[CG ES.107]` *Don't use `unsigned` for subscripts, prefer `gsl::index`* | Use a signed type for arithmetic per `[CG ES.102]`; no `gsl::index`. | Same GSL reason. |
| `[CG E.2]`, `[CG I.10]` — exceptions as the general failure mechanism | Exceptions are for genuinely exceptional conditions. Routine fallible operations return a result type. Exceptions are forbidden in real-time loops and never cross the FFI un-translated. | Latency determinism and the FFI seam. The CG assumes neither constraint. |
| `[CG NL.10]` *Prefer `underscore_style`* — offered as a preference | Mandated machine-wide, along with `PascalCase` types and `kPascalCase` constants. | The FFI rule requires names to cross unchanged; that is unachievable if case is a per-project choice. |
| `[CG SF.1]` *Use `.h` for interface files* | `.hpp` for C++ headers. | Distinguishes C++ headers from C headers at a glance in a mixed FFI tree. |
| `[CG T.10]` *Specify concepts for all template arguments* | Tier 2, gated on C++20. | Concepts do not exist earlier; a `static_assert` carries the same information. |

Where this document is silent and the Core Guidelines are not, the Core Guidelines apply.

---

## Provenance

Core Guidelines citations were verified verbatim against upstream on **2026-07-29**:

```
https://raw.githubusercontent.com/isocpp/CppCoreGuidelines/master/CppCoreGuidelines.md
```

The Core Guidelines are a living document; rule numbers may drift. When a citation stops resolving, re-verify upstream and correct it rather than dropping it.
