# AI README Guidance

## Purpose
Design every README as an onboarding surface for humans and LLMs. Each document must describe the real
entrypoints, APIs, guardrails, and extension seams so the repository stays self-narrating.

## Canonical Structure
1. **What this is** *(1–2 sentences)* – concise purpose plus the primary entrypoints.
2. **When to use it** *(3–5 bullets)* – concrete scenarios or jobs-to-be-done.
3. **How to run** – short paragraph followed by an executable `bash` block with working commands.
4. **Inputs & outputs (for AI & humans)** – list canonical files, schemas, and generated artifacts.
5. **Public surface** – enumerate CLI flags, APIs, or classes with terse descriptions.
6. **Invariants & guardrails** – constraints, safety rails, units, or policies that cannot be broken.
7. **Extension points** – where to plug in new behaviour, configs, or modules.
8. **AI reading order** – 5–8 follow-up files (code or docs) with one-line descriptions; root README must
   spotlight the project’s anchor files.

Keep headings verbatim so automation can parse them. Additional sections may follow section 8 when absolutely
necessary, but only after the required structure.

## Owner & Metadata
- Every README starts with an H1 title followed immediately by `Owner path: <relative path>`.
- The owner path points at the canonical folder or module documented by the file.
- Optional HTML comment `<!-- ai-readme: allow-long -->` may appear after the owner line to extend length limits.

## Length & Formatting
- Target **300–800 words** per README. The sweeper enforces an 800-word cap unless the long-read override comment
  is present.
- Prefer bullet lists over long prose. Keep command blocks minimal and runnable as written.
- Use backticks for file names, commands, and literal sections.

## AI Reading Order
- The root README lists **5–8 anchor files** that give an AI the fastest ramp (entrypoints, planners, configs,
  representative tests).
- Module READMEs should link the most relevant code or docs (typically 4–6 items).
- Order anchors by importance so agents can short-circuit once they have enough context.

## Validation Rules
The sweeper (`python tools/docs/sweep_readmes.py`) enforces the following:
- Sections 1–5 must exist with non-empty content; sections 6–8 must be present unless genuinely N/A.
- Owner line must match the declared path and appear immediately after the H1 heading.
- Command examples must map to real scripts/flags and provide required positional arguments.
- README length ≤800 words unless `<!-- ai-readme: allow-long -->` is present.
- Duplicate `What this is` copy across READMEs is forbidden (two-line shared tagline is the maximum overlap).
- README updates must ship in the same PR that changes a CLI flag or public API surface.
- JSON report is written to `docs/_reports/readme_sweep.json` when `--apply` is used.

## Maintenance Workflow
1. Update code or CLI behaviour.
2. Regenerate affected README(s) manually or run the sweeper with `--apply`.
3. Review the diff, ensure commands stay correct, and commit together with the code change.
4. Run `python tools/docs/sweep_readmes.py --check` before merging; CI mirrors this step.

## Example Skeleton
```
# Module Name
Owner path: path/to/module

## 1. What this is
One-liner purpose.

## 2. When to use it
- Scenario A
- Scenario B

## 3. How to run
Install dependencies, then:
```bash
python -m package.cli --flag value
```

...
```
