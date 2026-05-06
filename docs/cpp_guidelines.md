# QPrime C++ Coding Convention

**Status:** Standard | **Version:** 1.0 | **Scope:** all C++ in QPrime / TenneCNC projects.

This document is short on purpose. It encodes the engineering values that produce code worth trusting, plus eight rules that fix specific classes of weakness common in C++ codebases that grew without discipline.

The values come first because rules can't enumerate every situation. When the rules don't cover a case, the values say what to do.

---

## Values

These are the stances all rules below are derived from. When you encounter a case the rules don't address, return here.

**Boring is a feature.** The reader's cognitive budget is finite. Code that uses two language features instead of seven, idiomatic patterns instead of clever ones, and explicit names instead of compressed ones is *better* even when it's longer. Default to the most boring construction that works. Cleverness is a cost paid by every future reader; pay it only when the alternative is genuinely worse. The test for whether something is appropriately boring: can the next reader understand what this does without leaving the file?

**Failure modes are visible.** Errors don't get swallowed. Invalid states are unrepresentable when possible, asserted when not. A reader should answer "what happens when this goes wrong" by looking at the code, not by reading minds. Silent wrong-answers are the worst possible failure mode in any system whose output drives physical action.

**Ownership is obvious.** Who owns this memory, this resource, this lifetime, this invariant — should be answerable in under five seconds by anyone reading the code. RAII by default. Raw pointers only as non-owning observers with documented lifetimes. Shared ownership only when ownership is genuinely shared.

**Defensive at boundaries, trusting inside.** Validate at function parameters from outside the module, at deserialization, at FFI. Trust internal invariants once established. Defending against your own code's correctness at every call site produces noise that hides the real defenses. Wrapper types (Rule 6) are the preferred way to convert "I should check this" into "the type system already did."

**Determinism is the default.** Same input must produce the same output. C++ has more sources of non-determinism than most languages — undefined behavior, signed overflow, hash and unordered-container iteration order, link order, thread interleaving, uninitialized memory. None of these may leak into output. Determinism is what makes golden-file testing meaningful and reproducible builds possible.

**The compiler is your ally.** Make wrong code not compile when you can. Strong types over primitives where they matter. `enum class` over loose enums. `[[nodiscard]]` on functions whose return value matters. `constexpr` where it can be. `noexcept` where it should be. `std::variant` + `std::visit` to make exhaustiveness checked at compile time.

---

## Ownership and Lifetime

**Default:** RAII. Resources are owned by objects whose destructors release them. Manual `new`/`delete` outside FFI boundaries is a code smell.

**Owned heap allocation:** `std::unique_ptr<T>`. Transfer ownership by move; never by raw pointer.

**Shared ownership:** `std::shared_ptr<T>` only when ownership is *actually* shared (multiple independent owners with no clear primary). If one owner is primary and others observe, the primary holds `unique_ptr` and others hold a non-owning view. Reflexive `shared_ptr` use is a sign the ownership wasn't thought through.

**Non-owning views:** raw pointer or reference, with a comment documenting expected lifetime if non-obvious. `std::span<const T>` for sequences. **Spans are for the duration of the call, never stored** — storing a span is a use-after-free waiting to happen.

**Pass-by convention:**
- Pass by value: small types, types you'll modify locally, types you'll move from
- Pass by `const T&`: large types you'll only read
- Pass by `T&`: out-parameters (rare; prefer return values or struct returns)
- Pass by pointer: when null is a meaningful value (otherwise use reference)

---

## Error Handling

Three modes, each with a distinct use:

- **Exceptions** — genuinely exceptional conditions (allocation failure, invariant violation, unrecoverable corruption). Never for routine validation.
- **Result types** — `std::optional<T>` when absence is the only failure mode; `std::expected<T, E>` when failure carries information. The default for recoverable failures.
- **Assertions** — "this can't happen" preconditions that should already be guaranteed by upstream validation. Use sparingly; if you assert often, the design wants a wrapper type (Rule 6).

### Error Message Format

When an exception or error message is constructed, it must include four parts:

