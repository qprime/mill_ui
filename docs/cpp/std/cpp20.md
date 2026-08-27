# C++20 / C++23 Appendix

**Covers:** C++20, C++23 | **Core:** [../conventions.md](../conventions.md) | **Matrix:** [../mechanisms.md](../mechanisms.md)

Read [conventions.md](../conventions.md) first. This appendix says what you write on a C++20 or C++23 project.

This is the target for new work. Every Tier 2 rule in the core document has its intended mechanism here, so there is no "obtain the guarantee some other way" — there is one right answer per capability, and writing an older idiom in new code is a defect rather than a compromise.

---

## What C++20 gives you over C++17

| Facility | Effect on the standard |
|----------|----------------------|
| `std::span<T>` | The answer for sequence parameters. [mechanisms.md §4](../mechanisms.md#4-sequences) |
| `std::format` | The answer for text formatting. `ostringstream` in new code becomes a defect. |
| Concepts, `requires` | Template parameters are constrained. `[CG T.10]` becomes mandatory. |
| `operator<=>`, defaulted `operator==` | Comparison without six hand-written operators. |
| Designated initializers | What makes [params structs](../conventions.md#pattern-params-struct) read well. |
| `constinit`, `consteval` | Compile-time evaluation that is *required* rather than merely permitted. |
| `std::jthread`, `std::latch`, `std::barrier`, `std::atomic::wait` | The concurrency vocabulary the core document prefers. |
| Ranges | Composable algorithms without intermediate containers. |
| `[[likely]]`, `[[unlikely]]` | Branch hints, once measured. |
| `std::numbers` | `std::numbers::pi` rather than a local constant or `M_PI`. |
| Coroutines | See [Coroutines](../conventions.md#coroutines) in the core document. |

**C++23 adds**, and use them if the project declares 23: `std::expected`, `std::print`, `std::mdspan`, `std::flat_map`, `[[assume]]`.

---

## The rules that change

### Sequences are `std::span`

```cpp
double path_length_mm(std::span<const Vec2> path);
void smooth_in_place(std::span<Vec2> path);
```

A `const std::vector<T>&` parameter is now over-constrained — it forces the caller to hold a `vector` specifically. A `(T*, size_t)` pair is a defect outside an `extern "C"` boundary, where it converts on entry:

```cpp
extern "C" int process_buffer(const Vec2* data, size_t length) {
    const std::span<const Vec2> path(data, length);
    // body uses path only
}
```

**Never store a span as a member.** [Trap: stored view](../conventions.md#trap-stored-view).

### Formatting is `std::format`

```cpp
throw std::invalid_argument(
    std::format("Tool: diameter_mm must be > 0, got {}", diameter_mm));

moves.push_back(make_comment(
    std::format("pocket_spiral so={:.3f} sd={:.3f} depth={:.3f}",
                step_over_mm, step_down_mm, std::abs(depth_mm))));
```

Type-safe, no stream state, no `setprecision` leaking into the next call. `std::ostringstream` for number formatting in new code is a defect on this standard; a project-local `format_fixed` helper that wraps `ostringstream` should be deleted in favour of `std::format` directly.

`std::print` (C++23) for CLI output — still never in library code. See [Logging](../conventions.md#logging).

### Templates are constrained

An unconstrained template parameter is incomplete. `[CG T.10]`

```cpp
template <std::floating_point T>
T lerp(T a, T b, T t);

template <std::ranges::input_range R>
    requires std::same_as<std::ranges::range_value_t<R>, Vec2>
double total_length_mm(const R& path);
```

Prefer standard concepts to hand-written ones. `[CG T.11]` A hand-written concept must have meaningful semantics, not merely check for the presence of a member. `[CG T.20]`

This does not make templates a default — [Trap: premature template](../conventions.md#trap-premature-template) still holds. It means that *when* you write one, the constraint is part of the signature.

### Comparison is defaulted

```cpp
struct Vec2 {
    double x = 0.0;
    double y = 0.0;
    bool operator==(const Vec2&) const = default;
};
```

For ordering, `operator<=>`. Do not hand-write six comparison operators.

**Floating-point caution:** defaulted `==` on a struct of doubles is exact comparison. For geometry that is usually not what you want — provide a named tolerance predicate instead, and let `==` mean bitwise-equal or omit it entirely.

```cpp
bool approx_equal(const Vec2& a, const Vec2& b, double tol_mm);
```

### Designated initializers make params structs read well

```cpp
plan_pocket(face, tool, PocketParams{
    .step_over_mm = 6.0,
    .step_down_mm = 2.0,
    .safe_z_mm = 5.0,
    .ramp_angle_deg = 30.0,
    .strategy = PocketStrategy::Spiral,
});
```

This is the payoff for [Pattern: params struct](../conventions.md#pattern-params-struct). C++ has no keyword arguments; this is as close as the language gets, and it is close enough that a long parameter list has no excuse here.

Note the C++ rule: designated initializers must appear **in declaration order**, and you may skip fields but not reorder them.

### Informative failure is `std::expected` — on C++23

```cpp
std::expected<Toolpath, PlanError> plan(const Layout& layout);
```

**On C++20, `std::expected` does not exist.** Use a project-local result type and migrate at C++23. Do not pull in a third-party implementation.

### `std::numbers`

```cpp
const double radians = degrees * std::numbers::pi / 180.0;
```

Not `M_PI` (not standard, needs a feature macro on some platforms), not a local `constexpr double kPi`.

---

## Concurrency on this standard

The core document's preferences are all available:

| Need | Mechanism |
|------|-----------|
| Owned thread | `std::jthread` — joins in its destructor, supports cooperative cancellation. Prefer it to `std::thread` always. |
| Wait / notify | `std::latch` (single use), `std::barrier` (repeated), `std::atomic<T>::wait`/`notify_one`. Prefer these to a raw `condition_variable`. |
| Multi-mutex | `std::scoped_lock` |
| Read-heavy, measured | `std::shared_mutex` |

`std::jthread` over `std::thread` is not a style preference — a `std::thread` not joined before destruction terminates the program, and `jthread` removes that failure mode entirely.

---

## Ranges — use with restraint

Ranges compose well and eliminate intermediate containers. They also produce diagnostics that are difficult to read and can hide allocation and iteration cost.

**Good use** — a clear pipeline replacing a loop that needed a comment:

```cpp
auto long_edges = edges | std::views::filter([](const Edge& e) {
                              return e.length_mm > kMinEdgeMm;
                          });
```

**Poor use** — a pipeline the reader must simulate, or one whose laziness interacts with a mutation elsewhere. When a plain loop is clearer, write the plain loop. Value 4: boring is a feature.

Do not store a view that refers to a container which may be modified or destroyed. Views have the same lifetime hazard as `std::span`.

---

## Coroutines

Available here, and governed by the [core document's coroutine section](../conventions.md#coroutines). The rule most often violated: **a coroutine parameter is passed by value, never by reference**, because a reference dangles if the caller's frame is destroyed before resumption.

Do not introduce a coroutine because the facility exists. It earns its place when the alternative is an explicit state machine or a callback chain that obscures the flow.

---

## Banned on this standard

Everything in the [C++17 ban list](cpp17.md#banned-on-this-standard) plus:

| Banned | Use instead | Why |
|--------|-------------|-----|
| `(T*, size_t)` parameter pair outside `extern "C"` | `std::span` | Tier 2. |
| `const std::vector<T>&` for a read-only sequence parameter | `std::span<const T>` | Over-constrains the caller. |
| `std::ostringstream` for number formatting | `std::format` | Type safety, stream state. |
| `printf` / `snprintf` for formatting | `std::format` | Not type-safe. |
| Unconstrained template parameter | A concept or `requires` clause | `[CG T.10]` |
| `std::enable_if` SFINAE for constraints | Concepts | Diagnostics. |
| Hand-written comparison operator set | `= default` on `==`, or `<=>` | Boilerplate, asymmetry bugs. |
| `std::thread` as an owned member | `std::jthread` | A non-joined `std::thread` terminates the program. |
| Raw `std::condition_variable` for a one-shot wait | `std::latch`, or `atomic::wait` | Simpler and harder to misuse. |
| `M_PI` or a local pi constant | `std::numbers::pi` | Portability. |
| Compound assignment on a `volatile` | `std::atomic` | Deprecated in C++20. |
| Third-party `expected` on C++20 | Project result type; `std::expected` at C++23 | Dependency cost. |
| A generic `auto&&` fallback in a `std::visit` visitor | An explicit overload per alternative | Silently absorbs new alternatives. |

---

## Tooling

| Tool | C++20/23-specific configuration |
|------|--------------------------------|
| Standard | `set(CMAKE_CXX_STANDARD 20)` (or `23`) with `CMAKE_CXX_STANDARD_REQUIRED ON` |
| Warnings | The core baseline. `-Werror=switch` still worth keeping for enum switches, though `std::variant` is the primary exhaustiveness mechanism. |
| clang-tidy | The core set plus `modernize-use-std-format`, `modernize-use-constraints`, `modernize-use-nodiscard`. Pin `modernize-*` to the declared standard: on C++20, nothing suggesting `std::expected` or `std::print`. |
| Modules | Not yet. Tooling support across compilers and build systems is not broad enough. Revisit deliberately, not per project. |

C++23 features on a project declaring C++20 are bugs — `std::expected`, `std::print`, `std::mdspan`, `[[assume]]`. If the project should be on 23, change the build configuration deliberately.
