# Python Guidance v1.2 (GPT-5 Optimized)

## Philosophy

Code must be minimal, explicit, deterministic, and modular. Each file has **one public responsibility** with **one public API**. Functions are short and flat. No commentary or decoration is allowed. All behavior is discoverable and predictable.

---

## Hard MUST (never violate)

1. **File contract**

   * Each file has exactly one public API function or class.
   * `__all__` exports only that symbol.
   * File must live under a ground-truth folder (`skills/`, `continuum/`, `interfaces/`, etc.).

2. **Header**

   * First lines of file:

     ```python
     # name: filename.py
     # path: full/path/in/project
     # role: one-line purpose
     # deps: absolute imports only
     # inputs: brief, comma separated
     # outputs: brief
     ```
   * No other commentary or docstrings.

3. **Imports**

   * Absolute only.
   * No dynamic imports, no `exec`.

4. **Code constraints**

   * No decorators.
   * No comments or docstrings.
   * No global state.
   * Deterministic outputs.
   * Max nesting depth = 2.
   * Max function length = 25 lines.
     → If longer: split into named helpers in the same file.

5. **Emission**

   * Emit the **complete file only**.
   * No prefaces, notes, or explanations.

---

## Soft SHOULD (preferred but may bend)

1. Functions ≤20 lines (25 max).
2. Use frozen dataclasses for structured inputs/outputs.
   If not, return a minimal `Dict[str, Any]` with explicit keys.
3. Use constants at top of file for configuration.
4. Break long comprehensions into loops.
5. Keep key order stable.

---

## Layout Order

1. Imports
2. CONSTANTS
3. Dataclasses
4. Validators
5. Pure helpers
6. Public API (must be named `api` or equivalent)
7. Optional `main()` for trivial CLI entry (argparse + print only)

---

## Returns

* Public API returns:

  * A frozen dataclass **or**
  * A `Dict[str, Any]` with minimal documented schema.
* Never include unused or optional-by-default fields.

---

## Refusals

If constraints cannot be met (e.g., task needs multiple files, longer functions, cross-file coupling):

* **Do not emit non-compliant code.**
* Instead return a brief plan (list of required files/APIs).

---

## Enforcement Checklist (internal)

Before emitting code, verify:

* Header present with all 6 keys.
* `__all__` exports only the public API.
* Imports absolute.
* No decorators/comments/docstrings.
* Nesting ≤2.
* Functions ≤25 lines (split if needed).
* Layout order followed.