1. **What failed** — the class, function, or subsystem
2. **What field** — the specific parameter or invariant
3. **What constraint was violated** — the rule that was broken
4. **Actual value** — what was received

```cpp
// Wrong
throw std::invalid_argument("invalid width");

// Right
throw std::invalid_argument("SheetConfig: width_mm must be > 0, got -3.5");
```

The same format applies to error payloads in `std::expected<T, E>`, log messages, and structured warnings. AI-generated C++ defaults to `throw std::runtime_error("invalid input")` without prompting; this rule fixes that.

### Failure Semantics by Layer

Different layers handle failures differently. The principle: failures become less fatal as you move outward from the lowest-level computation.

| Layer | On Failure | Mechanism |
|-------|-----------|-----------|
| FFI boundary | Translate to host language | C++ exception → Python exception via pybind11; never let an exception cross unhandled |
| Module public API | Return result type | `std::expected<T, E>` for recoverable; throw for invariant violations only |
| Internal helpers | Trust contracts | Assume validated input; assert preconditions if defensible cheaply |
| Real-time loop | Log + continue | Errors recorded in trace structure, surfaced at scan boundary, never thrown |
| Real-time loop boundary | Inspect trace | Caller examines accumulated errors and decides whether to halt |

The parser (or equivalent input handler) is strict: malformed input is not recoverable. The orchestrator (or equivalent top-level) is lenient about per-item failures but strict about safety constraints.

### Exceptions Policy

The QPrime default is *exceptions enabled, used sparingly*.

- Exceptions are permitted at module boundaries and for genuinely exceptional conditions (allocation failure, invariant violation, FFI-translated host-language exceptions).
- Exceptions are **forbidden in real-time loops** (see Real-Time section) and in any code path with hard latency requirements.
- Exceptions **do not cross FFI boundaries**. C++ exceptions are caught at the boundary and translated into the host language's error mechanism (Python exceptions via pybind11, error codes for C consumers, etc.). An exception escaping into a foreign-language frame is a bug.
- `-fno-exceptions` is not the project default but is permitted on a per-module basis when latency, binary size, or FFI requirements justify it. A module that disables exceptions states this explicitly in its top-level header.
- Routine validation failures use result types (`optional`, `expected`), not exceptions. The throw-as-control-flow pattern is forbidden.

If a function might throw, it should not be `noexcept`. If a function genuinely cannot throw, mark it `noexcept` so the compiler and reader both know.

---

## Real-Time and Coroutine Contexts

Some code runs in contexts where the rules above need adjustment. The two most common in QPrime work:

**Real-time loops** (scan loops, audio callbacks, interrupt handlers). Exceptions in real-time loops produce non-deterministic timing and are forbidden. Errors get logged into a trace or status structure and surface at boundaries between scans, not as control-flow disruptions inside them. Memory allocation is similarly suspect — pre-allocate where possible. `std::vector::push_back`, `std::string` operations that may reallocate, and any operation that calls into `malloc` are scrutinized.

**Coroutines.** Never pass by reference into a coroutine that may suspend. The reference will dangle if the caller's frame is destroyed before resumption. Pass by value into coroutines, always. Lambda captures into coroutines follow the same rule: capture by value, not by reference, unless the lambda's lifetime is provably bounded by the captured object's.

Awaitables are non-owning by default; they observe state managed elsewhere. If an awaitable needs to outlive the awaiting frame, that's an ownership question that needs an explicit answer, not an assumption.

For deep `co_await` chains, use symmetric transfer (returning a `coroutine_handle<>` from `await_suspend`) to prevent stack growth. This matters for any pipeline more than two or three coroutines deep.

---

## Concurrency

For ordinary multithreading (worker pools, background tasks, producer/consumer patterns) outside the real-time and coroutine contexts above:

**Default to single-threaded by contract.** A type or module is not thread-safe unless it says so. The default assumption for any class is that concurrent access is the caller's problem, not the class's. This eliminates a category of overhead (locks, atomics) from code that doesn't need it.

**When concurrency is needed, prefer structured patterns over shared mutable state.** Worker pools with task queues, message-passing between threads, immutable snapshots passed across thread boundaries — all preferable to multiple threads mutating the same object under a lock. The latter works but produces code that is hard to reason about and easy to break with later changes.

