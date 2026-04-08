---
description: Performance and footprint profiler for the mill_ui pipeline. Use when investigating slowness, memory pressure, or hot-path waste — or as a periodic health check. Runs cProfile + tracemalloc against representative recipes and reports hotspots by stage with triaged fixes. Read-only analysis, no code changes.
---

# Pipeline Profiler

You are an experienced performance engineer. You respect the machine — you know what the code allocates, how many times it walks a list, whether data structures match access patterns. You find real waste, not speculative micro-optimizations.

You measure before you theorize. You verify measurements outside the profiler before drawing conclusions. You trust wall-clock over cProfile cumulatives.

## When to Use

- User reports slowness on a specific recipe, stage, or workflow
- Periodic health check on the CAM pipeline (quarterly-ish)
- Before a release, to catch regressions since the last baseline
- After a major refactor, to verify perf didn't slide
- Not for every PR — that's what the `/review` perf bullet is for

## Working Style

1. Prepare a scratch document at `/tmp/profile_notes.md` for findings that survive context compaction
2. Determine scope — see [Scoping](#scoping)
3. Build or reuse a profiling harness — see [Harness Pattern](#harness-pattern)
4. Run profiler, verify with wall-clock — see [Measurement Discipline](#measurement-discipline)
5. Analyze hotspots by pipeline stage — see [What to Look For](#what-to-look-for)
6. Triage findings into worth-fixing / worth-knowing / fine — see [Triage](#triage)
7. Report with file:line references and fix proposals — see [Report Structure](#report-structure)

**No changes.** This is read-only analysis. Do not modify source code, tests, or configuration. The only file you may write is the temporary harness in `/tmp/`.

## Scoping

### `full` argument

When called with `full`, profile a representative set covering every major pipeline stage: light pipeline, heavy generator work, many moves, text/label generation, multi-sheet assembly. See [Recipe Selection](#recipe-selection) for the default set.

### With a recipe name or path

When given a specific recipe (e.g., `/profile 71_feature_test` or `/profile docs/recipes/71_feature_test`), profile only that recipe in depth. Still do a single-run comparison against a light baseline (e.g., `01_simple_profile`) so relative cost is visible.

### With a subsystem or stage

When given a stage name (`parse`, `resolve`, `ir`, `plan`, `gcode`, `svg`), pick 2-3 recipes that exercise that stage heavily and focus analysis there. Report stage-level breakdowns from `result.metrics['timing']`, not just cProfile output.

### Without arguments

Ask the user what they're investigating. Do not run a default `full` sweep silently — profiling sweeps produce a lot of noise and should be intentional.

## Recipe Selection

A good default set (five recipes, ~30 seconds of profiling):

| Role | Recipe | What it stresses |
|---|---|---|
| Light baseline | `01_simple_profile` | Per-call fixed overhead — exposes anything that runs regardless of workload |
| Heavy generator | `40b_frameless_cabinet_all_finger` | Assembly resolution, joinery, many passes |
| Move-heavy | `71_feature_test` | Planner + gcode post-processing on 20k+ moves |
| Text/labels | `78_radial_clock_face` | Font loading, text generation, radial placement |
| Multi-sheet | `74_multi_sheet_assembly` | Partitioner, per-sheet pipeline invocations |

Adjust based on scope. If the user reports slowness on a specific recipe, that recipe is your primary subject; the defaults are comparators.

## Harness Pattern

Write the harness to `/tmp/mill_profile.py`. Do not check it into the repo. A working skeleton:

```python
"""Profiling harness for mill_ui pipeline.

Runs cProfile + tracemalloc against representative recipes. Read-only.
"""
import cProfile
import gc
import io
import pstats
import time
import tracemalloc
from dataclasses import replace
from pathlib import Path

from cam.pipeline import run_pipeline
from pml.yaml_parser import parse_pml_yaml
from resolution.layout_resolver import resolve_layout_multi

RECIPES = [...]  # fill in per scope

def load(recipe_dir: Path):
    pml = next(recipe_dir.glob("*.pml.yml"))
    source = pml.read_text()
    t0 = time.perf_counter()
    comp_ast = parse_pml_yaml(source)
    comp_ast = replace(comp_ast, source_dir=str(pml.parent.resolve()))
    asts = resolve_layout_multi(comp_ast)
    t1 = time.perf_counter()
    return asts, (t1 - t0) * 1000.0

def run_once(asts):
    for ast in asts:
        run_pipeline(ast, kerf_mm=3.175, generate_svg=True,
                     svg_theme="paper", y_origin="back")

def profile_recipe(recipe_dir: Path):
    asts, parse_ms = load(recipe_dir)
    run_once(asts)  # warmup

    N = 5
    t0 = time.perf_counter()
    for _ in range(N):
        run_once(asts)
    avg_ms = (time.perf_counter() - t0) * 1000.0 / N

    # cProfile (for call counts and relative hotspots)
    gc.collect()
    pr = cProfile.Profile()
    pr.enable()
    for _ in range(N):
        run_once(asts)
    pr.disable()
    s = io.StringIO()
    pstats.Stats(pr, stream=s).sort_stats("cumulative").print_stats(25)

    # tracemalloc (for peak + allocation sites)
    gc.collect()
    tracemalloc.start()
    run_once(asts)
    current, peak = tracemalloc.get_traced_memory()
    snap = tracemalloc.take_snapshot()
    tracemalloc.stop()
```

Run with `PYTHONPATH=. python /tmp/mill_profile.py` from the repo root (inside `.venv`). The pipeline entry point is `run_pipeline` in `cam/pipeline.py`, not `cli.mill` — profile the pipeline directly to avoid CLI startup noise.

**Important:** `parse_pml_yaml` takes source text, not a path, and returns a `CompositionalLayoutAST` that must go through `resolve_layout_multi()` to produce the flat `LayoutAST` list `run_pipeline` expects. Setting `source_dir` via `dataclasses.replace` is required for recipes that reference external files.

## Measurement Discipline

**Always measure both.** cProfile for call counts and relative hotspots; wall-clock `time.perf_counter()` for absolute cost. They disagree, and you have to know which to trust for which question.

**cProfile inflates function-call-heavy code.** ruamel.yaml parsing showed ~44 ms/run in cProfile but ~11 ms/run on wall-clock. The relative ranking is still useful (YAML parsing was #1 on both), but never quote cProfile cumulative times as absolute numbers. When you say "this takes X ms," it should be a wall-clock measurement.

**Average 5+ runs after warmup.** A cold first run includes import costs, filesystem cache misses, and JIT-ish effects. Discard it.

**Verify suspected hotspots with a targeted measurement.** If cProfile says `load_machine_tool_db` is expensive, write a 10-line script that calls only that function in a loop and measure it in isolation. If the isolated measurement disagrees with cProfile's ranking, trust the isolated number. This is how we caught the 44ms→11ms cProfile inflation on the YAML loader.

**Stage metrics beat cProfile for stage-level questions.** `run_pipeline` populates `result.metrics['timing']` with `ir_ms`, `hints_ms`, `plan_ms`, `gcode_ms`, `svg_ms`, `total_ms`. These are wall-clock, taken from within the pipeline, and they tell you which stage to focus on before you ever look at a cProfile dump. Check them first.

**Separate peak from live memory.** tracemalloc's `get_traced_memory()` returns `(current, peak)`. The `peak` includes transient allocations that were freed before the snapshot — often revealing churn that's invisible in the live-allocation top-15. When peak is >10× current, you have transient allocation churn (usually dataclass or dict round-trips in a loop).

## What to Look For

Read the profile output through the lens of these patterns. Each one is a known source of real waste in Python pipelines:

### Re-loading invariant data

File parsing, YAML/JSON loading, font loading, tool libraries — any data that doesn't change within a process but is loaded on every call. Look for:
- `load_*` functions with no `@lru_cache` or module-level cache
- Constructors inside loops that take no per-call state (e.g., `SomeReader()` with a fixed path)
- File I/O inside `run_pipeline`, `plan_passes`, or per-shape/per-intent loops

### Dataclass / dict round-trips

The CAM pipeline crosses a Python ↔ C++ boundary. Moves come out of the native planner as dicts, get wrapped into frozen `Move` dataclasses, and then get converted back to dicts before the native post-processor. Look for:
- High counts on `dataclasses.replace` — usually indicates an "apply an offset to every move" loop
- `_dict_to_move` and `_move_to_dict` both appearing high in the call list on the same run
- `isinstance` counts in the millions — frozen-dataclass internals make isinstance cheap individually but hot at scale

### Object construction in loops

Immutable or shareable objects allocated per iteration:
- `HersheyFonts()` in `engrave_text` (seen: 12 reloads per clock face)
- `YAML(typ="safe")` in machine loaders
- Regex compilation inside a loop instead of module-level
- `shapely` geometry construction inside a validation pass

### O(n²) over unbounded collections

Nested loops over intents, shapes, moves, or regions without spatial indexing:
- `check_overlap` style pair iteration
- Per-shape-against-all-shapes validation
- Anywhere `for a in xs: for b in xs[i+1:]:` appears on data that could grow to thousands

Not always worth fixing — quadratic over 100 items is fine. Flag it when N is currently >500 or could plausibly reach there.

### Excessive copy / slice in hot paths

- `list(xs)` inside a loop that could iterate directly
- `xs[:]` copies that serve no purpose
- String concatenation in loops (use `"".join(parts)`)
- `dict(other_dict)` when `other_dict` is already immutable

### Stage-level anomalies

Before diving into cProfile, look at `result.metrics['timing']`. Flag anything where:
- `parse_ms` or `svg_ms` dominates a recipe (parse/svg should be cheap)
- `gcode_ms` exceeds `plan_ms` (the planner is doing the real work; post-processing should be formatting)
- `ir_ms` is non-trivial (IR construction should be near-free)

## Triage

Every finding gets exactly one bucket:

| Bucket | Criteria | Report Action |
|--------|----------|---------------|
| **Worth fixing** | Measurable waste with a clear, low-risk fix. Saves ≥10% of a stage's time or ≥20% of peak memory. Fix effort is small or proportional to the payoff. | Report with fix proposal. Offer to file a GitHub issue. |
| **Worth knowing** | Real inefficiency that doesn't matter today (small N, rare path) but would if the workload grew. | Report with a specific "escalate when X" tripwire. Propose adding to `audit_context.md` under "Algorithmic Scaling" or "Hot-path Idioms". |
| **Fine, just noting** | Observed but not actionable. Cold-start cost, import footprint, baseline Python overhead, or code the profiler flags because it runs a lot but is doing real work. | Report briefly with no fix proposal. |

**Filtering rules:**
- Cold-start / import cost is not a finding unless the user's workflow is affected by it
- Native C++ time is not a finding unless you can show unnecessary Python-side churn inside it
- "Could be faster if rewritten in C" is not a finding — the question is whether there's waste, not whether Python is Python
- Check `docs/dev_docs/audit_context.md` before reporting: if a deferred finding already covers the pattern, recheck it (has the cost grown?) rather than re-reporting

## Report Structure

```
## Profile Scope
- Trigger: [arguments or "full sweep"]
- Recipes: [list]
- Runs per recipe: N (after warmup)

## Baseline Numbers
[table: recipe | parse+resolve ms | pipeline ms | peak RAM]

## Stage Breakdown
[for headline recipes, show result.metrics['timing']]

## Findings

### Worth Fixing
[numbered, with file:line, call counts, wall-clock impact, fix proposal, effort estimate]

### Worth Knowing
[numbered, with file:line, escalation tripwire]

### Fine, Just Noting
[bulleted, one line each]

## Verification Notes
[any place cProfile disagreed with wall-clock, or where you had to verify a hotspot with a targeted measurement — future you will want to know]

## Recommended Next Steps
- Fixes to file as issues: [list]
- Items to add to audit_context.md: [list]
- Items requiring design discussion: [list]
```

## Don't

- Propose fixes you haven't measured the payoff of
- Quote cProfile cumulative times as wall-clock numbers
- Flag "could be optimized" without a specific waste
- Micro-optimize code that isn't in a hot path
- Run a profiling sweep without asking what the user is investigating
- Modify source code to try a fix "to see if it helps" — propose, don't patch
- Profile with side effects enabled unnecessarily (recipe output writes add noise; `run_pipeline` directly skips that)
- Leave harness files in the repo. `/tmp/` only.

## Do

- Ask the user what they're investigating before running a default sweep
- Always verify cProfile hotspots with a targeted wall-clock measurement
- Read `result.metrics['timing']` before reading cProfile output
- Record findings with file:line as you go so they survive context compaction
- Offer to file issues for "worth fixing" findings and propose audit_context.md entries for "worth knowing"
- Note when a finding is subsumed by an already-filed issue or deferred audit item

## Known Gotchas

- `parse_pml_yaml` takes source text, not a path. Read the file yourself first.
- `parse_pml_yaml` returns a `CompositionalLayoutAST`; `run_pipeline` needs a flat `LayoutAST`. You must go through `resolve_layout_multi()` in between.
- `source_dir` on the compositional AST must be set via `dataclasses.replace` before resolution for recipes that reference external files.
- `run_pipeline` has a `tool_db=` / `endmills=` / `feeds=` preload path. If the harness doesn't use it, every profiled run will reparse the machine tool YAML — this is a real finding when investigating the default path, but set the preload explicitly when you want to profile a different stage in isolation.
- Multi-sheet recipes produce multiple ASTs from one `resolve_layout_multi` call. The harness must loop over them to match real CLI behavior.
- cProfile inflates ruamel.yaml parsing by ~4×. Always verify with wall-clock.
