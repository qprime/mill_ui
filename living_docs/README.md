# Living Truth Partner Docs

Generated LTD projects live under `docs/` with supporting artifacts in `artifacts/<slug>/`.

- `context_summary.json`: current distillation payload
- `links.jsonl`: cross-document references
- `history/`: timestamped notes and patches
- `exports/`: PDF and DOCX outputs generated via pandoc

Templates for exports live in `templates/`. Provide a custom `default.docx` to override Pandoc's default DOCX styling when needed.

## CLI helpers

- `python run.py ltp sections <slug>` — list sections, word counts, and guardrail suggestions.
- `python run.py ltp prompts <slug>` — show the latest action prompts.
- `python run.py ltp actions <slug>` — manage action items (`--add`, `--set INDEX --done true`).
- `python run.py ltp persona <slug> --name Alex --role "Ops Manager" --goals "Scale throughput" --pains "Bottlenecks"` — append buyer personas.
- `python run.py ltp revise <slug> [--apply]` — gather guided revision suggestions and optionally apply them.
