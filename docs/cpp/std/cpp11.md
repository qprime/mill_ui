# C++11 / C++14 Appendix

**Covers:** C++11, C++14 | **Core:** [../conventions.md](../conventions.md) | **Matrix:** [../mechanisms.md](../mechanisms.md)

Read [conventions.md](../conventions.md) first. It states the rules. This appendix says what you write to satisfy them on a C++11 or C++14 project, and what the older standard does *not* excuse.

A project on this standard is a modern C++ project working under a constraint. It is not a 2011 project. Every Tier 1 rule in the core document is satisfiable here, and the code should read as though the author knew what C++17 offers and chose the best available expression of the same intent.

---

## What you have

C++11 is where modern C++ begins. The facilities that matter most are all present:

| Facility | Notes |
|----------|-------|
| `std::unique_ptr`, `std::shared_ptr`, `std::weak_ptr` | Full ownership vocabulary. Nothing is missing. |
| `enum class` | Always. There is no reason to write an unscoped `enum` except to match a C API. |
| `constexpr` | C++11 restricts a `constexpr` function to a single return statement; C++14 relaxes this. |
| `auto`, range-`for`, lambdas | Present. Lambdas cannot have `auto` parameters until C++14. |
| Move semantics, `noexcept` | Full. Rule of zero and rule of five both apply exactly as the core document states. |
| `std::atomic`, `std::mutex`, `std::thread`, `std::condition_variable` | The full C++11 concurrency model. |
| `static_assert` | This is how you state a template's requirements without concepts. |
| Default member initializers, `= default`, `= delete`, `override`, `final` | All present. Use them. |

**C++14 adds**, and use them if your project declares 14: `std::make_unique`, relaxed `constexpr`, generic lambdas (`auto` parameters), `std::shared_timed_mutex`, binary literals, digit separators.

---

## What you do not have, and what to write instead

### Absence — no `std::optional`

Tier 1 #3 still holds: absence is represented, never encoded. Two permitted forms; pick one per project and do not mix.

**Preferred — a project-local optional.** A minimal `Optional<T>` in the project's support header. It does not need to be `std::optional`; it needs `has_value()`, `operator*`, and a disengaged state.

**Acceptable at a documented boundary — a `try_*` function with an out-parameter:**

```cpp
bool try_find_tool(const ToolDatabase& db, const std::string& name, Tool& out);
```

This is the one place the core document's preference for return values over out-parameters `[CG F.20]` legitimately bends, because the alternative is a sentinel — and a sentinel is a Tier 1 violation while an out-parameter is a style compromise.

**Still forbidden:** NaN as missing, `-1` as not-found, empty string as null. The absence of `std::optional` is not a licence to encode absence in the value space.

### Closed-set variation — no `std::variant`

The intent is compiler-checked exhaustiveness. You get it from the warning system instead of the type system:

```cpp
enum class MoveKind { Comment, SetRpm, Rapid, Cut };

const char* mnemonic_of(MoveKind kind) {
    switch (kind) {                      // no default label, deliberately
        case MoveKind::Comment: return ";";
        case MoveKind::SetRpm:  return "M3";
        case MoveKind::Rapid:   return "G0";
        case MoveKind::Cut:     return "G1";
    }
    throw std::logic_error("mnemonic_of: unhandled MoveKind");
}
```

