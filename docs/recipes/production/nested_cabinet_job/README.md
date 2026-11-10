# Nested cabinet job

**Demonstrates:** Nesting a part list with MaxRects, including templated parts, shaped parts and a per-part holding override.

## What gets cut

A cabinet part list nested with MaxRects: templated Shaker doors, plain panels, a rounded-corner part and a round part, held with onion skin by default and tabs on one part.

The job is `nested_cabinet_job.nest.yml`. Nest recipes commit no `output/`.

## Run

`python -m cli.nest docs/recipes/production/nested_cabinet_job/nested_cabinet_job.nest.yml -o <dir> --export-svg`

## Outputs

One PML file and one blueprint per sheet, plus a manifest, written to `<dir>`.
