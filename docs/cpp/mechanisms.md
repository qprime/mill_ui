# C++ Mechanism Matrix

**Status:** Standard | **Version:** 1.0 | **Scope:** all C++ in QPrime / TenneCNC projects.
**Companion to:** [conventions.md](conventions.md)

This document is the single home for version-specific facts. [conventions.md](conventions.md) states *design intent* and never names a version-specific type; this document says *which mechanism expresses that intent* in each supported standard.

Supported standards are grouped where the grouping does not change design guidance:

| Group | Covers | Appendix |
|-------|--------|----------|
| **C++11** | C++11, C++14 | [std/cpp11.md](std/cpp11.md) |
| **C++17** | C++17 | [std/cpp17.md](std/cpp17.md) |
| **C++20** | C++20, C++23 | [std/cpp20.md](std/cpp20.md) |

A project declares its standard once in its build configuration. Reaching for a mechanism from a later column than your project declares is a bug, not an upgrade.

---

## How to read this document

Each capability below answers one question: *given the intent, what do I write?*

The **Intent** row is the rule — it comes from [conventions.md](conventions.md) and never changes. The standard columns give the mechanism. Where a cell says *no mechanism*, the intent still holds and the row states how to satisfy it without library support.

An older mechanism used on a newer project is a defect the same way a newer mechanism on an older project is: the column your project declares is the column you write.

---

## 1. Absence

**Intent:** absence is represented explicitly, never encoded in a sentinel value. NaN is *invalid number*, not *no number*; `-1` is an integer, not a missing index.
**Tier:** 1 (intent) / 2 (mechanism)

| C++11 | C++17 | C++20 |
|-------|-------|-------|
| No standard mechanism. Two permitted forms: a dedicated `Optional<T>`-alike in the project's support header, or a `bool`-returning `try_*` function with a reference out-parameter at a documented boundary. Pick one per project; do not mix. | `std::optional<T>` | `std::optional<T>` |