**The `switch` has no `default` label.** Under `-Werror=switch` — which is mandatory on a C++11 project, see [Tooling](#tooling) — adding an enumerator breaks compilation at every such switch. That is the same guarantee `std::visit` gives, obtained differently.

The unreachable throw after the switch satisfies the compiler's return-path analysis. It is not defensive programming; it is the "cannot happen" branch, and it is `[CG C.181]`-compliant because the tag and payload stay together as a documented unit.

For alternatives carrying payloads, a tagged struct with the payload in an anonymous union `[CG C.182]`, or — usually better and always simpler — a struct with the tag plus the superset of fields, documented as a unit. Prefer the simple form until profiling says otherwise. `[CG P.9]`

**Still forbidden:** an `enum` with an if/else-if chain. That obtains no guarantee at all, and it is the trap the core document names.

### Sequences — no `std::span`

Use an iterator pair, or `const std::vector<T>&` when the caller genuinely holds a vector:

```cpp
double path_length_mm(std::vector<Vec2>::const_iterator first,
                      std::vector<Vec2>::const_iterator last);

double path_length_mm(const std::vector<Vec2>& path);   // usually this
```

A `(const T*, size_t)` pair is permitted **only** at an `extern "C"` boundary, and is converted immediately:

```cpp
extern "C" int process_buffer(const Vec2* data, size_t length) {
    const std::vector<Vec2> path(data, data + length);
    // body uses path only; never touch data again
}
```

### Strings — no `std::string_view`

`const std::string&` for a non-owning string parameter. Accept the occasional allocation at a call site passing a literal; the alternative on C++11 is a `(const char*, size_t)` pair, which is worse.

### Formatting — no `std::format`

`std::ostringstream`, contained in **one** formatting helper per project rather than scattered:

```cpp
std::string format_fixed(double value, int precision);
```

Do not spread `ostringstream` construction through planners and emitters. One helper, one place to change when the project moves to C++20.

### Header constants — no `inline constexpr`

`inline constexpr` at namespace scope requires C++17. On C++11, either put the constant in an anonymous namespace in the `.cpp`, or expose a `constexpr` function:

```cpp
// header
constexpr double min_margin_mm() { return 10.0; }
```

A `constexpr` variable at namespace scope in a header gives each translation unit its own copy — harmless for a `double`, an ODR problem for anything with an address that matters.

### Constrained templates — no concepts

`static_assert` in the function body states the requirement where a concept would:

```cpp
template <class Container>
double total_length_mm(const Container& path) {
    static_assert(std::is_same<typename Container::value_type, Vec2>::value,
                  "total_length_mm: Container must hold Vec2");
    ...
}
```

SFINAE (`std::enable_if`) only where overload selection genuinely requires it. It is a last resort, not a default. `[CG T.120]`

### Informative failure — no `std::expected`

A project-local result type, or an exception at a module boundary. Do not pull in a third-party `expected`.

---

## Banned on this standard

| Banned | Use instead | Why |
|--------|-------------|-----|
| `std::auto_ptr` | `std::unique_ptr` | Copy semantics that silently transfer ownership. Deprecated in C++11, removed in C++17. Never use it, even here. |
| `std::bind` | A lambda | Opaque, worse diagnostics, worse codegen. |
| `throw()` exception specification | `noexcept` | Deprecated; different semantics. `[CG E.30]` |
| `NULL`, `0` as a pointer | `nullptr` | `[CG ES.47]` |
| `register` | *(delete it)* | Deprecated, meaningless. |
| `std::random_shuffle` | `std::shuffle` with an explicit engine | Deprecated; hidden global state defeats determinism (Tier 1 #9). |
| Unscoped `enum` | `enum class` | Implicit integer conversion. |
| `typedef` | `using` | `using` is clearer and works with templates. |
| Raw `new` / `delete` outside a resource manager | `std::unique_ptr` + a factory | `[CG R.11]`, `[CG ES.60]` |
| Hand-written `for (size_t i = 0; ...)` over a whole container | Range-`for` | `[CG ES.71]` |

---

## Tooling

| Tool | C++11/14-specific configuration |
|------|--------------------------------|
| Standard | `set(CMAKE_CXX_STANDARD 11)` (or `14`) with `CMAKE_CXX_STANDARD_REQUIRED ON` |
| Warnings | The core baseline **plus `-Werror=switch`**, which is load-bearing here: it is the mechanism that makes closed-set dispatch exhaustive. Also add `-Werror=switch-enum` if the project wants every enumerator listed explicitly rather than merely covered. |
| clang-tidy | The core set. `modernize-*` is useful but must be pinned to the project's standard — `modernize-use-nullptr` and `modernize-use-override` yes; anything suggesting C++17 facilities, no. |

Reaching for `std::optional`, `std::variant`, `std::span`, `std::string_view`, or `std::format` on a project declaring C++11 or C++14 is a bug, not an improvement. If the project should be on a newer standard, change the build configuration deliberately — do not smuggle facilities in one call site at a time.