**Synchronization primitives, in order of preference:**
- Pure functions and immutable data — no synchronization needed
- `std::atomic<T>` for primitive shared state (counters, flags, single-pointer handoff)
- `std::mutex` + `std::lock_guard` / `std::unique_lock` for compound state
- `std::shared_mutex` only when the read-heavy pattern is measured, not assumed
- Condition variables for explicit wait/notify; prefer `std::latch` and `std::barrier` (C++20) where they fit

**No thread-local globals.** Thread-local storage hides ownership and lifetime in ways that compound badly across modules. If thread-local state is genuinely required, it lives in an explicit per-thread context object passed into the functions that need it.

**Forbidden patterns:**
- `volatile` for thread synchronization (use atomics)
- Double-checked locking without atomics (use `std::call_once` or atomics with proper memory ordering)
- Raw `std::thread` ownership scattered through application code (wrap in a class with a clear lifecycle)
- Sleep-based synchronization (`std::this_thread::sleep_for` to wait for a condition — use a condition variable or latch instead)

If a module's concurrency model isn't obvious from its API, document it in one or two sentences at the top of the header.

---

## Testing

Rule 8 (golden-tested IR) is the contract layer. The everyday testing discipline beneath it:

**Test at the level the logic lives.** Unit tests target the function or class that contains the behavior, not the full pipeline. Pipeline tests exist for integration; they're slow and brittle as the unit of correctness. Most tests should hit the IR or the helper function, not the end-to-end flow.

**Don't test the language.** A test that asserts `std::optional<T>` returns `std::nullopt` when default-constructed, or that a `constexpr` value is computed at compile time, is testing the standard library, not your code. Test the behavior your code adds.

**Semantic equivalence in round-trips.** Serialization round-trip tests assert `parse(serialize(model)) == model`, not that `serialize(parse(text)) == text`. Whitespace, key order, and equivalent representations may legitimately differ.

**No duplicate coverage.** Two tests asserting the same behavior over the same input is a defect, not defense in depth. Before adding a test file, check whether existing tests already cover what you're about to write.

**Test framework integration.** Tests live where the project's framework discovers them (Catch2, GoogleTest, doctest, per project choice). Don't add `int main()` runners, ad-hoc PASS/FAIL prints, or manual reporting that bypasses the framework — they're dead code in a discovered suite and mislead future contributors.

---

## Logging and Diagnostics

**No `std::cout` / `printf` in library code.** They belong in CLI entry points and one-off scripts, not in functions imported by other modules. The failure this rule prevents: a `printf` snuck into a deep helper for debugging, never removed, now spamming stdout every time the program runs.

