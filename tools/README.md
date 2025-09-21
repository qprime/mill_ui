# Tooling Utilities

Owner path: tools/

## 1. What this is

The tools package bundles repo-level utilities such as context builders, test runners, and the README sweeper.
These scripts keep the project AI-ready and enforce documentation hygiene.

## 2. When to use it

- Generate trimmed code context for prompts or offline analysis.
- Run the project-defined test harness across modules.
- Sweep and validate READMEs before committing documentation changes.

## 3. How to run

Invoke the utilities with `python -m` from the repository root.

```bash
python -m tools.context_builder continuum --output continuum/code_context.txt
python run.py tests
python tools/docs/sweep_readmes.py --dry-run
```

## 4. Inputs & outputs (for AI & humans)

- `tools/context_builder.py` — generates deduplicated code snapshots.
- `tools/test_runner.py` — curated pytest runner for the repository.
- `tools/docs/sweep_readmes.py` — README sweeper and validator.
- `docs/AI_README_GUIDE.md` — canonical README guidance consumed by the sweeper.
- `docs/_reports/` — output folder for sweeper JSON reports.

## 5. Public surface

- `tools.context_builder.build_context(target, output=None)` — produce code context archives.
- `tools.context_builder.main(argv=None)` — CLI entry for the context builder.
- `tools.test_runner.main()` — run the curated pytest selection.
- `tools.docs.sweep_readmes.main(argv=None)` — sweep and validate READMEs.

## 6. Invariants & guardrails

- Context builder strips docstrings/comments but preserves metadata headers.
- Test runner expects the repo root on `sys.path`; run from the repository root.
- Sweeper must not mutate files unless `--apply` is passed.
- All tools operate offline; avoid adding network dependencies.

## 7. Extension points

- Add new CLI utilities under `tools/` and expose them via `run.py` if needed.
- Expand sweeper specs by editing `tools/docs/sweep_readmes.py`.
- Capture additional machine-readable reports under `docs/_reports/`.
- Document any new tooling here so the sweeper can keep it in sync.

## 8. AI reading order

- `tools/context_builder.py` — Context snapshot generator.
- `tools/test_runner.py` — Pytest harness wrapper.
- `tools/docs/sweep_readmes.py` — README sweeper and validator.
- `docs/AI_README_GUIDE.md` — Canonical README structure and rules.
- `run.py` — Dispatcher integrating the tooling entrypoints.
