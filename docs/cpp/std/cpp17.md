# C++17 Appendix

**Covers:** C++17 | **Core:** [../conventions.md](../conventions.md) | **Matrix:** [../mechanisms.md](../mechanisms.md)

Read [conventions.md](../conventions.md) first. This appendix says what you write on a C++17 project.

C++17 is where the core document's vocabulary types arrive. `std::optional` and `std::variant` land here, which means two Tier 2 rules move from "obtain the guarantee some other way" to "there is one right answer." Most of what the core document describes is directly expressible.

---

## What C++17 gives you over C++11/14

| Facility | Effect on the standard |
|----------|----------------------|
| `std::optional<T>` | The answer for absence. [mechanisms.md §1](../mechanisms.md#1-absence) |
| `std::variant` + `std::visit` | The answer for closed-set variation. The `-Werror=switch` mechanism is no longer needed. [mechanisms.md §2](../mechanisms.md#2-closed-set-variation) |
| `std::string_view` | The answer for non-owning string parameters. |
| `if constexpr` | Replaces most tag dispatch and SFINAE. |
| `inline constexpr` at namespace scope | Header constants become straightforward. |
| Structured bindings | `auto [first, second] = ...` |
| Class template argument deduction (CTAD) | `std::pair p{1, 2.0}` without explicit `make_pair`. |
| `[[nodiscard]]`, `[[maybe_unused]]`, `[[fallthrough]]` | Standard attributes; all three earn their place. |
| `std::scoped_lock` | Multi-mutex locking without deadlock ordering bugs. |
| `std::shared_mutex` | Read-heavy locking, *once measured*. |
| `std::filesystem` | Path handling. |
| Guaranteed copy elision | Returning by value is unambiguously free. |
| Fold expressions | Variadic code without recursion. |

---

## The two rules that change

### Absence is `std::optional`

```cpp
std::optional<Tool> find_tool(const ToolDatabase& db, const std::string& name);
static std::optional<ConvexPolygon> try_from(Polygon points);
```

A `try_*` function returning `bool` with an out-parameter — the C++11 compromise — is a defect here. `[CG F.20]` applies without exception: prefer return values to output parameters.

`std::optional` is not a result type. Absence means *there is legitimately nothing here*. Failure carrying a reason still needs a project result type until C++23 — see [Informative failure](#informative-failure).

### Closed-set variation is `std::variant`

```cpp
struct Comment { std::string text; };
struct SetRpm  { double rpm; };
struct Rapid   { std::optional<double> x, y, z; };
struct Cut     { std::optional<double> x, y, z, feed; };

using Move = std::variant<Comment, SetRpm, Rapid, Cut>;
```

Dispatch with `std::visit` over an exhaustive overload set. The `overloaded` helper is the standard idiom:

```cpp
template <class... Ts>
struct overloaded : Ts... {
    using Ts::operator()...;
};
template <class... Ts>
overloaded(Ts...) -> overloaded<Ts...>;   // CTAD guide; unnecessary from C++20

std::string emit(const Move& move) {
    return std::visit(overloaded{
        [](const Comment& c) { return "; " + c.text; },
        [](const SetRpm& s)  { return format_rpm(s.rpm); },
        [](const Rapid& r)   { return format_rapid(r); },
        [](const Cut& c)     { return format_cut(c); },
    }, move);
}
```

Adding an alternative to `Move` breaks every `visit` that does not handle it. That is the guarantee, and it is why a `std::string kind` field is a Tier 2 violation on this standard.

**Do not add a generic `[](auto&&){}` fallback to a visitor.** It compiles for every future alternative and silently swallows the case you added — it destroys exactly the property `std::variant` was chosen for. A generic lambda is correct only when the body is genuinely alternative-independent.

---

## Facilities worth using deliberately

### `if constexpr` over SFINAE

```cpp
template <class T>
double magnitude(const T& v) {
    if constexpr (std::is_same_v<T, Vec2>) {
        return std::hypot(v.x, v.y);
    } else {
        return std::hypot(v.x, v.y, v.z);
    }
}
```

Readable where `std::enable_if` was not. It does not, however, make a template the right first choice — [Trap: premature template](../conventions.md#trap-premature-template) still applies. `[CG T.120]`

### `[[nodiscard]]`

Put it on any function whose return value is the point — which is most pure functions, and every `try_*`.

```cpp
[[nodiscard]] std::optional<ConvexPolygon> try_from(Polygon points);
[[nodiscard]] Paths plan_pocket(const PlanarFace& face, const Tool& tool,
                                const PocketParams& params);
```

Ignoring the result of `try_from` is always a bug, and this is how the compiler says so.

### `inline constexpr` for header constants

```cpp
// header — one object across all translation units
inline constexpr double kMinMarginMm = 10.0;
```

This removes the C++11 workaround of a `constexpr` function or an anonymous-namespace constant.

### `std::string_view` — with one caution

Correct for a non-owning string parameter. **Never store it as a member** and never return one that views a temporary: [Trap: stored view](../conventions.md#trap-stored-view). A `std::string_view` returned from a function taking `const std::string&` is a dangling-reference generator.

```cpp
void log_stage(std::string_view name);              // good
std::string_view name() const { return name_; }     // only if name_ outlives every caller
```

When in doubt, return `const std::string&` or a `std::string` by value.

### Structured bindings

Good for a genuine pair or a small struct return, which pairs with `[CG F.21]` — return a struct for multiple outputs.

```cpp
const auto [minx, miny, maxx, maxy] = bounds_of(polygon);
```

Do not use them to unpack something that should have named accessors. The names come from the struct's fields, so the struct's field names still have to be good.

---

## Informative failure

`std::expected` is **C++23**. On C++17, use a project-local result type or an exception at a module boundary — and do not pull in a third-party `expected` implementation. When the project moves to C++23, the local type is replaced in one commit.

```cpp
// project support header
template <class T, class E>
class Result { /* ... */ };
```

---

## Banned on this standard

Everything in the [C++11 ban list](cpp11.md#banned-on-this-standard) plus:

| Banned | Use instead | Why |
|--------|-------------|-----|
| `std::auto_ptr` | `std::unique_ptr` | Removed from the standard in C++17. It will not compile. |
| A `bool` + out-parameter `try_*` | `std::optional<T>` return | The C++11 compromise has no justification here. `[CG F.20]` |
| `std::string kind` tag field | `std::variant` | Tier 2. |
| `enum class` + if/else-if chain | `std::variant`, or a `default`-less `switch` | Obtains no exhaustiveness guarantee. |
| A generic `auto&&` fallback in a `std::visit` visitor | An explicit overload per alternative | Silently absorbs newly added alternatives. |
| `std::enable_if` for a compile-time branch | `if constexpr` | Readability, diagnostics. |
| A `constexpr` namespace-scope constant in a header | `inline constexpr` | One object rather than one per TU. |
| Third-party `expected` | Project result type | Dependency cost; migrate at C++23. |
| `std::random_shuffle` | `std::shuffle` | Removed in C++17. |

---

## Tooling

| Tool | C++17-specific configuration |
|------|-----------------------------|
| Standard | `set(CMAKE_CXX_STANDARD 17)` with `CMAKE_CXX_STANDARD_REQUIRED ON` |
| Warnings | The core baseline. `-Werror=switch` remains worth keeping — enum switches still exist — but it is no longer the load-bearing exhaustiveness mechanism. |
| clang-tidy | The core set plus `modernize-use-nodiscard`. Pin `modernize-*` to C++17: nothing suggesting `std::span`, `std::format`, or concepts. |

Reaching for `std::span`, `std::format`, concepts, or `std::expected` on a project declaring C++17 is a bug. Change the declared standard deliberately if the project should move.