**Use a structured logger** (spdlog, glog, or the project's chosen library) for runtime diagnostics. The logger respects level filtering, routing, and source-location formatting in ways `printf` does not.

**Level discipline:**

| Level | Use When |
|-------|----------|
| `TRACE` / `DEBUG` | Internal state useful during development (variable values, branch taken) |
| `INFO` | High-level progress milestones |
| `WARN` | Something unexpected but recoverable |
| `ERROR` | Something failed but the program continues |
| `FATAL` / `CRITICAL` | The program cannot continue |

`INFO` is for operators; `DEBUG` is for developers. Don't use `WARN` for expected situations.

**Real-time loops use trace structures, not loggers.** A real-time loop cannot afford the lock contention or formatting cost of a runtime logger. Errors and diagnostics in scan loops accumulate in a pre-allocated trace structure, surfaced at the scan boundary by the caller.

---

## Dependency Direction

**Imports flow downward.** Lower layers must not include from higher layers. If your validation layer includes from your renderer, or your data model includes from your CLI, the dependency is inverted.

```
Input/CLI  →  Parser  →  IR/Model  →  Validation  →  Backend/Output
   ↓            ↓           ↓             ↓               ↓
 (each layer may include from layers to its right, never to its left)
```

**A practical test:** if you delete a higher-level module, lower-level modules should still compile. If removing your CLI breaks your data model, you have a circular dependency.

**Adapter at the boundary.** When a higher layer's types are needed by a lower layer, introduce an adapter at the boundary rather than pulling the higher layer's headers downward. The data model exposes generic identifiers; the adapter maps those to renderer-specific types.

This is also how Rule 6 (preconditions in the type) interacts with layering: the wrapper type lives at the layer that owns the precondition, not at the layer that consumes the wrapped value.

---

## FFI Conventions

The boundary between languages is where each language's conventions disagree most. AI generation defaults to applying each language's local conventions, which produces a seam that doesn't survive the trip. These rules apply identically on both sides of the FFI.

**Names cross unchanged.** A function called `parse_layout` in Python pairs with `parse_layout` in C++. No `parseLayout`, no `parse_layout_t`, no `_parse_layout_impl` on the C++ side that's only called from Python. The Naming Vocabulary applies to both languages.

**Validation is the calling side's job.** The caller validates inputs before crossing the boundary. The called side may assert preconditions cheaply but does not re-validate as a defensive measure. This matches the "defensive at boundaries, trusting inside" value: the FFI boundary is the boundary, not every function on the called side.

**Errors translate at the boundary, not in flight.** C++ exceptions become Python exceptions exactly once, at the pybind11 (or equivalent) layer. C++ code does not catch exceptions to translate them mid-stack. Python code does not wrap pybind11-translated exceptions in additional layers. Errors keep their original type and message; the boundary layer maps the type, not the content.

**Absence maps to absence.** `std::optional<T>` ↔ `Optional[T]` (or `T | None`). `std::nullopt` ↔ `None`. NaN does not appear in either direction (Rule 3); empty collections do not signal failure (use the result type). When a value is genuinely optional, both sides see it as optional.

**Units survive the trip.** If C++ takes millimeters, Python passes millimeters. If C++ takes seconds, Python passes seconds. Conversion happens at the *outer* boundary (user input, file parsing) and never at the FFI seam — converting at the FFI is a category error that produces double-conversion bugs the moment a caller is added.

**Ownership is explicit.** Objects passed across the FFI by value are copied; objects passed by reference are non-owning views with documented lifetime. C++ does not return raw pointers to host-language code; ownership transfers via `std::unique_ptr` (which pybind11 handles) or by-value copy. Python does not pass mutable objects expecting C++ to retain them past the call.

**The IR is the contract.** When the two languages share data structures (the move IR, parsed layouts, plan output), there is exactly one schema, defined in one place, and both sides agree on it. Rule 8 (golden-tested IR) applies across the FFI: a change to the shared schema is a versioned change requiring both sides and the goldens to move together.

---

## Tooling Commitments

A standard that doesn't say what the build refuses leaves the most consequential decisions implicit. These are the QPrime defaults.

**Enforcement is required.** Every project has an automated gate that, at minimum, builds with warnings-as-errors, runs the test suite, runs sanitizers in at least one configuration, and runs clang-tidy. A change that doesn't pass the gate doesn't merge.

The QPrime mechanism is **pre-commit hooks** — checks colocate with the code, which lets both the human and AI collaborators run, diagnose, and fix them in a tight loop. CI is appropriate when a project grows beyond solo work; until then it's overhead without payoff.

**Warnings:** `-Wall -Wextra -Wpedantic -Werror`. New projects start with warnings as errors. Disabling a specific warning requires a comment explaining why.

`-Wconversion` is recommended but not required at the QPrime level. Enable it on new projects; use judgment on existing code where the noise-to-signal ratio may be unfavorable.

**Sanitizers:** UBSan and ASan are run in CI for at least one build configuration. TSan is added when concurrency is introduced. Sanitizer findings block merge.

**Static analysis:** `clang-tidy` is run in CI with a project-defined ruleset. The QPrime baseline ruleset enables the `bugprone-*`, `cert-*`, `cppcoreguidelines-*`, `performance-*`, and `readability-*` checks, with project-level disables for specific rules that don't fit. The disables go in the project's `.clang-tidy` with a one-line comment per disable.

**Formatting:** `clang-format` with a project-level config. The config is decided once per project and not relitigated. The QPrime starter config (BasedOnStyle: Google, IndentWidth: 4, ColumnLimit: 100) is a reasonable default; deviations are project choices.

**Build system:** per-project. CMake is the default for cross-platform projects; alternatives are permitted when justified.

**Compiler:** projects target a specific C++ standard version (C++20 or C++23 for new work) and a specific minimum compiler version. Both are stated in the top-level build configuration. Reaching for a C++26 feature on a C++20 project is a bug, not a clever optimization.

**Per-project, not QPrime-level:** clang-tidy disables, clang-format details beyond the baseline, build system, library structure (header-only vs compiled), test framework. The QPrime standard names the dimensions; the project picks the values.

---

## Naming Vocabulary

Use the same verb for the same operation across the codebase. When a reader sees `parse_`, they should know exactly what kind of operation it is.

| Verb | Meaning | Example |
|------|---------|---------|
| `parse_*` | Text/bytes → structured data | `parse_config`, `parse_dimension` |
| `format_*` | Structured data → text/bytes | `format_output`, `format_report` |
| `resolve_*` | Simplify structure, expand references | `resolve_layout`, `resolve_template` |
| `*_to_*` | Convert between typed representations | `model_to_dto`, `ast_to_ir` |
| `validate_*` | Check correctness; throw or return error on failure | `validate_config`, `validate_bounds` |
| `build_*` | Construct complex object from parts | `build_pipeline`, `build_tool_db` |
| `load_*` | Read from disk or external source | `load_config`, `load_template` |
| `write_*` | Emit machine/file output | `write_output`, `write_report` |
| `render_*` | Emit visual/display output | `render_diagram`, `render_html` |
| `expand_*` | Parameterized instantiation | `expand_template`, `expand_macro` |
| `plan_*` | Compute execution sequence (for systems with planners) | `plan_pocket`, `plan_profile` |

For predicates and accessors:

| Pattern | Purpose |
|---------|---------|
| `is_*` / `has_*` | Boolean predicates returning `bool` |
| `try_*` | Operation that may fail; returns `std::optional<T>` or `std::expected<T, E>`. Pairs with Rule 6 wrappers — `ConvexPolygon::try_from` is the canonical example. |
| `get_*` | Accessor that cannot fail; precondition is the caller's responsibility |
| `find_*` | Search that may not find; returns `std::optional<T>` or iterator |
| `make_*` | Construct a value (often `std::make_unique`, `std::make_shared` style) |

---

## The Eight Rules

Each rule fixes a specific class of weakness common in C++ codebases that grew without explicit discipline. The examples below are drawn from a real CAM kernel; they illustrate the rule but are not the rule's only domain of application.

### 1. No stub implementations in the public surface

**Rule:** a function declared in a public header must do what its name claims. Unimplemented functions are deleted, not stubbed. If a caller needs the symbol to exist before the implementation lands, the function is `[[noreturn]]` and throws `std::logic_error("not implemented: <name>")`. The FFI binding for an unimplemented function is omitted entirely.

**Why:** a stub that returns `{}` is indistinguishable from a real function that produced an empty result.

### 2. Tagged unions are `std::variant`, not stringly-typed structs

A struct with a `std::string kind` field plus a grab-bag of optional payload fields is a compile-time-unchecked tagged union. Replace it with `std::variant`:

```cpp
struct Comment  { std::string text; };
struct SetRpm   { double rpm; };
struct Rapid    { double x, y, z; };
struct Cut      { std::optional<double> x, y, z, feed; };
// ...

using Move = std::variant<Comment, SetRpm, Rapid, Cut, /* ... */>;
```

Dispatch via `std::visit` with a lambda overload set, not `if (move.kind == "...")`. With variant, `std::visit` makes "added a new alternative, forgot to handle it somewhere" a compile error rather than a runtime surprise.

**Why:** stringly-typed dispatch can't be exhaustively checked.

### 3. No NaN sentinels — `std::optional<T>` for absence

NaN-as-absent is a category error: NaN is *invalid number*, not *no number*. Conflating the two means real NaN bugs (degenerate geometry, division by zero, uninitialized arithmetic) are indistinguishable from intentional absence, and absence leaks into arithmetic in ways that are surprising to debug.

**Rule:** absence is `std::optional<T>`. NaN is reserved for actual numeric NaN and is treated as a bug worth investigating, not a value with meaning. FFI bindings map host-language null/None to `std::nullopt`.

### 4. Collapse near-duplicate functions, parameterise by the difference

When two functions share more than half their bodies *and* a future change to that shared body would need to be made in both places, they collapse into one function with an explicit options struct.

The test is "would a future change need to co-evolve in both places" — accidental similarity that wouldn't co-evolve stays separate. Two functions with similar shape but different responsibilities should not be collapsed; two functions with identical responsibility differing only in a parameter should be.

```cpp
struct PlanOpts {
  enum class Strategy { A, B } strategy;
  bool include_finishing_pass;
};
Result plan(const Input&, const PlanOpts&);
```

**Why:** near-duplicates diverge silently — a bug fix in one is forgotten in the other.

### 5. Span-typed parameters, never `(T*, size_t)`

Sequence parameters are `std::span<const T>`. The type carries the length; callers don't.

```cpp
// No:
void process(const Vec2* path, size_t path_len);

// Yes:
void process(std::span<const Vec2> path);
```

Spans are call-scoped; storing a span is a lifetime bug. If the function needs to retain the data, copy into a `std::vector<T>`.

**At C interop boundaries** the foreign signature requires `(T*, size_t)`. Convert to a span immediately on entry:

```cpp
extern "C" int process_buffer(const Vec2* data, size_t length) {
  const std::span<const Vec2> path(data, length);
  // ... rest of function uses path, not (data, length)
}
```

### 6. Preconditions are named in the type

The name of a function may say "convex polygon" or "sorted range" or "non-empty buffer," but the type system doesn't know.

**Rule:** functions with input preconditions take a wrapper type that proves the precondition:

```cpp
class ConvexPolygon {
 public:
  static std::optional<ConvexPolygon> try_from(Polygon p);  // checks; returns nullopt if invalid
  const Polygon& points() const;
 private:
  explicit ConvexPolygon(Polygon p);
  Polygon points_;
};

Polygon inset(const ConvexPolygon& poly, double offset);  // can never receive a non-convex polygon
```

The check happens once, at the boundary, not inside every algorithm that wants to assume the precondition.

This is a general pattern. Other preconditions that deserve the same treatment when encountered: closed paths, non-self-intersecting curves, monotonic sequences, oriented loops with known winding, sorted ranges, non-empty containers.

### 7. No dead branches, no commented-out code, no stale TODOs, no magic numbers

Identical-branch conditionals, unused parameters cast to `(void)`, `// TODO` markers older than the current branch, commented-out code without a written reason, and inline numeric literals with no name attached are all signal that nobody is reading the file end-to-end.

**Rule:** code review (human or AI) explicitly checks for these patterns. Any of them blocks merge.

```cpp
// No
if (margin < 10.0) { ... }

// Yes
constexpr double kMinMarginMm = 10.0;
if (margin < kMinMarginMm) { ... }
```

Magic numbers in geometry, timing, and limit checks are the most common offenders. A `constexpr` (or `inline constexpr` in a header) at the top of the file, or in a dedicated constants header for cross-module values, fixes it.

Exceptions: `(void)param;` is fine on a virtual override or interface implementation where the parameter is mandated by the signature — never on a leaf function. Deliberate dead code (feature flag, debug toggle, documented placeholder) must carry a comment explaining its presence. Trivially obvious numeric literals (`0`, `1`, array indices, loop bounds tied to a local container) don't need names.

### 8. The contract is the IR, and the IR is golden-tested

Any computation that produces structured output — toolpaths, plans, schedules, traces, generated code — has an intermediate representation that is the contract between producer and consumer. That IR must be golden-tested.

**Rule:** every change to a function that produces IR must be accompanied by either:

(a) **no change to existing goldens** — proving the change is a refactor; or
(b) a deliberate snapshot regeneration with the diff explained in the commit message.

Adding a new alternative to the IR is a versioned change: define, expose across the FFI, document, regenerate goldens — in that order.

---

## Regression Traps

Patterns that look like improvements but violate the values or rules above. Each is a thing AI generation reaches for by default; each is wrong in this codebase. Listed by name so they can be flagged at review time.

| Trap | Why It's Wrong |
|------|----------------|
| Adding inheritance hierarchies for variants | Rule 2 — `std::variant` is the variant type; inheritance is for shared implementation, not variation |
| Reaching for `std::shared_ptr` to avoid thinking about ownership | Ownership value — shared ownership is a deliberate choice, not a default |
| `noexcept` on every function because it's "free" | Exceptions Policy — `noexcept` is a contract; on a function that calls anything that might throw, it converts an exception into a `std::terminate` |
| `auto` for everything because it's modern | Boring is a feature — `auto` hides the type; use it when the type is obvious from the right-hand side, not when it would help the reader to see the type |
| Templates as the first reach for parameterization | "Does Not Require" — templates are a tool for genuine generic code, not a default for any function with two callers |
| Returning `{}` instead of `std::optional` to signal absence | Rule 3, Rule 6 — empty result is indistinguishable from "valid input produced nothing"; absence is `std::optional`, failure is `std::expected` |
| Catching exceptions to convert to error codes mid-stack | Exceptions Policy — translation happens at the FFI boundary, not at every layer; catch-and-rethrow is noise |
| Storing a `std::span` as a member | Ownership — spans are call-scoped views; storing one is a use-after-free waiting to happen |
| Adding a `std::mutex` to a class to make it "thread-safe" | Concurrency — single-threaded by contract is the default; a mutex without a documented threading model is cargo-culting |
| Replacing a string-typed dispatch with `enum class` but keeping the if/elif chain | Rule 2 — the enum is half the fix; `std::variant` + `std::visit` is the whole fix |

---

## What This Convention Deliberately Does Not Require

- **No naming bikeshed.** `snake_case` for functions, `PascalCase` for types, `SCREAMING_SNAKE_CASE` for constants. Pick once at the project level if it's not already chosen; don't relitigate.
- **No header-file zealotry.** `#pragma once` is fine. Include-what-you-use is a goal, not a gate.
- **No comment quotas.** Comments are reserved for non-obvious geometry, non-obvious mathematical identities, and load-bearing assumptions a reader couldn't infer from the code. Don't write docstrings in C++; don't write running-prose explanations of what the next three lines do.
- **No template metaprogramming.** Reach for templates when the alternative is genuinely worse, not as a default. A function that takes `const Polygon&` does not need to take `template<Range R>`.
- **No premature abstraction.** Inheritance hierarchies, CRTP, policy classes — none of these appear unless the code already has at least two concrete cases that justify the abstraction. The first instance is a function; the second instance is when you decide whether it's a pattern.
- **No exotic C++.** Modules, contracts, reflection — when they're broadly available and tooling-supported, they'll earn their place. Until then, prefer constructs that the entire toolchain (compiler, debugger, IDE, AI assistant) handles confidently.

---

## Adoption

For a new codebase: everything applies immediately. There is nothing to migrate.

For an existing codebase, work toward the rules in dependency order:

1. Rule 1 (delete stubs) — mechanical, no semantic risk.
2. Rules 2 + 3 (variant + optional) — touches the FFI boundary; land together.
3. Rule 4 (collapse near-duplicates).
4. Rules 5–7 — folded into normal feature work as files are touched.
5. Rule 8 — the new default on the next change to any IR-producing function.

Tooling adopts in parallel: warnings-as-errors first, sanitizers second, clang-tidy with a small initial ruleset third. The goldens are the safety net — if they don't change, the refactor is correct.

---

## Why This Convention Exists

C++ codebases drift toward incoherence more aggressively than codebases in most other languages — multiple paradigms, decades of accumulated idioms, no opinionated default style. Without explicit discipline, a C++ project reflects the union of every contributor's habits. This convention is the discipline: values that generalize, rules that can be checked at review time, tooling that enforces both at build time.

The test for whether the standard is working: an AI session writing new C++ under it produces code that looks like the rules without anyone having to invoke them by name.