`std::optional` is not a substitute for a result type. Absence means *there is legitimately nothing here*. Failure that carries a reason belongs in [Failure](#5-failure).

**FFI:** `std::optional<T>` ↔ `Optional[T]`, `std::nullopt` ↔ `None`. NaN never crosses.

---

## 2. Closed-set variation

**Intent:** a value that is one of a fixed set of alternatives is represented so that the compiler catches a missing case. Adding an alternative must break compilation at every site that must handle it — not fall through silently.
**Tier:** 1 (intent) / 2 (mechanism)

| C++11 | C++17 | C++20 |
|-------|-------|-------|
| `enum class` tag + `switch` with **no `default` label**, compiled with `-Werror=switch`. A new enumerator becomes a compile error at every switch. Payload lives in a struct per alternative; the tagged aggregate is documented as a unit. | `std::variant` + `std::visit` with an exhaustive overload set | `std::variant` + `std::visit` |

The C++11 form is not a lesser pattern — it is the same guarantee obtained from the warning system rather than the type system. What is forbidden in every standard is an `enum` paired with an if/else-if chain, which obtains no guarantee at all.

**Anti-pattern in every standard:** a `std::string kind` field with optional payload members. That is a tagged union with no checking whatsoever. See [conventions.md — Trap: stringly-typed dispatch](conventions.md#trap-stringly-typed-dispatch).

**`[CG C.181]`** *Avoid "naked" `union`s.* **`[CG C.182]`** *Use anonymous `union`s to implement tagged unions.*

---

## 3. Ownership

**Intent:** every allocation has exactly one owner, identifiable from the declaration. A raw pointer is always non-owning.
**Tier:** 1

| Need | C++11 | C++17 | C++20 |
|------|-------|-------|-------|
| Exclusive ownership | `std::unique_ptr<T>` | same | same |
| Construct owned | `std::make_unique` (C++14; C++11 writes the `unique_ptr(new T(...))` form once, in a factory) | `std::make_unique` | `std::make_unique` |
| Shared ownership *(only when genuinely shared)* | `std::shared_ptr<T>` | same | same |
| Break a `shared_ptr` cycle | `std::weak_ptr<T>` | same | same |
| Non-owning observer | `T*` or `T&` | same | same |
| Non-null pointer | Document it; `assert` at entry | same | same |

**Banned in every standard:** `std::auto_ptr` (removed in C++17, broken copy semantics in C++11 — never use it), owning raw pointers, `malloc`/`free` in C++ code, `new`/`delete` outside a resource-management function.

**`[CG R.20]`** *Use `unique_ptr` to express exclusive ownership.* **`[CG R.21]`** *Prefer `unique_ptr` over `shared_ptr` unless you actually need to share ownership.* **`[CG R.3]`** *A raw pointer (a `T*`) is non-owning.* **`[CG R.11]`** *Avoid calling `new` and `delete` explicitly.*

---

## 4. Sequences

**Intent:** a parameter denoting a sequence carries its own bounds. The lifetime contract is in the type, not in a comment; the bounds check is not the caller's job to remember.
**Tier:** 1 (intent) / 2 (mechanism)

| C++11 | C++17 | C++20 |
|-------|-------|-------|
| An iterator pair, or `const std::vector<T>&` when the caller genuinely owns a vector. A `(T*, size_t)` pair is permitted **only** at an `extern "C"` boundary, and is converted to a pair/vector on entry. | Same as C++11. `std::string_view` is available and is the correct type for non-owning string parameters. | `std::span<const T>` for read, `std::span<T>` for write. `std::string_view` for strings. |

**In every standard:** a non-owning view is never stored as a class member. If the class must retain the data, it stores a `std::vector<T>`. See [conventions.md — Trap: stored view](conventions.md#trap-stored-view).

**`[CG F.24]`** *Use a `span<T>` or a `span_p<T>` to designate a half-open sequence.* **`[CG I.13]`** *Do not pass an array as a single pointer.*

---

## 5. Failure

**Intent:** a function that can fail says so in its signature, and the failure carries whatever the caller needs to act. Failure is never silently absorbed and never returned as a valid-looking value.
**Tier:** 1 (intent) / 2 (mechanism)

| Failure mode | C++11 | C++17 | C++20 |
|--------------|-------|-------|-------|
| Absence is the only failure | see [Absence](#1-absence) | `std::optional<T>` | `std::optional<T>` |
| Failure carries information | Project result type, or exception at a module boundary | Project result type, or exception | `std::expected<T, E>` (C++23); project result type on C++20 |
| Genuinely exceptional (allocation failure, invariant violation, corruption) | exception | exception | exception |
| "Cannot happen" precondition | `assert` | `assert` | `assert` |

`std::expected` is C++23. A C++20 project uses a project-local result type and migrates when it moves to 23 — it does not pull in a third-party `expected`.

**Exception-free modules** (`-fno-exceptions`, real-time, some FFI targets) follow the CG's own guidance: **`[CG E.25]`** *If you can't throw exceptions, simulate RAII for resource management.* **`[CG E.26]`** *If you can't throw exceptions, consider failing fast.* **`[CG E.27]`** *If you can't throw exceptions, use error codes systematically.* "Systematically" is the operative word — one convention per module, stated in its top-level header.

**`[CG E.1]`** *Develop an error-handling strategy early in a design.* **`[CG E.3]`** *Use exceptions for error handling only.* **`[CG E.14]`** *Use purpose-designed user-defined types as exceptions (not built-in types).*

---

## 6. Immutability

**Intent:** data is immutable unless there is a reason for it to change. Compile-time-known values are computed at compile time.
**Tier:** 1

| Need | C++11 | C++17 | C++20 |
|------|-------|-------|-------|
| Object that never changes | `const` | `const` | `const` |
| Member function that does not mutate | `const` | `const` | `const` |
| Compile-time constant | `constexpr` | `constexpr`, `inline constexpr` for header constants | same |
| Compile-time function | `constexpr` (single-return in C++11; relaxed in C++14) | `constexpr` | `constexpr`, `consteval` when compile-time evaluation is *required* |
| Immutable class member | `const` member, or private + accessor | same | same |

`inline constexpr` at namespace scope in a header requires C++17. A C++11 project puts header constants in an anonymous namespace or a function returning the value.

**`[CG Con.1]`** *By default, make objects immutable.* **`[CG Con.2]`** *By default, make member functions `const`.* **`[CG Con.3]`** *By default, pass pointers and references to `const`s.* **`[CG Con.4]`** *Use `const` to define objects with values that do not change after construction.* **`[CG Con.5]`** *Use `constexpr` for values that can be computed at compile time.* **`[CG P.10]`** *Prefer immutable data to mutable data.*

---

## 7. Invariants and preconditions

**Intent:** a type with an invariant establishes it at construction and cannot exist in a state that violates it. A function's structural preconditions are visible in its signature.
**Tier:** 1

| Need | C++11 | C++17 | C++20 |
|------|-------|-------|-------|
| Establish an invariant | Constructor validates; throws on invalid input | same | same |
| Non-throwing construction | Static `try_from` returning the project optional | Static `try_from` returning `std::optional<T>` | same |
| Structural precondition on a function | Wrapper type in the signature | same | same |
| Cheap "cannot happen" check | `assert` | `assert` | `assert`; `[[assume]]` in C++23 only where measured |
| Compile-time precondition | `static_assert` | `static_assert` | Constraints / `requires` |

We do **not** take the GSL dependency. `Expects()`/`Ensures()` are borrowed as a *concept*: preconditions are stated explicitly and checked with `assert`, or — better — made unrepresentable by a wrapper type. A project wanting the macro names may define them locally in one header.

**`[CG C.2]`** *Use `class` if the class has an invariant; use `struct` if the data members can vary independently.* **`[CG C.40]`** *Define a constructor if a class has an invariant.* **`[CG C.41]`** *A constructor should create a fully initialized object.* **`[CG C.42]`** *If a constructor cannot construct a valid object, throw an exception.* **`[CG I.5]`** *State preconditions (if any).*

---

## 8. Special members and value semantics

**Intent:** copying, moving, and destruction are a deliberate decision, stated once, consistently.
**Tier:** 1

| Need | C++11 | C++17 | C++20 |
|------|-------|-------|-------|
| Default (no resources owned directly) | Declare nothing — rule of zero | same | same |
| Suppress a default operation | `= delete` | same | same |
| Request a default explicitly | `= default` | same | same |
| Move that must not throw | `noexcept` move ctor/assign | same | same |
| Comparison | Write `==`/`<` by hand, symmetric and `noexcept` | same | `= default` on `operator==`; `operator<=>` for ordering |

**Rule of zero is the default in every standard.** If you declare any one of copy ctor, copy assign, move ctor, move assign, or destructor, you declare or `= delete` all of them.

**`[CG C.20]`** *If you can avoid defining default operations, do.* **`[CG C.21]`** *If you define or `=delete` any copy, move, or destructor function, define or `=delete` them all.* **`[CG C.22]`** *Make default operations consistent.* **`[CG C.66]`** *Make move operations `noexcept`.*

---

## 9. Generic code

**Intent:** parameterize only where the code is genuinely generic. Constraints on template parameters are stated, not discovered by the reader in a wall of instantiation errors.
**Tier:** 2 (mechanism) / 3 (when to templatize at all)

| Need | C++11 | C++17 | C++20 |
|------|-------|-------|-------|
| Constrain a template parameter | `static_assert` in the body; SFINAE only where unavoidable | `if constexpr`, `static_assert` | Concepts and `requires` clauses |
| Compile-time branch | Tag dispatch or specialization | `if constexpr` | `if constexpr` |
| Variadic forwarding | `template<class... Ts>` + `std::forward` | same, plus fold expressions | same |
| Deduce class template args | Explicit factory function (`make_*`) | CTAD | CTAD |

On C++20 a template parameter without a concept is incomplete. On earlier standards a `static_assert` stating the requirement carries the same information.

**`[CG T.10]`** *Specify concepts for all template arguments.* **`[CG T.11]`** *Whenever possible use standard concepts.* **`[CG T.120]`** *Use template metaprogramming only when you really need to.*

---

## 10. Concurrency

**Intent:** the default for every type is single-threaded by contract. Concurrency is introduced deliberately and the model is documented.
**Tier:** 1 (default) / 2 (mechanism)

| Need | C++11 | C++17 | C++20 |
|------|-------|-------|-------|
| Shared primitive | `std::atomic<T>` | same | same |
| Compound shared state | `std::mutex` + `std::lock_guard` | + `std::scoped_lock` | same |
| Read-heavy (measured) | `std::mutex` (no `shared_mutex` until C++14/17) | `std::shared_mutex` | same |
| Wait / notify | `std::condition_variable` | same | `std::latch`, `std::barrier`, `atomic::wait` — prefer these |
| One-time init | `std::call_once`, or function-local `static` | same | same |
| Owned thread | `std::thread` behind a class that joins in its destructor | same | `std::jthread` |
| Pure functions, immutable data | nothing | nothing | nothing |

**Forbidden in every standard:** `volatile` for synchronization, double-checked locking without atomics, `sleep_for` to wait for a condition, raw `std::thread` ownership scattered through application code, thread-local globals.

---

## 11. Strings and formatting

**Intent:** text formatting is type-safe and does not go through a stream of side effects.
**Tier:** 2

| Need | C++11 | C++17 | C++20 |
|------|-------|-------|-------|
| Non-owning string parameter | `const std::string&` | `std::string_view` | `std::string_view` |
| Format a number | `std::ostringstream` (contained in one helper) or `snprintf` into a fixed buffer | same | `std::format` |
| Build a message | `std::string` concatenation, or one stream helper | same | `std::format` |

`printf`-family calls are not type-safe and are permitted only where a project has no `std::format` and a measured reason to avoid streams. On C++20 `std::format` is the answer and `ostringstream` in new code is a defect.

**Never in library code:** `std::cout` / `printf` as output. See [conventions.md — Logging](conventions.md#logging).

---

## 12. Enumerations

**Intent:** an enumeration is a distinct type, not an integer.
**Tier:** 1

| C++11 | C++17 | C++20 |
|-------|-------|-------|
| `enum class` always. Unscoped `enum` only to match a C API. | same | same |

`enum class` in every standard from C++11 onward. There is no version-dependence here; the row exists because unscoped `enum` remains legal and is still generated by habit.

---

## 13. Standard-specific bans

Mechanisms that are legal but wrong in the column where they appear.

| Banned | From | Use instead |
|--------|------|-------------|
| `std::auto_ptr` | C++11 | `std::unique_ptr` |
| `std::bind` | C++11 | lambda |
| `throw()` exception specification | C++11 | `noexcept` |
| `register`, `NULL`, `0` as pointer | C++11 | *(delete)*, `nullptr` |
| `std::random_shuffle` | C++11 | `std::shuffle` |
| `ostringstream` for number formatting | C++20 | `std::format` |
| `(T*, size_t)` parameter pair | C++20 | `std::span` |
| `enable_if` SFINAE for constraints | C++20 | concepts / `requires` |
| Compound assignment on `volatile` | C++20 | *(deprecated; use `std::atomic`)* |
| Third-party `expected` | any | project result type until C++23 |
| GSL dependency | any | concept borrowed; `std::span` covers the valuable part |

---

## Retrieval provenance

Core Guidelines citations in this document and in [conventions.md](conventions.md) were verified verbatim against the upstream source on **2026-07-29**:

```
https://raw.githubusercontent.com/isocpp/CppCoreGuidelines/master/CppCoreGuidelines.md
```

The Core Guidelines are a living document and rule numbers may drift. When a citation no longer resolves, re-verify against upstream and correct it here rather than dropping it.
