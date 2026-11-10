# Pocket with island

![Blueprint](output/pocket_with_island.svg)

**Demonstrates:** A pocket that leaves an island of material standing.

## What gets cut

A recessed panel that leaves a raised medallion standing in the middle.

Sheet 400 × 400 × 19mm mdf.

- `pocket-12.70mm.nc`: pocket, 12.7mm tool, 1 feature(s), to 6mm
- `profile-3.17mm.nc`: profile, 3.175mm tool, 1 feature(s), to 19.2mm

## Run

`python -m cli.mill --recipe docs/recipes/panels/pocket_with_island`

## Outputs

- `machining_summary.json`
- `metrics.json`
- `pocket-12.70mm.nc`
- `pocket_with_island.svg`
- `profile-3.17mm.nc`
