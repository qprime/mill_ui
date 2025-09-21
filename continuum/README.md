# Continuum Toolkit

Owner path: continuum/

## 1. What this is

Continuum collects graph, context, and metadata utilities that keep the repository AI-legible.
It powers code snapshots, dependency maps, and metadata regeneration for downstream tools.

## 2. When to use it

- Need an up-to-date dependency graph before planning a refactor.
- Generate stripped code or metadata blocks for LLM prompts.
- Refresh metadata headers after adding new files or moving modules.

## 3. How to run

Run the modules directly with `python -m` so outputs land in the working directory.

```bash
python -m continuum.project_graph --out project_graph.json
python -m continuum.code_context . --mode metadata --output metadata_headers.md
python -m continuum.regen_metadata_headers --root . --dry-run
```

## 4. Inputs & outputs (for AI & humans)

- `continuum/file_crawl.py` — canonical file walker shared by project graph and context tools.
- `project_graph.json` — optional JSON snapshot of modules, files, and dependencies.
- `metadata_headers.md` — metadata-only stream produced by `code_context` in metadata mode.
- `continuum/stats.py` — helpers used when printing token budgets.

## 5. Public surface

- `continuum.project_graph.build_project_graph(root_dir='.', model_name='gpt-4.1')` — return graph data and token stats.
- `continuum.code_context.generate_code_context(root_dir, mode='code')` — emit stripped code or header blocks.
- `continuum.regen_metadata_headers.update_metadata_headers(root='.', file_path=None, dry_run=False)` — rebuild metadata headers.
- `continuum.diff_tools.apply_patch(patch)` — utility for applying unified patches in automation flows.

## 6. Invariants & guardrails

- Metadata headers follow the `# key: value` format with path/type/tags/owner/depends_on/description.
- Exclude lists in `file_crawl` prevent noisy directories; prefer extending them over replacing.
- `regen_metadata_headers` never overwrites file bodies; run with `--dry-run` before committing changes.
- Token counts assume UTF-8 and the GPT-4.1 tokenizer with a stable cl100k fallback.

## 7. Extension points

- Add extra module roots by editing `MODULE_DIRS` in `project_graph.py`.
- Teach `find_files` about new extensions when asset types expand.
- Expose additional summary metrics by extending `stats.py` and the CLI output.

## 8. AI reading order

- `continuum/project_graph.py` — Builds module graphs and token statistics.
- `continuum/code_context.py` — Extracts stripped code and metadata blocks.
- `continuum/file_crawl.py` — Shared filesystem traversal and exclusion logic.
- `continuum/regen_metadata_headers.py` — Regenerates metadata headers via the LLM client.
- `continuum/diff_tools.py` — Patch application helpers used by automation.
