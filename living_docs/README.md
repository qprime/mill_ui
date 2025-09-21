# Living Docs

Owner path: living_docs/

## 1. What this is

Living Docs orchestrates the Living Truth Partner workflow for LTD documents.
It manages slugs, artifacts, prompts, and exports for AI-guided writing sessions.

## 2. When to use it

- Create or revise LTD documents with guardrails, personas, and action tracking.
- Inspect generated prompts, sections, and action items for a specific document.
- Export LTD artifacts (PDF, DOCX) for review or handoff.

## 3. How to run

Drive the workflow through the `ltp` CLI exposed by `run.py`.

```bash
python run.py ltp sections test_document
python run.py ltp prompts test_document
python run.py ltp revise test_document --apply
```

## 4. Inputs & outputs (for AI & humans)

- `living_docs/docs/<slug>.ltd.md` — ground-truth LTD source documents.
- `living_docs/artifacts/<slug>/` — summaries, prompts, history, and exports per document.
- `living_docs/templates/` — Pandoc templates for PDF/DOCX outputs.
- `skills/living_truth_partner/config.py` — config wiring storage locations for the CLI.

## 5. Public surface

- `python run.py ltp new <title>` — create a document slug and scaffold storage.
- `python run.py ltp sections <slug>` — list sections with word counts and guardrails.
- `python run.py ltp revise <slug> --apply` — apply AI-guided revision patches.
- `python run.py ltp persona <slug> --name ...` — append persona context to a document.

## 6. Invariants & guardrails

- Slugs are normalized to lowercase kebab-case; the CLI enforces naming.
- Artifacts live under `living_docs/artifacts/<slug>` and should be committed for audit trails.
- Audio ingestion (voice capture) requires explicit file paths; recording is optional.
- Exports must remain reproducible offline; avoid network lookups in exporters.

## 7. Extension points

- Add export formats by extending `skills.living_truth_partner.export_doc`.
- Introduce additional guardrails in `skills.living_truth_partner.guardrails`.
- Seed new templates under `living_docs/templates/` and reference them in exporters.
- Document new CLI verbs here and teach the sweeper how to validate them.

## 8. AI reading order

- `skills/living_truth_partner/cli.py` — CLI verbs and argparse surface for the workflow.
- `skills/living_truth_partner/project_store.py` — Slug normalization and storage layout.
- `living_docs/docs/test_document.ltd.md` — Sample LTD source structure.
- `living_docs/artifacts/test_document/context_summary.json` — Distilled context payload for the sample.
- `living_docs/templates/pdf/default.latex` — Pandoc template used for PDF exports.
